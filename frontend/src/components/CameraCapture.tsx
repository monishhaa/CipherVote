import React, { useRef, useState, useEffect, useCallback } from 'react';
import { Camera, AlertCircle, RefreshCw, CheckCircle2, RotateCcw, VideoOff } from 'lucide-react';

export interface CameraCaptureProps {
  onCapture: (base64DataUrl: string) => void;
  onRetake?: () => void;
  isProcessing?: boolean;
}

export type CameraLifecycle = 'idle' | 'requesting' | 'live' | 'captured' | 'error';

export const CameraCapture: React.FC<CameraCaptureProps> = ({
  onCapture,
  onRetake,
  isProcessing = false,
}) => {
  const [lifecycle, setLifecycle] = useState<CameraLifecycle>('idle');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [capturedImage, setCapturedImage] = useState<string | null>(null);

  // Hardware / stream telemetry
  const [deviceLabel, setDeviceLabel] = useState<string>('Default Camera');
  const [resolution, setResolution] = useState<{ width: number; height: number }>({ width: 0, height: 0 });
  const [displayFrames, setDisplayFrames] = useState<number>(0);
  const [canCapture, setCanCapture] = useState<boolean>(false);

  // Refs
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const frameCountRef = useRef<number>(0);
  const animFrameIdRef = useRef<number | null>(null);
  const mountIdRef = useRef<number>(0);
  const lastThrottleTimeRef = useRef<number>(0);

  // Stop stream tracks cleanly
  const stopStream = useCallback(() => {
    if (animFrameIdRef.current) {
      cancelAnimationFrame(animFrameIdRef.current);
      animFrameIdRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setCanCapture(false);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopStream();
    };
  }, [stopStream]);

  // Track video frames via requestVideoFrameCallback or rAF
  const monitorStreamFrames = useCallback((videoEl: HTMLVideoElement, activeMount: number) => {
    let firstFrameConfirmed = false;
    const timeoutTimer = setTimeout(() => {
      if (!firstFrameConfirmed && mountIdRef.current === activeMount) {
        setLifecycle('error');
        setErrorMsg('Camera stream started but delivered 0 frames within 4 seconds. Please check device privacy settings.');
        stopStream();
      }
    }, 4000);

    const onFrame = (now: number) => {
      if (mountIdRef.current !== activeMount || !streamRef.current) return;

      frameCountRef.current += 1;
      if (!firstFrameConfirmed) {
        firstFrameConfirmed = true;
        clearTimeout(timeoutTimer);
        setCanCapture(true);
        if (videoEl.videoWidth > 0 && videoEl.videoHeight > 0) {
          setResolution({ width: videoEl.videoWidth, height: videoEl.videoHeight });
        }
      }

      // Throttle UI frame counter updates to at most twice per second (every 500ms)
      if (now - lastThrottleTimeRef.current >= 500) {
        setDisplayFrames(frameCountRef.current);
        if (videoEl.videoWidth > 0 && videoEl.videoHeight > 0) {
          setResolution({ width: videoEl.videoWidth, height: videoEl.videoHeight });
        }
        lastThrottleTimeRef.current = now;
      }

      if ('requestVideoFrameCallback' in videoEl) {
        (videoEl as any).requestVideoFrameCallback(onFrame);
      } else {
        animFrameIdRef.current = requestAnimationFrame(onFrame);
      }
    };

    if ('requestVideoFrameCallback' in videoEl) {
      (videoEl as any).requestVideoFrameCallback(onFrame);
    } else {
      animFrameIdRef.current = requestAnimationFrame(onFrame);
    }
  }, [stopStream]);

  // Explicit User Gesture: Start Camera
  const startCamera = async () => {
    const currentMount = ++mountIdRef.current;
    stopStream();
    setErrorMsg(null);
    setLifecycle('requesting');
    setCanCapture(false);
    frameCountRef.current = 0;
    setDisplayFrames(0);

    try {
      // 1. Try ideal HD constraints first
      let stream: MediaStream;
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' },
          audio: false,
        });
      } catch (fallbackErr) {
        // Fallback to basic video: true
        stream = await navigator.mediaDevices.getUserMedia({
          video: true,
          audio: false,
        });
      }

      if (mountIdRef.current !== currentMount) {
        // Stale or unmounted while waiting for user prompt
        stream.getTracks().forEach((t) => t.stop());
        return;
      }

      streamRef.current = stream;

      // Extract device label
      const videoTrack = stream.getVideoTracks()[0];
      if (videoTrack) {
        setDeviceLabel(videoTrack.label || 'Webcam (Active)');
      }

      // Attach to video element
      const videoEl = videoRef.current;
      if (videoEl) {
        videoEl.srcObject = stream;
        try {
          await videoEl.play();
        } catch (playErr: any) {
          throw new Error(`Video playback error: ${playErr?.message || 'Autoplay prevented'}`);
        }
      }

      setLifecycle('live');
      if (videoEl) {
        monitorStreamFrames(videoEl, currentMount);
      }
    } catch (err: any) {
      if (mountIdRef.current !== currentMount) return;
      setLifecycle('error');
      if (err.name === 'NotAllowedError') {
        setErrorMsg('Camera access was denied. Please allow camera permissions in Chrome (click the lock/tune icon in the address bar) and retry.');
      } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
        setErrorMsg('No camera device detected on this system.');
      } else if (err.name === 'NotReadableError' || err.name === 'TrackStartError') {
        setErrorMsg('Camera is currently in use by another application or tab.');
      } else {
        setErrorMsg(err.message || 'Failed to initialize camera.');
      }
    }
  };

  // Capture frame from canvas with brightness/variance validation
  const handleCapture = () => {
    const video = videoRef.current;
    if (!video || !canCapture) return;

    const w = video.videoWidth || 640;
    const h = video.videoHeight || 480;
    const canvas = document.createElement('canvas');
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.drawImage(video, 0, 0, w, h);

    // Validate frame content: check for black / blank frame
    try {
      const imgData = ctx.getImageData(0, 0, w, h).data;
      let totalLuma = 0;
      let sampleCount = 0;
      // Step by 16 to quickly sample image
      for (let i = 0; i < imgData.length; i += 16) {
        const r = imgData[i];
        const g = imgData[i + 1];
        const b = imgData[i + 2];
        const luma = 0.299 * r + 0.587 * g + 0.114 * b;
        totalLuma += luma;
        sampleCount++;
      }
      const avgLuma = sampleCount > 0 ? totalLuma / sampleCount : 0;
      if (avgLuma < 5.0) {
        setErrorMsg('Captured frame is completely dark or black. Please ensure your camera lens is not covered.');
        return;
      }
    } catch (_) {
      // ImageData security edge case; continue if blocked
    }

    const dataUrl = canvas.toDataURL('image/jpeg', 0.92);
    setCapturedImage(dataUrl);
    stopStream();
    setLifecycle('captured');
    onCapture(dataUrl);
  };

  const handleRetake = () => {
    setCapturedImage(null);
    setErrorMsg(null);
    onRetake?.();
    startCamera();
  };

  return (
    <div className="space-y-4">
      {/* Video Viewport Container */}
      <div className="relative rounded overflow-hidden border border-line bg-black min-h-[280px] flex items-center justify-center">
        {/* Single persistent video element */}
        <video
          ref={videoRef}
          autoPlay
          muted
          playsInline
          style={{
            display: lifecycle === 'live' ? 'block' : 'none',
            width: '100%',
            maxHeight: '380px',
            objectFit: 'cover',
            background: '#000',
          }}
        />

        {/* State 1: Idle (User gesture required) */}
        {lifecycle === 'idle' && (
          <div className="p-8 text-center space-y-3">
            <div className="w-12 h-12 rounded-full bg-paper-2 border border-line text-text-muted mx-auto flex items-center justify-center">
              <Camera className="w-6 h-6 text-accent" />
            </div>
            <div>
              <p className="text-sm font-medium text-ink">Webcam Inactive</p>
              <p className="text-xs text-text-muted mt-0.5 max-w-sm mx-auto">
                Click below to start your webcam. Browser camera permissions will be requested on click.
              </p>
            </div>
            <button
              type="button"
              onClick={startCamera}
              className="px-5 py-2.5 bg-primary hover:bg-primary-hover text-white text-xs font-semibold rounded transition flex items-center justify-center gap-2 mx-auto shadow-sm"
            >
              <Camera className="w-4 h-4" />
              <span>Start Camera</span>
            </button>
          </div>
        )}

        {/* State 2: Requesting */}
        {lifecycle === 'requesting' && (
          <div className="p-8 text-center space-y-3">
            <RefreshCw className="w-8 h-8 text-accent animate-spin mx-auto" />
            <div>
              <p className="text-sm font-medium text-ink">Requesting Camera...</p>
              <p className="text-xs text-text-muted mt-0.5">Please allow access in your browser prompt.</p>
            </div>
          </div>
        )}

        {/* State 3: Captured Still */}
        {lifecycle === 'captured' && capturedImage && (
          <div className="relative w-full">
            <img
              src={capturedImage}
              alt="Biometric enrollment frame"
              className="w-full max-h-[380px] object-cover"
            />
            <div className="absolute top-3 right-3 bg-paper/90 border border-line text-ink px-2.5 py-1 rounded text-xs font-mono flex items-center gap-1.5 shadow">
              <CheckCircle2 className="w-3.5 h-3.5 text-success" />
              <span>Face Photo Ready</span>
            </div>
          </div>
        )}

        {/* State 4: Error */}
        {lifecycle === 'error' && (
          <div className="p-8 text-center space-y-3">
            <div className="w-12 h-12 rounded-full bg-paper-2 border border-danger/30 text-danger mx-auto flex items-center justify-center">
              <AlertCircle className="w-6 h-6" />
            </div>
            <div>
              <p className="text-sm font-medium text-danger">Camera Notice</p>
              <p className="text-xs text-text-muted mt-1 max-w-sm mx-auto">
                {errorMsg || 'Unable to access video stream.'}
              </p>
            </div>
            <div className="flex items-center justify-center gap-2 pt-1">
              <button
                type="button"
                onClick={startCamera}
                className="px-4 py-2 bg-paper-2 border border-line text-ink text-xs font-medium rounded hover:bg-line/20 transition flex items-center gap-1.5"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Retry Camera</span>
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Telemetry Indicator (Camera name, resolution, frames count) */}
      {lifecycle === 'live' && (
        <div className="flex items-center justify-between text-[11px] font-mono text-text-muted px-1">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            <span>{deviceLabel}</span>
          </div>
          <div>
            <span>{resolution.width > 0 ? `${resolution.width}×${resolution.height}` : 'initializing'}</span>
            <span className="mx-1.5">•</span>
            <span>{displayFrames} frames</span>
          </div>
        </div>
      )}

      {/* Live Controls: Capture Photo */}
      {lifecycle === 'live' && (
        <div className="flex gap-2">
          <button
            type="button"
            onClick={handleCapture}
            disabled={!canCapture}
            className="flex-1 py-2.5 bg-primary hover:bg-primary-hover text-white text-xs font-semibold rounded transition flex items-center justify-center gap-2 shadow-sm disabled:opacity-50"
          >
            <Camera className="w-4 h-4" />
            <span>{canCapture ? 'Capture Photo' : 'Waiting for Video Frames...'}</span>
          </button>
          <button
            type="button"
            onClick={() => {
              stopStream();
              setLifecycle('idle');
            }}
            className="px-3 py-2.5 bg-paper-2 border border-line hover:bg-line/20 text-ink text-xs font-medium rounded transition flex items-center gap-1.5"
            title="Turn off camera"
          >
            <VideoOff className="w-3.5 h-3.5" />
            <span>Turn Off</span>
          </button>
        </div>
      )}

      {/* Captured Controls: Retake */}
      {lifecycle === 'captured' && (
        <div className="flex justify-end">
          <button
            type="button"
            onClick={handleRetake}
            disabled={isProcessing}
            className="px-4 py-2 bg-paper-2 border border-line hover:bg-line/20 text-ink text-xs font-medium rounded transition flex items-center gap-1.5 disabled:opacity-50"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Retake Photo</span>
          </button>
        </div>
      )}
    </div>
  );
};

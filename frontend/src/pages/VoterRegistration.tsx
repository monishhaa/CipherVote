import React, { useState, useRef, useEffect, useCallback } from 'react';
import { APP_NAME } from '../constants';
import {
  UserCheck,
  ShieldCheck,
  CheckCircle,
  ArrowRight,
  Camera,
  RefreshCw,
  AlertCircle,
  Upload,
  RotateCcw,
  Mail,
  Lock,
} from 'lucide-react';

interface VoterRegistrationProps {
  electionId?: string;
  electionTitle?: string;
  onRegistered?: (voterId: string, email: string) => void;
  onProceedToVote?: (voterId: string) => void;
}

export const VoterRegistration: React.FC<VoterRegistrationProps> = ({
  electionId = 'council-2026',
  electionTitle = 'University Student Council Election 2026',
  onRegistered,
  onProceedToVote,
}) => {
  // Form fields start EMPTY with placeholders
  const [voterId, setVoterId] = useState('');
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');

  // Camera state
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [cameraStatus, setCameraStatus] = useState<'idle' | 'live' | 'captured' | 'error'>('idle');
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const [deviceId, setDeviceId] = useState<string>('');
  const [snapshot, setSnapshot] = useState<string | null>(null);

  // Biometric state (128-d embedding)
  const [capturedEmbedding, setCapturedEmbedding] = useState<number[] | null>(null);
  const [isFaceProcessing, setIsFaceProcessing] = useState<boolean>(false);
  const [photoAccepted, setPhotoAccepted] = useState<boolean>(false);

  // Field Errors & Status
  const [fieldErrors, setFieldErrors] = useState<{
    voter_id?: string;
    email?: string;
    general?: string;
    biometric?: string;
  }>({});
  const [isLoading, setIsLoading] = useState(false);

  const [regResult, setRegResult] = useState<{
    voter_id: string;
    email: string;
    commitment: string;
    message: string;
  } | null>(null);

  const stopTracks = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
  }, []);

  const enumerate = useCallback(async () => {
    try {
      const all = await navigator.mediaDevices.enumerateDevices();
      const videoInputs = all.filter((d) => d.kind === 'videoinput');
      setDevices(videoInputs);
      if (!deviceId && videoInputs[0]) {
        setDeviceId(videoInputs[0].deviceId);
      }
    } catch (_) {}
  }, [deviceId]);

  const startCamera = useCallback(async () => {
    stopTracks();
    setCameraError(null);
    setFieldErrors((prev) => ({ ...prev, biometric: undefined }));
    try {
      const constraints: MediaStreamConstraints = {
        video: deviceId ? { deviceId: { exact: deviceId } } : true,
        audio: false,
      };
      const s = await navigator.mediaDevices.getUserMedia(constraints);
      streamRef.current = s;
      if (videoRef.current) {
        videoRef.current.srcObject = s;
        await videoRef.current.play().catch(() => {});
      }
      setCameraStatus('live');
      enumerate();
    } catch (e: any) {
      setCameraStatus('error');
      setCameraError(e.name + ': ' + e.message);
    }
  }, [deviceId, enumerate, stopTracks]);

  const capturePhoto = useCallback(() => {
    const video = videoRef.current;
    if (!video) return;
    const w = video.videoWidth || 640;
    const h = video.videoHeight || 480;
    const canvas = document.createElement('canvas');
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.drawImage(video, 0, 0, w, h);

    // Lenient black check on STILL only
    const imgData = ctx.getImageData(0, 0, Math.min(w, 64), Math.min(h, 64)).data;
    let sum = 0;
    for (let i = 0; i < imgData.length; i += 4) {
      sum += (imgData[i] + imgData[i + 1] + imgData[i + 2]) / 3;
    }
    const mean = sum / (imgData.length / 4);
    if (mean < 3) {
      setCameraStatus('error');
      setCameraError('Captured image is completely black. Ensure camera lens is uncovered.');
      return;
    }

    const dataUrl = canvas.toDataURL('image/jpeg', 0.92);
    setSnapshot(dataUrl);
    stopTracks();
    setCameraStatus('captured');
  }, [stopTracks]);

  const retakePhoto = useCallback(() => {
    setSnapshot(null);
    setPhotoAccepted(false);
    setCapturedEmbedding(null);
    setFieldErrors((prev) => ({ ...prev, biometric: undefined }));
    startCamera();
  }, [startCamera]);

  useEffect(() => {
    return () => {
      stopTracks();
    };
  }, [stopTracks]);

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === 'string') {
        setSnapshot(reader.result);
        stopTracks();
        setCameraStatus('captured');
        setPhotoAccepted(false);
        setCapturedEmbedding(null);
        setFieldErrors((prev) => ({ ...prev, biometric: undefined }));
      }
    };
    reader.readAsDataURL(file);
  };

  const handleUseThisPhoto = async () => {
    if (!snapshot) return;
    setIsFaceProcessing(true);
    setFieldErrors((prev) => ({ ...prev, biometric: undefined }));
    setCapturedEmbedding(null);
    setPhotoAccepted(false);

    try {
      const res = await fetch('/api/voters/process-face', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image_base64: snapshot }),
      });

      const data = await res.json();

      if (!res.ok) {
        const errorMsg = data.detail?.message || data.detail || 'Face validation failed. Please retake photo.';
        setFieldErrors((prev) => ({ ...prev, biometric: errorMsg }));
        setPhotoAccepted(false);
        return;
      }

      // Valid single face detected and 128-d embedding extracted
      setCapturedEmbedding(data.embedding);
      setPhotoAccepted(true);
      setFieldErrors((prev) => ({ ...prev, biometric: undefined }));
    } catch (err: any) {
      setFieldErrors((prev) => ({
        ...prev,
        biometric: err.message || 'Failed to connect to face processing service.',
      }));
      setPhotoAccepted(false);
    } finally {
      setIsFaceProcessing(false);
    }
  };

  const handleVoterIdChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setVoterId(e.target.value);
    if (fieldErrors.voter_id) {
      setFieldErrors((prev) => ({ ...prev, voter_id: undefined, general: undefined }));
    }
  };

  const handleEmailChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setEmail(e.target.value);
    if (fieldErrors.email) {
      setFieldErrors((prev) => ({ ...prev, email: undefined, general: undefined }));
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setFieldErrors({});

    if (!voterId.trim()) {
      setFieldErrors((prev) => ({ ...prev, voter_id: 'Voter ID is required' }));
      return;
    }
    if (!email.trim()) {
      setFieldErrors((prev) => ({ ...prev, email: 'Email address is required' }));
      return;
    }
    if (!capturedEmbedding) {
      setFieldErrors((prev) => ({
        ...prev,
        biometric: 'Facial enrollment required: Please capture your photo and click "Use This Photo".',
      }));
      return;
    }

    setIsLoading(true);

    try {
      const res = await fetch(`/api/voters/register?election_id=${encodeURIComponent(electionId)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          voter_id: voterId.trim(),
          full_name: fullName.trim() || 'Registered Voter',
          email: email.trim(),
          face_embedding: capturedEmbedding,
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        if (res.status === 409 && data.detail) {
          const detail = typeof data.detail === 'object' ? data.detail : { message: data.detail };
          if (detail.field === 'voter_id') {
            setFieldErrors({ voter_id: detail.message || 'This voter ID is already registered, pick another ID.' });
          } else if (detail.field === 'email') {
            setFieldErrors({ email: detail.message || 'This email address is already registered.' });
          } else {
            setFieldErrors({ general: detail.message || 'Duplicate voter credential detected.' });
          }
        } else {
          const msg = typeof data.detail === 'object' ? data.detail.message : data.detail;
          setFieldErrors({ general: msg || 'Registration error' });
        }
        return;
      }

      setRegResult({
        voter_id: data.voter_id,
        email: data.email,
        commitment: data.commitment,
        message: data.message,
      });

      if (onRegistered) {
        onRegistered(data.voter_id, data.email);
      }
    } catch (err: any) {
      setFieldErrors({ general: err.message || 'Network connection failed' });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto py-8 px-4">
      {/* Header */}
      <div className="text-center mb-8">
        <div className="inline-flex items-center justify-center p-3 bg-emerald-500/10 text-emerald-400 rounded-2xl border border-emerald-500/20 mb-3">
          <UserCheck className="w-8 h-8" />
        </div>
        <h1 className="text-2xl font-bold text-slate-100">Step 1: Voter Registration & Biometric Enrollment</h1>
        <p className="text-sm text-emerald-400/90 font-medium mt-1">
          Enrolling for: {electionTitle}
        </p>
        <p className="text-xs text-slate-400 mt-1 max-w-lg mx-auto">
          Enroll with your ID and a live facial photo. Your secret credential will be split via 2-of-2 Shamir secret sharing: <strong>Share A is emailed to you</strong>, and Share B is locked until election opening.
        </p>
      </div>

      {!regResult ? (
        <form onSubmit={handleRegister} className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-5">
          {/* Voter ID */}
          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
              Voter ID / Roll Number <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              value={voterId}
              onChange={handleVoterIdChange}
              placeholder="e.g. CS21B045 or VOTE-001"
              className={`w-full bg-slate-950 border rounded-xl px-4 py-2.5 text-sm text-slate-200 focus:outline-none font-mono transition ${
                fieldErrors.voter_id
                  ? 'border-red-500 focus:border-red-500'
                  : 'border-slate-800 focus:border-emerald-500'
              }`}
            />
            {fieldErrors.voter_id && (
              <p className="text-xs text-red-400 mt-1 flex items-center space-x-1">
                <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" />
                <span>{fieldErrors.voter_id}</span>
              </p>
            )}
          </div>

          {/* Full Name */}
          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
              Full Legal Name <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="Your full legal name"
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-slate-200 focus:outline-none focus:border-emerald-500"
            />
          </div>

          {/* Email */}
          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
              Registered Email Address (Share A Password Sent Here) <span className="text-red-400">*</span>
            </label>
            <input
              type="email"
              value={email}
              onChange={handleEmailChange}
              placeholder="name@organization.com"
              className={`w-full bg-slate-950 border rounded-xl px-4 py-2.5 text-sm text-slate-200 focus:outline-none transition ${
                fieldErrors.email
                  ? 'border-red-500 focus:border-red-500'
                  : 'border-slate-800 focus:border-emerald-500'
              }`}
            />
            {fieldErrors.email ? (
              <p className="text-xs text-red-400 mt-1 flex items-center space-x-1">
                <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" />
                <span>{fieldErrors.email}</span>
              </p>
            ) : (
              <p className="text-[11px] text-slate-400 mt-1 flex items-center space-x-1">
                <Mail className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />
                <span>Your voting password (Share A) will be delivered to this email.</span>
              </p>
            )}
          </div>

          {/* Biometric Face Photo Enrollment Section */}
          <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-3">
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold text-slate-200 uppercase tracking-wider flex items-center space-x-1.5">
                <Camera className="w-4 h-4 text-emerald-400" />
                <span>Biometric Facial Enrollment</span>
              </label>
              <span className="text-[11px] text-slate-400 font-mono">Live WebCam</span>
            </div>

            {/* Device selector if available */}
            {devices.length > 1 && cameraStatus !== 'captured' && (
              <div>
                <label className="block text-[11px] text-slate-400 mb-1">Select Camera:</label>
                <select
                  value={deviceId}
                  onChange={(e) => {
                    setDeviceId(e.target.value);
                    if (cameraStatus === 'live') {
                      setTimeout(startCamera, 50);
                    }
                  }}
                  className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-emerald-500"
                >
                  {devices.map((d, i) => (
                    <option key={d.deviceId || i} value={d.deviceId}>
                      {d.label || `Camera ${i + 1}`}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* Camera View Area */}
            <div className="relative rounded-xl overflow-hidden border border-slate-800 bg-black min-h-[240px] flex items-center justify-center">
              {/* Video Element for live preview */}
              <video
                ref={videoRef}
                autoPlay
                muted
                playsInline
                width={640}
                height={480}
                style={{
                  display: cameraStatus === 'live' ? 'block' : 'none',
                  width: '100%',
                  maxHeight: '360px',
                  objectFit: 'cover',
                  background: '#000',
                }}
              />

              {/* Idle State */}
              {cameraStatus === 'idle' && (
                <div className="p-6 text-center space-y-3">
                  <div className="w-12 h-12 rounded-full bg-slate-900 border border-slate-800 text-slate-400 mx-auto flex items-center justify-center">
                    <Camera className="w-6 h-6" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-slate-300">Camera Inactive</p>
                    <p className="text-xs text-slate-500 mt-0.5">Click below to start your webcam preview.</p>
                  </div>
                  <button
                    type="button"
                    onClick={startCamera}
                    className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-semibold transition"
                  >
                    Start Camera
                  </button>
                </div>
              )}

              {/* Error State */}
              {cameraStatus === 'error' && (
                <div className="p-6 text-center space-y-3">
                  <div className="w-12 h-12 rounded-full bg-red-500/10 border border-red-500/20 text-red-400 mx-auto flex items-center justify-center">
                    <AlertCircle className="w-6 h-6" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-red-400">Camera Error</p>
                    <p className="text-xs text-red-300/80 mt-1 max-w-xs mx-auto break-words">
                      {cameraError || 'Failed to start camera. Please check permissions.'}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={startCamera}
                    className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-semibold transition border border-slate-700"
                  >
                    Retry Camera
                  </button>
                </div>
              )}

              {/* Captured Snapshot State */}
              {cameraStatus === 'captured' && snapshot && (
                <div className="relative w-full">
                  <img
                    src={snapshot}
                    alt="Captured voter snapshot"
                    className="w-full max-h-[360px] object-cover"
                  />
                  {photoAccepted && (
                    <div className="absolute top-3 right-3 bg-emerald-500/90 text-white px-2.5 py-1 rounded-full text-xs font-semibold flex items-center space-x-1 shadow-lg backdrop-blur">
                      <UserCheck className="w-3.5 h-3.5" />
                      <span>Face Enrolled</span>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Camera Controls */}
            {cameraStatus === 'live' && (
              <button
                type="button"
                onClick={capturePhoto}
                className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-semibold transition flex items-center justify-center space-x-2 shadow-lg shadow-emerald-600/20"
              >
                <Camera className="w-4 h-4" />
                <span>Capture Photo</span>
              </button>
            )}

            {cameraStatus === 'captured' && (
              <div className="space-y-2">
                <div className="flex space-x-2">
                  <button
                    type="button"
                    onClick={handleUseThisPhoto}
                    disabled={isFaceProcessing || photoAccepted}
                    className={`flex-1 py-2.5 rounded-xl text-xs font-semibold transition flex items-center justify-center space-x-1.5 ${
                      photoAccepted
                        ? 'bg-emerald-600/20 text-emerald-400 border border-emerald-500/30 cursor-default'
                        : 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-600/20'
                    }`}
                  >
                    {isFaceProcessing ? (
                      <>
                        <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                        <span>Extracting Face Embedding...</span>
                      </>
                    ) : photoAccepted ? (
                      <>
                        <UserCheck className="w-3.5 h-3.5" />
                        <span>Photo Accepted & Template Ready</span>
                      </>
                    ) : (
                      <>
                        <UserCheck className="w-3.5 h-3.5" />
                        <span>Use This Photo</span>
                      </>
                    )}
                  </button>
                  <button
                    type="button"
                    onClick={retakePhoto}
                    disabled={isFaceProcessing}
                    className="px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs font-semibold transition flex items-center space-x-1.5 border border-slate-700"
                  >
                    <RotateCcw className="w-3.5 h-3.5" />
                    <span>Retake</span>
                  </button>
                </div>
              </div>
            )}

            {/* Fallback selfie upload option */}
            <div className="pt-2 flex items-center justify-between text-xs text-slate-400">
              <span className="text-[11px]">Or upload a photo:</span>
              <label className="cursor-pointer inline-flex items-center space-x-1 text-emerald-400 hover:text-emerald-300 font-medium">
                <Upload className="w-3.5 h-3.5" />
                <span>Choose Image File</span>
                <input
                  type="file"
                  accept="image/*"
                  onChange={handleFileUpload}
                  className="hidden"
                />
              </label>
            </div>

            {/* Biometric validation error */}
            {fieldErrors.biometric && (
              <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-xs flex items-center space-x-2">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                <span>{fieldErrors.biometric}</span>
              </div>
            )}

            <div className="pt-2 border-t border-slate-900 text-[11px] text-slate-400 flex items-center space-x-1.5">
              <ShieldCheck className="w-4 h-4 text-emerald-400 flex-shrink-0" />
              <span>Raw photos are ephemeral. Only the AES-256-GCM encrypted template is stored.</span>
            </div>
          </div>

          {fieldErrors.general && (
            <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-xs">
              {fieldErrors.general}
            </div>
          )}

          {/* Submit Button */}
          <button
            type="submit"
            disabled={isLoading || !photoAccepted}
            className={`w-full py-3 font-medium rounded-xl text-sm transition flex items-center justify-center space-x-2 ${
              photoAccepted && !isLoading
                ? 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-600/20'
                : 'bg-slate-800 text-slate-500 cursor-not-allowed'
            }`}
          >
            {isLoading ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                <span>Creating Shamir Shares & Vaulting Credentials...</span>
              </>
            ) : (
              <>
                <span>Complete Registration & Email Share A</span>
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </form>
      ) : (
        /* Successful Registration Card - SHARE A IS SENT TO EMAIL, NOT DISPLAYED ON WEBSITE */
        <div className="bg-slate-900 border border-emerald-500/30 rounded-2xl p-6 shadow-2xl space-y-6">
          <div className="flex items-center space-x-3 text-emerald-400">
            <CheckCircle className="w-7 h-7 flex-shrink-0" />
            <div>
              <h2 className="text-lg font-bold text-slate-100">Registration Complete!</h2>
              <p className="text-xs text-slate-400">Biometric enrollment and 2-of-2 Shamir split established.</p>
            </div>
          </div>

          {/* Email Confirmation Notice Box */}
          <div className="bg-emerald-950/40 border border-emerald-500/40 rounded-xl p-5 space-y-3">
            <div className="flex items-center space-x-2.5 text-emerald-400 font-semibold text-sm">
              <Mail className="w-5 h-5 flex-shrink-0" />
              <span>Secret Share A Dispatched to Registered Email</span>
            </div>
            <p className="text-xs text-slate-200 leading-relaxed">
              Your personal <strong>Secret Share A (voting password)</strong> has been sent to:{' '}
              <strong className="font-mono text-emerald-300 bg-emerald-950/80 px-2 py-0.5 rounded border border-emerald-500/30">{regResult.email}</strong>
            </p>
            <div className="flex items-start space-x-2 text-[11px] text-slate-400 pt-1">
              <Lock className="w-3.5 h-3.5 text-amber-400 flex-shrink-0 mt-0.5" />
              <span>
                <strong>Privacy & Security Notice:</strong> For election integrity and anti-coercion privacy, Share A is <strong>never displayed on this website</strong>. Please check your email inbox (and spam/junk folder) for your official {APP_NAME} Credential Card.
              </span>
            </div>
          </div>

          {/* Registration Details */}
          <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-3">
            <div>
              <span className="text-xs text-slate-500 font-semibold uppercase">Registered Voter:</span>
              <p className="text-sm font-medium text-slate-200">{fullName || voterId} ({regResult.voter_id})</p>
            </div>

            <div>
              <span className="text-xs text-slate-500 font-semibold uppercase">Target Election:</span>
              <p className="text-xs font-medium text-emerald-400">{electionTitle}</p>
            </div>

            <div>
              <span className="text-xs text-slate-500 font-semibold uppercase">Public Commitment H(S):</span>
              <p className="text-xs font-mono text-slate-300 break-all bg-slate-900/90 p-2 rounded border border-slate-800 mt-1">
                {regResult.commitment}
              </p>
            </div>

            <div className="p-3 bg-slate-900 rounded-lg border border-slate-800 text-xs text-slate-400 space-y-1">
              <span className="font-semibold text-slate-300">How to Cast Your Vote:</span>
              <p>1. Open your email inbox to retrieve your <strong>Secret Share A</strong>.</p>
              <p>2. On election day (when polls open), navigate to the <strong>2. Election Voting</strong> tab.</p>
              <p>3. Enter your Voter ID and Share A, pass the quick facial liveness check, and submit your encrypted ballot.</p>
            </div>
          </div>

          <div className="flex flex-col sm:flex-row gap-3">
            {onProceedToVote && (
              <button
                type="button"
                onClick={() => onProceedToVote(regResult.voter_id)}
                className="flex-1 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-sm font-semibold transition flex items-center justify-center space-x-2 shadow-lg shadow-emerald-600/20"
              >
                <span>Proceed to Voting Portal</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            )}
            <button
              type="button"
              onClick={async () => {
                try {
                  const res = await fetch(`/api/voters/outbox/${encodeURIComponent(regResult.voter_id)}`);
                  const data = await res.json();
                  if (res.ok && data.content) {
                    alert(`📬 Dispatched Email Outbox:\n\n${data.content}`);
                  } else {
                    alert('No outbox record found for this voter.');
                  }
                } catch (e: any) {
                  alert(`Failed to fetch outbox: ${e.message}`);
                }
              }}
              className="px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-sm font-medium transition border border-slate-700 flex items-center justify-center space-x-1.5"
            >
              <Mail className="w-4 h-4 text-emerald-400" />
              <span>Preview Dispatched Email</span>
            </button>
            <button
              type="button"
              onClick={() => {
                setRegResult(null);
                setVoterId('');
                setFullName('');
                setEmail('');
                setCapturedEmbedding(null);
                setPhotoAccepted(false);
                setSnapshot(null);
                setCameraStatus('idle');
              }}
              className="px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-sm font-medium transition border border-slate-700"
            >
              Register Another Voter
            </button>
          </div>
        </div>
      )}
    </div>
  );
};


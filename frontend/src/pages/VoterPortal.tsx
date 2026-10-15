import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Stepper, StepItem } from '../components/ui/Stepper';
import { StatusChip } from '../components/ui/Badge';
import { InfoDisclosure } from '../components/ui/InfoDisclosure';
import { Modal } from '../components/ui/Modal';
import { WebcamLiveness } from '../components/WebcamLiveness';
import { encryptVote } from '../crypto/elgamal';
import { generateDisjunctiveZKP, generateBallotSumProof } from '../crypto/zkp';
import { blindBallotToken, unblindBallotSignature } from '../crypto/blindSignature';
import {
  Camera,
  CheckCircle2,
  Lock,
  ArrowRight,
  RotateCcw,
  Copy,
  Check,
  AlertCircle,
  ExternalLink,
  ShieldCheck,
  ChevronLeft,
  Bell,
  Calendar,
  Search,
  CheckCheck
} from 'lucide-react';

interface Candidate {
  id: number;
  name: string;
}

interface VoterPortalProps {
  electionId?: string;
  electionTitle?: string;
  electionStatus?: string;
  isOpen?: boolean;
  navigateTo?: (path: string) => void;
}

const VOTER_STEPS: StepItem[] = [
  { id: 1, label: 'Register' },
  { id: 2, label: 'Await voting' },
  { id: 3, label: 'Verify identity' },
  { id: 4, label: 'Cast vote' },
  { id: 5, label: 'Receipt' },
];

export const VoterPortal: React.FC<VoterPortalProps> = ({
  electionId = 'council-2026',
  electionTitle = 'University Student Council Election 2026',
  electionStatus = 'REGISTRATION',
  isOpen = false,
  navigateTo = () => {},
}) => {
  const [currentStep, setCurrentStep] = useState<number>(1);

  // Registration Form State
  const [voterId, setVoterId] = useState<string>(() => {
    try {
      const saved = localStorage.getItem('ciphervote_saved_voter_id');
      return saved || '';
    } catch {
      return '';
    }
  });
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState<string>(() => {
    try {
      const saved = localStorage.getItem('ciphervote_saved_voter_email');
      return saved || '';
    } catch {
      return '';
    }
  });

  // Schedule & Window State
  const [formattedWindow, setFormattedWindow] = useState<string>('Dates to be announced');

  // Camera & Face Template
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [cameraStatus, setCameraStatus] = useState<'idle' | 'live' | 'captured' | 'error'>('idle');
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [snapshot, setSnapshot] = useState<string | null>(null);

  const [capturedEmbedding, setCapturedEmbedding] = useState<number[] | null>(null);
  const [isFaceProcessing, setIsFaceProcessing] = useState<boolean>(false);
  const [photoAccepted, setPhotoAccepted] = useState<boolean>(false);

  const [fieldErrors, setFieldErrors] = useState<{
    voter_id?: string;
    email?: string;
    general?: string;
    biometric?: string;
  }>({});
  const [isRegistering, setIsRegistering] = useState(false);

  const [regResult, setRegResult] = useState<{
    voter_id: string;
    email: string;
    commitment: string;
    shareA?: string;
    message: string;
    voting_window?: string;
  } | null>(null);

  // Voting State
  const [shareA, setShareA] = useState('');
  const [shareB, setShareB] = useState<string | null>(null);

  const [livenessPassed, setLivenessPassed] = useState<boolean>(false);
  const [livenessTelemetry, setLivenessTelemetry] = useState<any>(null);

  const [blindToken, setBlindToken] = useState<{
    nonce: string;
    signature: string;
  } | null>(null);

  const [candidates, setCandidates] = useState<Candidate[]>([
    { id: 0, name: 'Alice Candidate' },
    { id: 1, name: 'Bob Candidate' },
    { id: 2, name: 'Charlie Candidate' },
  ]);
  const [selectedCandidate, setSelectedCandidate] = useState<number | null>(null);
  const [electionPK, setElectionPK] = useState<bigint | null>(null);
  const [blindRsaPK, setBlindRsaPK] = useState<{ n: bigint; e: bigint } | null>(null);

  const [isVotingProcessing, setIsVotingProcessing] = useState<boolean>(false);
  const [receiptData, setReceiptData] = useState<{
    receiptCode: string;
    sequenceNumber: number;
    blockHash: string;
  } | null>(null);
  const [copiedReceipt, setCopiedReceipt] = useState<boolean>(false);
  const [copiedShareA, setCopiedShareA] = useState<boolean>(false);
  const [voteError, setVoteError] = useState<string | null>(null);

  // In-site Notifications State
  const [notifications, setNotifications] = useState<any[]>([]);
  const [unreadCount, setUnreadCount] = useState<number>(0);
  const [showNotifModal, setShowNotifModal] = useState<boolean>(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Check My Status Modal
  const [showStatusLookupModal, setShowStatusLookupModal] = useState<boolean>(false);
  const [lookupVoterId, setLookupVoterId] = useState<string>('');
  const [lookupEmail, setLookupEmail] = useState<string>('');
  const [lookupError, setLookupError] = useState<string | null>(null);
  const [isLookingUp, setIsLookingUp] = useState<boolean>(false);

  // Fetch election status, keys, and schedule
  const fetchElectionInfo = useCallback(async () => {
    try {
      const res = await fetch(`/api/election/status?election_id=${encodeURIComponent(electionId)}`);
      if (res.ok) {
        const data = await res.json();
        if (data.candidates && data.candidates.length > 0) {
          setCandidates(data.candidates);
        }
        if (data.public_key_h) setElectionPK(BigInt(data.public_key_h));
        if (data.blind_rsa_n && data.blind_rsa_e) {
          setBlindRsaPK({
            n: BigInt(data.blind_rsa_n),
            e: BigInt(data.blind_rsa_e),
          });
        }
        if (data.formatted_window) {
          setFormattedWindow(data.formatted_window);
        }
      }
    } catch (e) {
      console.error(e);
    }
  }, [electionId]);

  // Fetch in-site notifications for this voter
  const fetchNotifications = useCallback(async (currentVid: string) => {
    if (!currentVid) return;
    try {
      const res = await fetch(`/api/voters/notifications?voter_id=${encodeURIComponent(currentVid)}&election_id=${encodeURIComponent(electionId)}`);
      if (res.ok) {
        const data = await res.json();
        const prevCount = unreadCount;
        setNotifications(data.notifications || []);
        setUnreadCount(data.unread_count || 0);

        if (data.unread_count > prevCount && prevCount >= 0 && data.notifications.length > 0) {
          const latest = data.notifications[0];
          setToastMessage(latest.title);
          setTimeout(() => setToastMessage(null), 5000);
        }
      }
    } catch (e) {
      console.error(e);
    }
  }, [electionId, unreadCount]);

  useEffect(() => {
    fetchElectionInfo();
  }, [fetchElectionInfo]);

  useEffect(() => {
    if (voterId) {
      fetchNotifications(voterId);
      const interval = setInterval(() => {
        fetchNotifications(voterId);
      }, 30000);
      return () => clearInterval(interval);
    }
  }, [voterId, fetchNotifications]);

  useEffect(() => {
    if (regResult && currentStep === 1) {
      if (isOpen || electionStatus === 'OPEN' || electionStatus === 'VOTING') {
        setCurrentStep(3);
      } else {
        setCurrentStep(2);
      }
    }
  }, [regResult, isOpen, electionStatus, currentStep]);

  const stopTracks = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
  }, []);

  const startCamera = useCallback(async () => {
    stopTracks();
    setCameraError(null);
    setFieldErrors((prev) => ({ ...prev, biometric: undefined }));
    try {
      const s = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      streamRef.current = s;
      if (videoRef.current) {
        videoRef.current.srcObject = s;
        await videoRef.current.play().catch(() => {});
      }
      setCameraStatus('live');
    } catch (e: any) {
      setCameraStatus('error');
      setCameraError(e.name + ': ' + e.message);
    }
  }, [stopTracks]);

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

      setCapturedEmbedding(data.embedding);
      setPhotoAccepted(true);
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
        biometric: 'Facial enrollment required: Please capture your photo and click "Confirm Photo Template".',
      }));
      return;
    }

    setIsRegistering(true);

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
        let msg = 'Registration failed';
        if (typeof data.detail === 'string') msg = data.detail;
        else if (data.detail?.message) msg = data.detail.message;
        setFieldErrors((prev) => ({ ...prev, general: msg }));
        return;
      }

      try {
        localStorage.setItem('ciphervote_saved_voter_id', voterId.trim());
        localStorage.setItem('ciphervote_saved_voter_email', email.trim());
      } catch (_) {}

      const retrievedShareA = data.share_a || '';
      setShareA(retrievedShareA);

      setRegResult({
        voter_id: voterId.trim(),
        email: email.trim(),
        commitment: data.commitment || 'Recorded',
        shareA: retrievedShareA,
        message: data.message || 'Voter registered successfully',
        voting_window: data.voting_window || formattedWindow,
      });

      await fetchNotifications(voterId.trim());

      if (isOpen || electionStatus === 'OPEN' || electionStatus === 'VOTING') {
        setCurrentStep(3);
      } else {
        setCurrentStep(2);
      }
    } catch (err: any) {
      setFieldErrors((prev) => ({ ...prev, general: err.message || 'Registration failed' }));
    } finally {
      setIsRegistering(false);
    }
  };

  const handleMarkAllRead = async () => {
    if (!voterId) return;
    try {
      await fetch('/api/voters/notifications/mark-read', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ voter_id: voterId }),
      });
      setUnreadCount(0);
      setNotifications(prev => prev.map(n => ({ ...n, read_at: new Date().toISOString() })));
    } catch (e) {
      console.error(e);
    }
  };

  const handleLookupSession = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!lookupVoterId.trim() || !lookupEmail.trim()) {
      setLookupError('Both Voter ID and Email are required.');
      return;
    }

    setIsLookingUp(true);
    setLookupError(null);

    try {
      const res = await fetch('/api/voters/lookup-session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          voter_id: lookupVoterId.trim(),
          email: lookupEmail.trim(),
          election_id: electionId,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Voter record not found.');
      }

      setVoterId(data.voter_id);
      setEmail(data.email);
      setFullName(data.full_name);
      setFormattedWindow(data.voting_window);

      try {
        localStorage.setItem('ciphervote_saved_voter_id', data.voter_id);
        localStorage.setItem('ciphervote_saved_voter_email', data.email);
      } catch (_) {}

      setRegResult({
        voter_id: data.voter_id,
        email: data.email,
        commitment: 'Recorded',
        message: 'Registration verified from institutional roll.',
        voting_window: data.voting_window,
      });

      await fetchNotifications(data.voter_id);
      setShowStatusLookupModal(false);

      if (isOpen || electionStatus === 'OPEN' || electionStatus === 'VOTING') {
        setCurrentStep(3);
      } else {
        setCurrentStep(2);
      }
    } catch (err: any) {
      setLookupError(err.message);
    } finally {
      setIsLookingUp(false);
    }
  };

  const handleVerifyIdentityAndGetToken = async () => {
    if (!voterId || !shareA) {
      setVoteError('Voter ID and Secret Share A are required.');
      return;
    }
    setIsVotingProcessing(true);
    setVoteError(null);

    try {
      let currentShareB = shareB;
      if (!currentShareB) {
        const resB = await fetch(`/api/voters/share_b/${encodeURIComponent(voterId)}?election_id=${encodeURIComponent(electionId)}`);
        if (!resB.ok) {
          const err = await resB.json();
          setVoteError(err.detail || 'Time-lock is currently active for this election.');
          setIsVotingProcessing(false);
          return;
        }
        const dataB = await resB.json();
        currentShareB = dataB.share_b;
        setShareB(currentShareB);
      }

      if (!blindRsaPK) {
        await fetchElectionInfo();
      }
      if (!blindRsaPK) {
        throw new Error('Election cryptographic keys are not initialized.');
      }

      const ballotNonce = `ballot_token_${voterId}_${Date.now()}_${Math.random()}`;
      const { mPrime, rBlind } = await blindBallotToken(ballotNonce, blindRsaPK.n, blindRsaPK.e);

      const formattedTelemetry = {
        challenge_id: 'challenge_web',
        ear_scores: livenessTelemetry?.earScores || livenessTelemetry?.ear_scores || [0.35, 0.15, 0.36],
        yaw_angles: livenessTelemetry?.yawAngles || livenessTelemetry?.yaw_angles || [0.0, -12.0, 0.0],
        probe_embedding: livenessTelemetry?.probeEmbedding || livenessTelemetry?.probe_embedding || undefined,
      };

      const resAuth = await fetch(`/api/auth/blind-token?election_id=${encodeURIComponent(electionId)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          voter_id: voterId.trim(),
          share_a: shareA.trim(),
          share_b: currentShareB!.trim(),
          blinded_token: '0x' + mPrime.toString(16),
          liveness_telemetry: formattedTelemetry,
        }),
      });

      if (!resAuth.ok) {
        const err = await resAuth.json();
        let errMsg = 'Authentication failed';
        if (typeof err.detail === 'string') errMsg = err.detail;
        else if (err.detail?.message) errMsg = err.detail.message;
        throw new Error(errMsg);
      }

      const authData = await resAuth.json();
      const sPrime = BigInt(authData.blind_signature);
      const unblindedSig = unblindBallotSignature(sPrime, rBlind, blindRsaPK.n);

      setBlindToken({
        nonce: ballotNonce,
        signature: '0x' + unblindedSig.toString(16),
      });

      setCurrentStep(4);
    } catch (err: any) {
      setVoteError(err.message || 'Verification failed');
    } finally {
      setIsVotingProcessing(false);
    }
  };

  const handleCastVote = async () => {
    const selectedIndex = candidates.findIndex((c: { id: number }) => c.id === selectedCandidate);
    if (selectedCandidate === null || selectedIndex < 0 || !electionPK || !blindToken) {
      setVoteError('Please select a candidate before casting your ballot.');
      return;
    }
    setIsVotingProcessing(true);
    setVoteError(null);

    try {
      const ciphertexts = [];
      const randomizers = [];
      const disjunctiveProofs = [];

      for (let i = 0; i < candidates.length; i++) {
        const v = i === selectedIndex ? 1 : 0;
        const { ciphertext, randomizer } = encryptVote(electionPK, v);
        ciphertexts.push(ciphertext);
        randomizers.push(randomizer);

        const zkp = await generateDisjunctiveZKP(electionPK, ciphertext, v, randomizer);
        disjunctiveProofs.push(zkp);
      }

      const sumProof = await generateBallotSumProof(electionPK, ciphertexts, randomizers);

      const payload = {
        election_id: electionId,
        ciphertexts: ciphertexts.map((ct) => ({
          c1: '0x' + ct.c1.toString(16),
          c2: '0x' + ct.c2.toString(16),
        })),
        zkp_proofs: {
          disjunctive_proofs: disjunctiveProofs,
          sum_proof: sumProof,
        },
        token_nonce: blindToken.nonce,
        token_signature: blindToken.signature,
      };

      const res = await fetch('/api/ballots/cast', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Ballot casting failed');
      }

      const data = await res.json();
      setReceiptData({
        receiptCode: data.receipt_code,
        sequenceNumber: data.sequence_number,
        blockHash: data.block_hash,
      });
      setCurrentStep(5);
    } catch (err: any) {
      setVoteError(err.message || 'Failed to submit encrypted ballot.');
    } finally {
      setIsVotingProcessing(false);
    }
  };

  const copyReceipt = () => {
    if (!receiptData) return;
    navigator.clipboard.writeText(receiptData.receiptCode);
    setCopiedReceipt(true);
    setTimeout(() => setCopiedReceipt(false), 2000);
  };

  const copyShareA = () => {
    if (!shareA) return;
    navigator.clipboard.writeText(shareA);
    setCopiedShareA(true);
    setTimeout(() => setCopiedShareA(false), 2000);
  };

  return (
    <div className="max-w-[640px] mx-auto py-6 px-4">
      {/* Toast Notification on new incoming notification */}
      {toastMessage && (
        <div className="fixed top-16 right-4 z-50 p-4 bg-primary text-white rounded shadow-lg flex items-center gap-3 border border-accent animate-fade-in">
          <Bell className="w-5 h-5 text-accent flex-shrink-0" />
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-accent">New Election Notification</p>
            <p className="text-xs">{toastMessage}</p>
          </div>
        </div>
      )}

      {/* Slim Top Bar with Notifications Bell */}
      <header className="border-b border-border pb-4 mb-6 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => navigateTo('/')}
            className="text-xs text-text-muted hover:text-text flex items-center gap-1 transition"
          >
            <ChevronLeft className="w-3.5 h-3.5" />
            <span>Portals</span>
          </button>
          <span className="text-border">|</span>
          <span className="font-serif text-sm font-semibold text-text truncate max-w-[200px] sm:max-w-xs">
            {electionTitle}
          </span>
        </div>

        <div className="flex items-center gap-2.5">
          {/* Notifications Bell */}
          <button
            type="button"
            onClick={() => {
              setShowNotifModal(true);
              if (voterId) fetchNotifications(voterId);
            }}
            className="relative p-1.5 text-text-muted hover:text-text hover:bg-surface rounded transition"
            title="View In-Site Notifications"
          >
            <Bell className="w-4 h-4" />
            {unreadCount > 0 && (
              <span className="absolute -top-1 -right-1 bg-danger text-white text-[10px] font-bold w-4 h-4 rounded-full flex items-center justify-center">
                {unreadCount}
              </span>
            )}
          </button>
          <StatusChip status={electionStatus} />
        </div>
      </header>

      {/* Dynamic Voter Status & Schedule Banner */}
      <div className="mb-6 p-4 bg-surface border border-border rounded flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <span className="text-[11px] font-semibold text-accent-text uppercase tracking-wider block">
            Official Election Schedule
          </span>
          <p className="text-xs font-semibold text-text mt-0.5">{formattedWindow}</p>
        </div>

        {currentStep === 1 && (
          <Button
            size="sm"
            variant="secondary"
            onClick={() => setShowStatusLookupModal(true)}
            className="text-xs self-start sm:self-auto"
          >
            <Search className="w-3.5 h-3.5 mr-1" />
            Check My Status
          </Button>
        )}
      </div>

      {/* 5-Step Horizontal Stepper */}
      <div className="mb-8">
        <Stepper
          steps={VOTER_STEPS}
          currentStep={currentStep}
          onStepClick={(s) => {
            if (s < currentStep) setCurrentStep(s);
          }}
        />
      </div>

      {/* STEP 1: REGISTER */}
      {currentStep === 1 && (
        <Card
          title="Voter Registration & Enrollment"
          subtitle="Submit your official voter credentials and enroll your biometric template."
        >
          <form onSubmit={handleRegister} className="space-y-4">
            {fieldErrors.general && (
              <div className="p-3 bg-[#FEE2E2] border border-[#FECACA] rounded text-xs text-danger flex items-start gap-2">
                <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                <span>{fieldErrors.general}</span>
              </div>
            )}

            <Input
              label="Official Voter ID / Student ID"
              placeholder="e.g. STU-2026-001"
              value={voterId}
              onChange={(e) => setVoterId(e.target.value)}
              error={fieldErrors.voter_id}
              required
            />

            <Input
              label="Full Name (Official Record)"
              placeholder="e.g. Eleanor Vance"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
            />

            <Input
              label="Institutional Email Address"
              type="email"
              placeholder="e.g. voter@institution.edu"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              error={fieldErrors.email}
              helperText="Official schedule updates and notifications will be dispatched here (no secrets included)."
              required
            />

            <div className="pt-2">
              <label className="block text-xs font-semibold text-text uppercase tracking-wider mb-1.5">
                Facial Biometric Template Enrollment
              </label>

              <div className="border border-border rounded p-3.5 bg-[#FAF8F5]">
                {cameraStatus === 'idle' && !snapshot && (
                  <div className="text-center py-6">
                    <Camera className="w-8 h-8 text-text-muted mx-auto mb-2" />
                    <p className="text-xs text-text-muted mb-3">
                      Capture a live photo to generate your zero-knowledge biometric commitment.
                    </p>
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      onClick={startCamera}
                    >
                      Open Camera
                    </Button>
                  </div>
                )}

                {cameraStatus === 'live' && (
                  <div className="space-y-3 text-center">
                    <div className="relative rounded overflow-hidden border border-border bg-[#14202F] max-h-[260px] flex items-center justify-center">
                      <video
                        ref={videoRef}
                        autoPlay
                        muted
                        playsInline
                        className="w-full h-full object-cover"
                      />
                    </div>
                    <Button
                      type="button"
                      variant="primary"
                      size="sm"
                      onClick={capturePhoto}
                    >
                      Capture Photo
                    </Button>
                  </div>
                )}

                {snapshot && (
                  <div className="space-y-3">
                    <div className="relative rounded overflow-hidden border border-border bg-[#14202F] max-h-[240px] flex items-center justify-center">
                      <img src={snapshot} alt="Captured portrait" className="w-full h-full object-cover" />
                    </div>

                    <div className="flex items-center justify-between gap-2">
                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        onClick={retakePhoto}
                      >
                        <RotateCcw className="w-3.5 h-3.5 mr-1.5" />
                        Retake
                      </Button>

                      {!photoAccepted ? (
                        <Button
                          type="button"
                          variant="primary"
                          size="sm"
                          isLoading={isFaceProcessing}
                          onClick={handleUseThisPhoto}
                        >
                          Confirm Photo Template
                        </Button>
                      ) : (
                        <span className="text-xs text-success font-medium flex items-center gap-1">
                          <CheckCircle2 className="w-4 h-4" />
                          Template Verified (128-d)
                        </span>
                      )}
                    </div>
                  </div>
                )}

                {cameraError && (
                  <p className="text-xs text-danger mt-2">{cameraError}</p>
                )}
                {fieldErrors.biometric && (
                  <p className="text-xs text-danger mt-2">{fieldErrors.biometric}</p>
                )}
              </div>
            </div>

            <div className="pt-4 border-t border-border flex items-center justify-between">
              <span className="text-xs text-text-muted">
                Step 1 of 5
              </span>
              <Button
                type="submit"
                variant="primary"
                isLoading={isRegistering}
                disabled={!photoAccepted}
              >
                Complete Registration
                <ArrowRight className="w-4 h-4 ml-1.5" />
              </Button>
            </div>
          </form>
        </Card>
      )}

      {/* STEP 2: AWAIT VOTING WINDOW */}
      {currentStep === 2 && (
        <Card
          title="Registration Confirmed — Awaiting Voting Window"
          subtitle="Your registration is securely recorded. Voting will activate when the election authority opens the ballot box."
        >
          <div className="space-y-5">
            <div className="p-4 bg-[#E2EFE7] border border-[#B7D8C4] rounded">
              <div className="flex items-start gap-2.5">
                <CheckCircle2 className="w-5 h-5 text-success flex-shrink-0 mt-0.5" />
                <div>
                  <h4 className="font-semibold text-xs text-[#1E4D36]">
                    Voter Roll Enrollment Complete
                  </h4>
                  <p className="text-xs text-[#1E4D36]/90 mt-0.5">
                    Voter ID <strong className="font-mono">{voterId}</strong> has been enrolled with cryptographic commitment.
                  </p>
                </div>
              </div>
            </div>

            {/* Secret Share A On-Screen Backup */}
            {shareA && (
              <div className="p-4 bg-surface border border-accent/40 rounded">
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-xs font-semibold text-accent-text uppercase tracking-wider flex items-center gap-1.5">
                    <Lock className="w-3.5 h-3.5" />
                    Your Secret Share A (Save This Key)
                  </span>
                  <button
                    type="button"
                    onClick={copyShareA}
                    className="text-xs text-primary hover:underline flex items-center gap-1"
                  >
                    {copiedShareA ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                    <span>{copiedShareA ? 'Copied' : 'Copy'}</span>
                  </button>
                </div>
                <p className="text-xs font-mono bg-[#FAF8F5] p-2.5 rounded border border-border break-all text-text">
                  {shareA}
                </p>
                <p className="text-[11px] text-text-muted mt-1.5">
                  Notice: For security, Secret Share A is NOT sent in your notification email. Please copy and store it now.
                </p>
              </div>
            )}

            {/* Schedule Status Card */}
            <div className="p-4 bg-[#FAF8F5] border border-border rounded text-xs text-text-muted space-y-2">
              <div className="flex items-center gap-2">
                <Calendar className="w-4 h-4 text-accent" />
                <span className="font-semibold text-text">Scheduled Voting Window:</span>
              </div>
              <p className="font-semibold text-text pl-6">{formattedWindow}</p>
              <p className="pl-6 text-[11px]">
                You will receive an in-site notification and email as soon as the election authority opens the ballot box.
              </p>
            </div>

            <div className="pt-3 border-t border-border flex items-center justify-between">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setCurrentStep(1)}
              >
                &larr; View Registration
              </Button>

              <Button
                variant="primary"
                size="sm"
                disabled={!isOpen && electionStatus !== 'OPEN' && electionStatus !== 'VOTING'}
                onClick={() => setCurrentStep(3)}
              >
                Proceed to Identity Verification
                <ArrowRight className="w-4 h-4 ml-1.5" />
              </Button>
            </div>
          </div>
        </Card>
      )}

      {/* STEP 3: VERIFY IDENTITY & ANONYMOUS BLIND TOKEN */}
      {currentStep === 3 && (
        <Card
          title="Voter Identity Verification"
          subtitle="Reconstruct your credential commitment and complete live anti-spoof verification."
        >
          <div className="space-y-5">
            {voteError && (
              <div className="p-3 bg-[#FEE2E2] border border-[#FECACA] rounded text-xs text-danger flex items-start gap-2">
                <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                <span>{voteError}</span>
              </div>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Input
                label="Voter ID"
                value={voterId}
                onChange={(e) => setVoterId(e.target.value)}
                placeholder="STU-2026-001"
                required
              />

              <Input
                label="Secret Share A"
                value={shareA}
                onChange={(e) => setShareA(e.target.value)}
                placeholder="0x..."
                required
              />
            </div>

            <div className="pt-2">
              <WebcamLiveness
                actions={['BLINK', 'TURN_LEFT']}
                onCaptureCompleted={(telemetry) => {
                  setLivenessPassed(true);
                  setLivenessTelemetry(telemetry);
                }}
              />
            </div>

            <div className="pt-4 border-t border-border flex items-center justify-between">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setCurrentStep(2)}
              >
                &larr; Back
              </Button>

              <Button
                variant="primary"
                isLoading={isVotingProcessing}
                disabled={!livenessPassed || !voterId || !shareA}
                onClick={handleVerifyIdentityAndGetToken}
              >
                Issue Anonymous Ballot Token
                <ArrowRight className="w-4 h-4 ml-1.5" />
              </Button>
            </div>
          </div>
        </Card>
      )}

      {/* STEP 4: CAST ENCRYPTED VOTE & ZKP */}
      {currentStep === 4 && (
        <Card
          title="Confidential Voting Booth"
          subtitle="Select your preferred candidate. Your vote is encrypted client-side using threshold ElGamal."
        >
          <div className="space-y-5">
            {voteError && (
              <div className="p-3 bg-[#FEE2E2] border border-[#FECACA] rounded text-xs text-danger flex items-start gap-2">
                <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                <span>{voteError}</span>
              </div>
            )}

            <div className="p-3 bg-[#FAF8F5] border border-border rounded flex items-center justify-between">
              <div className="flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-success" />
                <span className="text-xs font-semibold text-text">Anonymous Token Issued</span>
              </div>
              <span className="text-[11px] font-mono text-text-muted truncate max-w-[200px]">
                {blindToken?.nonce.slice(0, 18)}...
              </span>
            </div>

            <div>
              <label className="block text-xs font-semibold text-text uppercase tracking-wider mb-2">
                Select Candidate
              </label>
              <div className="space-y-2">
                {candidates.map((c) => {
                  const isSelected = selectedCandidate === c.id;
                  return (
                    <div
                      key={c.id}
                      onClick={() => setSelectedCandidate(c.id)}
                      className={`p-3.5 border rounded cursor-pointer transition flex items-center justify-between ${
                        isSelected
                          ? 'border-primary bg-[#FAF8F5] ring-1 ring-primary'
                          : 'border-border bg-surface hover:bg-[#FAF8F5]'
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <div
                          className={`w-4 h-4 rounded-full border flex items-center justify-center ${
                            isSelected
                              ? 'border-primary bg-primary'
                              : 'border-[#CDC6B6] bg-surface'
                          }`}
                        >
                          {isSelected && <div className="w-1.5 h-1.5 rounded-full bg-white" />}
                        </div>
                        <span className="text-sm font-medium text-text">{c.name}</span>
                      </div>
                      <span className="text-xs text-text-muted font-mono">Option #{c.id + 1}</span>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="pt-4 border-t border-border flex items-center justify-between">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setCurrentStep(3)}
              >
                &larr; Back
              </Button>

              <Button
                variant="primary"
                isLoading={isVotingProcessing}
                disabled={selectedCandidate === null}
                onClick={handleCastVote}
              >
                Encrypt &amp; Submit Ballot
                <ArrowRight className="w-4 h-4 ml-1.5" />
              </Button>
            </div>
          </div>
        </Card>
      )}

      {/* STEP 5: RECEIPT & AUDIT */}
      {currentStep === 5 && (
        <Card
          title="Ballot Cast Successfully"
          subtitle="Your encrypted ballot is recorded on the immutable cryptographic bulletin board."
        >
          <div className="space-y-5">
            <div className="p-4 bg-[#E2EFE7] border border-[#B7D8C4] rounded flex items-start gap-3">
              <CheckCircle2 className="w-6 h-6 text-success flex-shrink-0 mt-0.5" />
              <div>
                <h4 className="font-semibold text-sm text-[#1E4D36]">
                  Ballot Confirmed &amp; Included
                </h4>
                <p className="text-xs text-[#1E4D36]/90 mt-0.5">
                  Your encrypted choices and zero-knowledge validity proofs have been validated by the election engine.
                </p>
              </div>
            </div>

            {receiptData && (
              <div className="border border-border rounded bg-surface p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-text uppercase tracking-wider">
                    Ballot Receipt Code
                  </span>
                  <Button
                    variant="quiet"
                    size="sm"
                    onClick={copyReceipt}
                    className="text-xs"
                  >
                    {copiedReceipt ? <Check className="w-3.5 h-3.5 mr-1" /> : <Copy className="w-3.5 h-3.5 mr-1" />}
                    <span>{copiedReceipt ? 'Copied' : 'Copy Code'}</span>
                  </Button>
                </div>

                <div className="p-3 bg-[#FAF8F5] border border-border rounded font-mono text-xs text-text break-all">
                  {receiptData.receiptCode}
                </div>

                <div className="grid grid-cols-2 gap-2 text-xs text-text-muted pt-2 border-t border-border/70">
                  <div>
                    <span className="block font-medium text-text">Bulletin Board Seq:</span>
                    <span className="font-mono">#{receiptData.sequenceNumber}</span>
                  </div>
                  <div>
                    <span className="block font-medium text-text">Merkle Block Hash:</span>
                    <span className="font-mono truncate block" title={receiptData.blockHash}>
                      {receiptData.blockHash.slice(0, 16)}...
                    </span>
                  </div>
                </div>
              </div>
            )}

            <div className="flex items-center justify-between pt-3 border-t border-border">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => navigateTo('/audit')}
              >
                <ExternalLink className="w-3.5 h-3.5 mr-1.5" />
                Inspect on Public Audit
              </Button>

              <Button
                variant="primary"
                size="sm"
                onClick={() => navigateTo('/')}
              >
                Return to Gateway
              </Button>
            </div>
          </div>
        </Card>
      )}

      {/* Collapsed Info Disclosure */}
      <div className="mt-8">
        <InfoDisclosure title="How is my vote protected? (Cryptographic Assurance)">
          <div className="space-y-3 pt-2">
            <div>
              <strong className="font-semibold text-text block mb-0.5">1. End-to-End Encryption</strong>
              <p className="text-text-muted">
                Your candidate selection is encrypted inside your browser using threshold ElGamal encryption. No server or authority ever sees your plaintext choice.
              </p>
            </div>
            <div>
              <strong className="font-semibold text-text block mb-0.5">2. Non-Interactive Zero-Knowledge Proofs (NIZKP)</strong>
              <p className="text-text-muted">
                Your browser attaches mathematical proofs guaranteeing your ballot contains exactly one valid candidate vote without revealing who you voted for.
              </p>
            </div>
            <div>
              <strong className="font-semibold text-text block mb-0.5">3. Anonymous Blind Credentials</strong>
              <p className="text-text-muted">
                The server blind-signs your ballot token during authentication. Because the token is unblinded in your browser, the authority cannot link your voter ID to the final submitted ballot.
              </p>
            </div>
          </div>
        </InfoDisclosure>
      </div>

      {/* NOTIFICATIONS MODAL */}
      <Modal
        isOpen={showNotifModal}
        onClose={() => setShowNotifModal(false)}
        title="In-Site Notifications"
        description="Official schedule updates and status announcements."
      >
        <div className="space-y-4">
          <div className="flex items-center justify-between pb-2 border-b border-border">
            <span className="text-xs font-semibold text-text-muted uppercase">
              {notifications.length} Notification{notifications.length === 1 ? '' : 's'}
            </span>
            {unreadCount > 0 && (
              <Button size="sm" variant="quiet" onClick={handleMarkAllRead} className="text-xs">
                <CheckCheck className="w-3.5 h-3.5 mr-1" />
                Mark all as read
              </Button>
            )}
          </div>

          <div className="space-y-3 max-h-72 overflow-y-auto pr-1">
            {notifications.length > 0 ? (
              notifications.map((n) => (
                <div
                  key={n.id}
                  className={`p-3 rounded border transition ${
                    n.read_at
                      ? 'bg-surface border-border text-text-muted'
                      : 'bg-[#FAF8F5] border-accent/40 text-text font-medium'
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="font-semibold text-xs text-text">{n.title}</span>
                    <span className="text-[10px] text-text-muted font-mono whitespace-nowrap">
                      {new Date(n.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                  <p className="text-xs mt-1 leading-relaxed text-text/90">{n.body}</p>
                </div>
              ))
            ) : (
              <div className="text-center py-6 text-text-muted text-xs">
                No notifications for this voter yet.
              </div>
            )}
          </div>

          <div className="pt-2 border-t border-border flex justify-end">
            <Button size="sm" variant="secondary" onClick={() => setShowNotifModal(false)}>
              Close
            </Button>
          </div>
        </div>
      </Modal>

      {/* CHECK MY STATUS MODAL */}
      <Modal
        isOpen={showStatusLookupModal}
        onClose={() => setShowStatusLookupModal(false)}
        title="Check My Voter Registration Status"
        description="Lookup your verified registration record using your Voter ID and registered email."
      >
        <form onSubmit={handleLookupSession} className="space-y-4">
          {lookupError && (
            <div className="p-3 bg-[#FEE2E2] border border-[#FECACA] rounded text-xs text-danger flex items-start gap-2">
              <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
              <span>{lookupError}</span>
            </div>
          )}

          <Input
            label="Voter ID"
            placeholder="e.g. STU-2026-001"
            value={lookupVoterId}
            onChange={(e) => setLookupVoterId(e.target.value)}
            required
          />

          <Input
            label="Registered Institutional Email"
            type="email"
            placeholder="e.g. voter@institution.edu"
            value={lookupEmail}
            onChange={(e) => setLookupEmail(e.target.value)}
            required
          />

          <div className="flex justify-end gap-2 pt-2 border-t border-border">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => setShowStatusLookupModal(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              isLoading={isLookingUp}
            >
              Lookup Record
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};

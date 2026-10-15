import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  ArrowRight,
  ArrowLeft,
  CheckCircle2,
  AlertCircle,
  Shield,
  Key,
  Upload,
  RefreshCw,
} from 'lucide-react';
import { CameraCapture } from '../components/CameraCapture';

interface PublicElection {
  election_id: string;
  title: string;
  status: string;
  is_open: boolean;
  registration_open: boolean;
  closed_reason?: string | null;
  scheduled_window?: string | null;
}

interface VoterRegisterProps {
  navigateTo: (path: string) => void;
  electionId?: string;
  electionTitle?: string;
  onSelectElection?: (id: string) => void;
}

export const VoterRegister: React.FC<VoterRegisterProps> = ({
  navigateTo,
  electionId = '',
  electionTitle: _electionTitle = '',
  onSelectElection,
}) => {
  const [step, setStep] = useState<1 | 2 | 3>(1);

  // Elections list & state
  const [elections, setElections] = useState<PublicElection[]>([]);
  const [selectedElectionId, setSelectedElectionId] = useState<string>(electionId);
  const [fetchingElections, setFetchingElections] = useState<boolean>(true);

  // Step 1: Form details
  const [voterId, setVoterId] = useState('');
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  // Step 2: Camera & Face Capture state
  const [snapshot, setSnapshot] = useState<string | null>(null);
  const [isFaceProcessing, setIsFaceProcessing] = useState(false);

  // Step 3: Registration response data
  const [registeredData, setRegisteredData] = useState<{
    voter_id: string;
    email_masked: string;
    delivery_status: string;
    voting_window: string;
  } | null>(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [alreadyRegisteredIds, setAlreadyRegisteredIds] = useState<string[]>([]);

  // Check if voter is already signed in
  useEffect(() => {
    const token = sessionStorage.getItem('voter_session_token');
    const storedVoterId = sessionStorage.getItem('voter_id');
    const storedEmail = sessionStorage.getItem('voter_email');
    if (storedVoterId) setVoterId(storedVoterId);
    if (storedEmail) setEmail(storedEmail);

    if (token) {
      fetch('/api/voter/my-elections', {
        headers: { Authorization: `Bearer ${token}` },
      })
        .then((res) => (res.ok ? res.json() : null))
        .then((data) => {
          if (data && data.elections) {
            setAlreadyRegisteredIds(data.elections.map((e: any) => e.election_id));
          }
        })
        .catch(() => {});
    }
  }, []);

  // Fetch elections on mount
  useEffect(() => {
    let active = true;
    fetch('/api/public/elections')
      .then((res) => (res.ok ? res.json() : Promise.reject('Failed to fetch elections')))
      .then((data) => {
        if (!active) return;
        const list: PublicElection[] = data.elections || [];
        setElections(list);

        const openList = list.filter((e) => e.registration_open);
        if (openList.length === 1) {
          // Exactly one open election -> auto-select
          setSelectedElectionId(openList[0].election_id);
          onSelectElection?.(openList[0].election_id);
        } else if (openList.length > 1) {
          // Multiple open elections: pick prop if open, else pick first open
          const match = openList.find((e) => e.election_id === electionId);
          const chosen = match ? match.election_id : openList[0].election_id;
          setSelectedElectionId(chosen);
          onSelectElection?.(chosen);
        } else if (list.length > 0) {
          // None open
          setSelectedElectionId(list[0].election_id);
        }
      })
      .catch(() => {
        if (active) setElections([]);
      })
      .finally(() => {
        if (active) setFetchingElections(false);
      });

    return () => {
      active = false;
    };
  }, [electionId, onSelectElection]);

  // File upload fallback
  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === 'string') {
        setSnapshot(reader.result);
        setError(null);
      }
    };
    reader.readAsDataURL(file);
  };

  // Step 1 Details Submit -> Proceed to Step 2 (Face Capture)
  const handleDetailsSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!selectedElectionId) {
      setError('Please select an active election to register for.');
      return;
    }
    const targetElection = elections.find((el) => el.election_id === selectedElectionId);
    if (targetElection && !targetElection.registration_open) {
      setError(`Registration is closed for "${targetElection.title}": ${targetElection.closed_reason || 'Closed'}`);
      return;
    }

    if (!voterId.trim() || !fullName.trim() || !email.trim() || !password) {
      setError('Please fill in all required registration fields.');
      return;
    }
    if (password.length < 6) {
      setError('Password must be at least 6 characters long.');
      return;
    }
    if (password !== confirmPassword) {
      setError('Passwords do not match. Please re-enter.');
      return;
    }

    setStep(2);
  };

  // Step 2 "Use this photo" -> Validate face embedding & complete registration
  const handleUseThisPhoto = async () => {
    if (!snapshot) return;
    setIsFaceProcessing(true);
    setError(null);

    try {
      // 1. Process still face photo
      const faceRes = await fetch('/api/voters/process-face', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image_base64: snapshot }),
      });

      let faceData: any;
      try {
        faceData = await faceRes.json();
      } catch (_) {
        const text = await faceRes.text().catch(() => '');
        throw new Error(text || 'Face processing service returned an unexpected response. Please try again.');
      }

      if (!faceRes.ok) {
        const errorMsg =
          faceData.detail?.message ||
          faceData.detail ||
          'Face capture failed. Please retake photo.';
        throw new Error(typeof errorMsg === 'string' ? errorMsg : JSON.stringify(errorMsg));
      }

      const embedding: number[] = faceData.embedding;
      if (!embedding || embedding.length !== 128) {
        throw new Error('Biometric extraction error: Invalid embedding vector received.');
      }

      // 2. Submit cryptographic registration with election_id in body
      setLoading(true);
      const regRes = await fetch(`/api/voter/register?election_id=${encodeURIComponent(selectedElectionId)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          election_id: selectedElectionId,
          voter_id: voterId.trim(),
          full_name: fullName.trim(),
          email: email.trim(),
          password: password,
          face_embedding: embedding,
        }),
      });

      let regData: any;
      try {
        regData = await regRes.json();
      } catch (_) {
        const text = await regRes.text().catch(() => '');
        throw new Error(text || 'Registration service returned an error. Please check details and try again.');
      }

      if (!regRes.ok) {
        const msg =
          regData.detail?.message ||
          regData.detail ||
          'Registration could not be completed. Please check details and try again.';
        throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
      }

      setRegisteredData({
        voter_id: regData.voter_id,
        email_masked: regData.email_masked || email.trim(),
        delivery_status: regData.delivery_status || 'DELIVERED',
        voting_window: regData.voting_window || 'Dates to be announced',
      });

      // Save credentials to session
      sessionStorage.setItem('securevote_voter_id', regData.voter_id);
      sessionStorage.setItem('voter_id', regData.voter_id);
      sessionStorage.setItem('voter_email', regData.email || email.trim());
      sessionStorage.setItem('voter_election_id', selectedElectionId);

      setStep(3);
    } catch (err: any) {
      setError(err.message || 'Face validation or registration error. Please retake photo.');
    } finally {
      setIsFaceProcessing(false);
      setLoading(false);
    }
  };

  const handleResendCredential = async () => {
    if (!registeredData) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/voter/reissue-credential', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          voter_id: registeredData.voter_id,
          password: password,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail?.message || data.detail || 'Failed to resend credential.');
      }
      setRegisteredData((prev) => prev ? { ...prev, delivery_status: data.delivery_status || 'DELIVERED' } : null);
      setCopied(true); // Re-use indicator to show "Email resent"
      setTimeout(() => setCopied(false), 3000);
    } catch (e: any) {
      setError(e.message || 'Failed to resend credential.');
    } finally {
      setLoading(false);
    }
  };

  // Determine election display states
  const openElections = elections.filter((e) => e.registration_open);
  const selectedElection = elections.find((e) => e.election_id === selectedElectionId);

  return (
    <div className="min-h-[calc(100vh-4rem)] bg-paper py-8 px-4 sm:px-6 lg:px-8 flex items-center justify-center">
      <div className="w-full max-w-2xl bg-paper border border-line rounded p-6 sm:p-10">
        {/* Loading state for public elections */}
        {fetchingElections ? (
          <div className="py-16 text-center text-xs font-mono text-text-muted space-y-2">
            <RefreshCw className="w-5 h-5 animate-spin mx-auto text-accent" />
            <p>Loading available election rosters...</p>
          </div>
        ) : elections.length === 0 ? (
          /* STATE 1: No elections exist at all */
          <div className="py-12 px-6 text-center space-y-4">
            <div className="w-12 h-12 rounded-full bg-paper-2 border border-line flex items-center justify-center mx-auto text-text-muted">
              <Shield className="w-6 h-6 text-accent" />
            </div>
            <h2 className="font-display text-2xl font-semibold text-ink">Registration Not Open</h2>
            <p className="text-text-muted text-sm max-w-md mx-auto leading-relaxed">
              Registration is not open yet. Please check back later.
            </p>
            <div className="pt-4">
              <button
                type="button"
                onClick={() => navigateTo('/')}
                className="px-4 py-2 text-xs font-medium text-ink bg-paper-2 border border-line rounded hover:bg-line/20 transition"
              >
                Return to Gateway
              </button>
            </div>
          </div>
        ) : openElections.length === 0 ? (
          /* STATE 2: Elections exist, but NONE accepts registration */
          <div className="py-8 px-2 space-y-6">
            <div className="text-center space-y-2">
              <div className="w-12 h-12 rounded-full bg-paper-2 border border-line flex items-center justify-center mx-auto text-text-muted">
                <AlertCircle className="w-6 h-6 text-warning" />
              </div>
              <h2 className="font-display text-2xl font-semibold text-ink">
                Registration Closed
              </h2>
              <p className="text-text-muted text-sm max-w-md mx-auto leading-relaxed">
                Registration is closed for all current elections.
              </p>
            </div>

            <div className="space-y-3 max-w-lg mx-auto">
              {elections.map((el) => (
                <div
                  key={el.election_id}
                  className="p-4 bg-paper-2 border border-line rounded flex items-center justify-between"
                >
                  <div>
                    <p className="font-medium text-sm text-ink">{el.title}</p>
                    <p className="text-xs text-text-muted mt-0.5">
                      {el.scheduled_window || 'Schedule to be announced'}
                    </p>
                  </div>
                  <div className="text-right">
                    <span className="inline-block px-2 py-0.5 text-[11px] font-mono rounded bg-paper border border-line text-text-muted uppercase">
                      {el.status}
                    </span>
                    <p className="text-[11px] text-danger mt-1 font-medium">
                      {el.closed_reason || 'Closed'}
                    </p>
                  </div>
                </div>
              ))}
            </div>

            <div className="pt-4 text-center">
              <button
                type="button"
                onClick={() => navigateTo('/')}
                className="px-4 py-2 text-xs font-medium text-ink bg-paper-2 border border-line rounded hover:bg-line/20 transition"
              >
                Return to Gateway
              </button>
            </div>
          </div>
        ) : (
          /* REGISTRATION FORM (States 3 & 4) */
          <>
            {/* Slim Step Progress Bar */}
            <div className="mb-8">
              <div className="flex items-center justify-between text-xs text-text-muted font-mono uppercase tracking-wider mb-3">
                <span>
                  Step {step} of 3:{' '}
                  {step === 1
                    ? 'Personal Details'
                    : step === 2
                    ? 'Biometric Enrollment'
                    : 'Credential Issued'}
                </span>
                <span>{step === 1 ? '33%' : step === 2 ? '66%' : '100%'}</span>
              </div>
              <div className="w-full h-1 bg-paper-2 rounded-full overflow-hidden border border-line/60">
                <div
                  className="h-full bg-accent transition-all duration-500"
                  style={{ width: step === 1 ? '33%' : step === 2 ? '66%' : '100%' }}
                />
              </div>
            </div>

            {/* Error banner (rendered strictly upon action failure, never on page load) */}
            {error && (
              <div className="mb-6 p-4 rounded bg-paper-2 border border-danger/40 text-danger text-xs flex items-start gap-2.5">
                <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                <span className="leading-relaxed">{error}</span>
              </div>
            )}

            {/* STEP 1: Personal Details & Password */}
            {step === 1 && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                <div className="mb-6">
                  <h1 className="font-display text-2xl sm:text-3xl font-semibold text-ink tracking-tight">
                    Voter Registration
                  </h1>
                  <p className="text-text-muted text-sm mt-1.5 leading-relaxed">
                    Provide your institutional details and create an account password to register on the official roll.
                  </p>
                </div>

                <form onSubmit={handleDetailsSubmit} className="space-y-4">
                  {/* Election Selector / Header Display */}
                  {elections.length === 1 && openElections.length === 1 ? (
                    /* STATE 3: Exactly one election open -> plain text banner, no dropdown */
                    <div className="p-3.5 bg-paper-2 border border-line rounded mb-2">
                      <span className="text-xs font-mono uppercase tracking-wider text-text-muted block mb-0.5">
                        Target Election
                      </span>
                      <p className="text-sm font-semibold text-ink">
                        Registering for: <span className="text-accent">{openElections[0].title}</span>
                      </p>
                      {openElections[0].scheduled_window && (
                        <p className="text-xs text-text-muted mt-0.5">
                          Window: {openElections[0].scheduled_window}
                        </p>
                      )}
                    </div>
                  ) : (
                    /* STATE 4: Two or more elections -> Accessible Select Dropdown */
                    <div className="mb-4">
                      <label
                        htmlFor="voter-election-select"
                        className="block text-xs font-medium text-ink uppercase tracking-wider mb-1.5 font-mono"
                      >
                        Election
                      </label>
                      <select
                        id="voter-election-select"
                        value={selectedElectionId}
                        onChange={(e) => {
                          setSelectedElectionId(e.target.value);
                          onSelectElection?.(e.target.value);
                          setError(null);
                        }}
                        className="w-full px-3.5 py-2.5 bg-paper border border-line rounded text-sm text-ink focus:bg-white focus:outline-none focus:border-accent transition"
                      >
                        {elections.map((el) => {
                          const isAlready = alreadyRegisteredIds.includes(el.election_id);
                          const isDisabled = !el.registration_open || isAlready;
                          return (
                            <option
                              key={el.election_id}
                              value={el.election_id}
                              disabled={isDisabled}
                            >
                              {el.title} {isAlready ? '(Already registered)' : el.registration_open ? `(${el.status})` : `— ${el.closed_reason || 'Closed'}`}
                            </option>
                          );
                        })}
                      </select>
                      {selectedElection && (
                        <p className="text-[11px] text-text-muted mt-1">
                          {selectedElection.registration_open
                            ? `Status: ${selectedElection.status} • Scheduled Window: ${selectedElection.scheduled_window || 'Dates to be announced'}`
                            : `Registration Closed: ${selectedElection.closed_reason}`}
                        </p>
                      )}
                    </div>
                  )}

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-medium text-ink uppercase tracking-wider mb-1 font-mono">
                        Voter ID
                      </label>
                      <input
                        type="text"
                        value={voterId}
                        onChange={(e) => setVoterId(e.target.value)}
                        placeholder="e.g. 2026-CS-042"
                        required
                        className="w-full px-3.5 py-2.5 bg-paper border border-line rounded text-sm text-ink focus:bg-white focus:outline-none focus:border-accent transition"
                      />
                    </div>

                    <div>
                      <label className="block text-xs font-medium text-ink uppercase tracking-wider mb-1 font-mono">
                        Full Name
                      </label>
                      <input
                        type="text"
                        value={fullName}
                        onChange={(e) => setFullName(e.target.value)}
                        placeholder="e.g. Elena Rostova"
                        required
                        className="w-full px-3.5 py-2.5 bg-paper border border-line rounded text-sm text-ink focus:bg-white focus:outline-none focus:border-accent transition"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-ink uppercase tracking-wider mb-1 font-mono">
                      Official Email Address
                    </label>
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="voter@university.edu"
                      required
                      className="w-full px-3.5 py-2.5 bg-paper border border-line rounded text-sm text-ink focus:bg-white focus:outline-none focus:border-accent transition"
                    />
                    <p className="text-[11px] text-text-muted mt-1">
                      Confirmation and schedule notifications will be dispatched here. Zero cryptographic secrets are ever sent by email.
                    </p>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
                    <div>
                      <label className="block text-xs font-medium text-ink uppercase tracking-wider mb-1 font-mono">
                        Account Password
                      </label>
                      <input
                        type="password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        placeholder="••••••••"
                        required
                        className="w-full px-3.5 py-2.5 bg-paper border border-line rounded text-sm text-ink focus:bg-white focus:outline-none focus:border-accent transition"
                      />
                    </div>

                    <div>
                      <label className="block text-xs font-medium text-ink uppercase tracking-wider mb-1 font-mono">
                        Confirm Password
                      </label>
                      <input
                        type="password"
                        value={confirmPassword}
                        onChange={(e) => setConfirmPassword(e.target.value)}
                        placeholder="••••••••"
                        required
                        className="w-full px-3.5 py-2.5 bg-paper border border-line rounded text-sm text-ink focus:bg-white focus:outline-none focus:border-accent transition"
                      />
                    </div>
                  </div>

                  <div className="pt-4 border-t border-line flex items-center justify-between">
                    <button
                      type="button"
                      onClick={() => navigateTo('/user/login')}
                      className="text-xs text-text-muted hover:text-ink transition underline underline-offset-4"
                    >
                      Already registered? Sign in
                    </button>

                    <button
                      type="submit"
                      className="py-2.5 px-5 bg-primary text-white text-sm font-medium rounded hover:bg-primary-hover transition flex items-center gap-2"
                    >
                      <span>Continue to Face Capture</span>
                      <ArrowRight className="w-4 h-4" />
                    </button>
                  </div>
                </form>
              </motion.div>
            )}

            {/* STEP 2: Plain Photo Capture (NO LIVENESS) */}
            {step === 2 && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                <div className="mb-6">
                  <h2 className="font-display text-2xl sm:text-3xl font-semibold text-ink tracking-tight">
                    Biometric Face Enrollment
                  </h2>
                  <p className="text-text-muted text-sm mt-1.5 leading-relaxed">
                    Capture a single still face photo. A 128-dimensional biometric embedding is extracted and encrypted with AES-256-GCM. Raw photo pixels are never stored to disk.
                  </p>
                </div>

                {/* Rebuilt Camera Capture Component */}
                <div className="mb-4">
                  <CameraCapture
                    onCapture={(img) => {
                      setSnapshot(img);
                      setError(null);
                    }}
                    onRetake={() => {
                      setSnapshot(null);
                      setError(null);
                    }}
                    isProcessing={isFaceProcessing || loading}
                  />
                </div>

                {/* Action Button: When snapshot is captured */}
                {snapshot && (
                  <div className="mb-4">
                    <button
                      type="button"
                      onClick={handleUseThisPhoto}
                      disabled={isFaceProcessing || loading}
                      className="w-full py-2.5 bg-primary hover:bg-primary-hover text-white text-xs font-semibold rounded transition flex items-center justify-center gap-2 shadow-sm disabled:opacity-50"
                    >
                      {isFaceProcessing || loading ? (
                        <>
                          <RefreshCw className="w-4 h-4 animate-spin" />
                          <span>Validating Face & Registering...</span>
                        </>
                      ) : (
                        <>
                          <CheckCircle2 className="w-4 h-4 text-white" />
                          <span>Use This Photo to Complete Registration</span>
                        </>
                      )}
                    </button>
                  </div>
                )}

                {/* Fallback Selfie Upload */}
                <div className="p-3 bg-paper-2 border border-line rounded flex items-center justify-between text-xs text-text-muted mb-6">
                  <span>Having camera issues?</span>
                  <label className="cursor-pointer inline-flex items-center gap-1 text-accent hover:underline font-medium">
                    <Upload className="w-3.5 h-3.5" />
                    <span>Upload a selfie instead</span>
                    <input
                      type="file"
                      accept="image/*"
                      onChange={handleFileUpload}
                      className="hidden"
                    />
                  </label>
                </div>

                <div className="pt-4 border-t border-line flex items-center justify-between">
                  <button
                    type="button"
                    onClick={() => {
                      setSnapshot(null);
                      setStep(1);
                    }}
                    disabled={isFaceProcessing || loading}
                    className="py-2 px-4 text-xs font-medium text-text-muted hover:text-ink transition flex items-center gap-1.5"
                  >
                    <ArrowLeft className="w-3.5 h-3.5" />
                    <span>Back to Details</span>
                  </button>
                </div>
              </motion.div>
            )}

            {/* STEP 3: Done & Email Confirmation */}
            {step === 3 && registeredData && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6">
                <div>
                  <div className="inline-flex items-center gap-2 text-xs font-mono uppercase bg-paper-2 text-success px-2.5 py-1 rounded border border-line mb-3">
                    <CheckCircle2 className="w-4 h-4 text-success" />
                    <span>Registration Complete & Confirmed</span>
                  </div>
                  <h2 className="font-display text-2xl sm:text-3xl font-semibold text-ink tracking-tight">
                    Voting credential dispatched
                  </h2>
                  <p className="text-text-muted text-sm mt-1.5 leading-relaxed">
                    Your identity is registered on the official voter roll for {selectedElection?.title || 'the election'}.
                  </p>
                </div>

                {/* Email Delivery Card */}
                <div className="p-5 bg-paper-2 border border-line rounded space-y-3">
                  <div className="flex items-center gap-2.5 text-ink font-semibold text-sm">
                    <Shield className="w-5 h-5 text-accent" />
                    <span>Secret Share A delivered via Email</span>
                  </div>
                  <p className="text-xs text-ink/80 leading-relaxed">
                    We sent your confidential voting credential and <code className="text-accent font-mono">.json</code> attachment to:
                  </p>
                  <div className="p-3 bg-white font-mono text-sm text-ink font-bold border border-line rounded flex items-center justify-between">
                    <span>{registeredData.email_masked}</span>
                    <span className="text-[11px] font-mono uppercase px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200">
                      {registeredData.delivery_status}
                    </span>
                  </div>
                  <p className="text-[11px] text-text-muted leading-relaxed">
                    Keep your credential attachment safe and do not share it with anyone. You will need your Voter ID (<span className="font-mono font-medium text-ink">{registeredData.voter_id}</span>) and Secret Share A to cast your ballot once voting opens.
                  </p>
                </div>

                {/* Explanatory Dual Credential Cards */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="p-4 bg-paper-2 border border-line rounded space-y-2">
                    <div className="flex items-center gap-2 text-ink font-semibold text-sm">
                      <Key className="w-4 h-4 text-accent" />
                      <span>Account Password</span>
                    </div>
                    <p className="text-xs text-text-muted leading-relaxed">
                      Used to log in to the Voter Portal, track election progress, and review announcements.
                    </p>
                  </div>

                  <div className="p-4 bg-paper-2 border border-line rounded space-y-2">
                    <div className="flex items-center gap-2 text-ink font-semibold text-sm">
                      <Shield className="w-4 h-4 text-accent" />
                      <span>Secret Share A</span>
                    </div>
                    <p className="text-xs text-text-muted leading-relaxed">
                      Emailed as an encrypted credential file. Never stored in browser history or displayed publicly.
                    </p>
                  </div>
                </div>

                {/* Resend / Reissue Action if Delivery Issue or Not Received */}
                <div className="p-4 bg-white border border-line rounded flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
                  <div>
                    <span className="font-semibold text-ink block">Didn't receive your credential email?</span>
                    <span className="text-text-muted text-[11px]">Check spam folder or request an immediate credential resend.</span>
                  </div>
                  <button
                    type="button"
                    onClick={handleResendCredential}
                    disabled={loading}
                    className="px-3.5 py-2 bg-paper-2 hover:bg-line/20 border border-line text-ink font-medium rounded transition flex items-center gap-1.5 self-start sm:self-auto font-mono text-xs disabled:opacity-50"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
                    <span>{copied ? 'Credential Resent!' : 'Send Credential Again'}</span>
                  </button>
                </div>

                {/* Voting Window Notice */}
                <div className="p-4 bg-paper-2 border border-line rounded text-xs text-text-muted space-y-1">
                  <span className="font-semibold text-ink block">Scheduled Voting Window:</span>
                  <span className="text-sm font-medium text-ink block">{registeredData.voting_window}</span>
                  <p className="text-[11px] text-text-muted pt-1">
                    You will receive an in-site notification and email update when voting officially opens.
                  </p>
                </div>

                <div className="pt-4 border-t border-line flex items-center justify-end gap-3">
                  <button
                    type="button"
                    onClick={() => navigateTo('/user/overview')}
                    className="py-2.5 px-6 bg-primary text-white text-sm font-medium rounded hover:bg-primary-hover transition flex items-center gap-2"
                  >
                    <span>Go to Voter Portal</span>
                    <ArrowRight className="w-4 h-4" />
                  </button>
                </div>
              </motion.div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default VoterRegister;

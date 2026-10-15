import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  KeyRound,
  ShieldCheck,
  CheckCircle2,
  AlertCircle,
  Clock,
  Users,
  Download,
  ArrowRight,
  RotateCcw,
  RefreshCw,
  Lock,
  Unlock,
  BarChart3,
  Trophy,
} from 'lucide-react';
import { APP_NAME } from '../constants';

interface CeremonyPageProps {
  token?: string;
  navigateTo?: (path: string) => void;
}

interface SlotInfo {
  position: number;
  name: string;
  is_present: boolean;
  is_accepted: boolean;
  is_locked: boolean;
  lockout_remaining_seconds: number;
  is_you: boolean;
}

interface CeremonyEvent {
  time: string;
  type: string;
  message: string;
  position?: number;
}

export const CeremonyPage: React.FC<CeremonyPageProps> = ({ token: propToken, navigateTo }) => {
  const [pastedInput, setPastedInput] = useState<string>('');
  const [pasteError, setPasteError] = useState<string | null>(null);
  const [activeToken, setActiveToken] = useState<string>(propToken || '');

  useEffect(() => {
    if (propToken) {
      setActiveToken(propToken);
    }
  }, [propToken]);

  const [loading, setLoading] = useState<boolean>(Boolean(propToken));
  const [error, setError] = useState<string | null>(null);

  // Trustee & Election Metadata
  const [electionInfo, setElectionInfo] = useState<{
    election_id: string;
    election_title: string;
    election_status: string;
    is_voting_closed: boolean;
    scheduled_close: string | null;
    your_position: number;
    your_name: string;
    total_trustees: number;
    threshold_t: number;
    window_minutes: number;
    is_unlocked: boolean;
    has_approved: boolean;
    results_published: boolean;
  } | null>(null);

  // Live Ceremony State
  const [ceremonyState, setCeremonyState] = useState<{
    status: string; // WAITING, IN_PROGRESS, UNLOCKED, COMPLETED
    all_present: boolean;
    present_count: number;
    next_expected_position: number | null;
    accepted_count: number;
    remaining_seconds: number;
    window_seconds: number;
    reset_reason: string | null;
    slots: SlotInfo[];
    event_log: CeremonyEvent[];
  } | null>(null);

  // Code input
  const [inputCode, setInputCode] = useState<string>('');
  const [isSubmittingCode, setIsSubmittingCode] = useState<boolean>(false);
  const [submissionError, setSubmissionError] = useState<string | null>(null);

  // Validation Console State (Post-Unlock)
  const [validationSummary, setValidationSummary] = useState<any | null>(null);
  const [summaryError, setSummaryError] = useState<string | null>(null);
  const [isApproving, setIsApproving] = useState<boolean>(false);
  const [approvalMessage, setApprovalMessage] = useState<string | null>(null);

  const socketRef = useRef<WebSocket | null>(null);
  const pingIntervalRef = useRef<any>(null);

  // Fetch initial info
  const fetchInfo = useCallback(async () => {
    if (!activeToken) return;
    setLoading(true);
    try {
      const res = await fetch(`/api/ceremony/info/${encodeURIComponent(activeToken)}`);
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Could not load ceremony details.');
      }
      const data = await res.json();
      setElectionInfo(data);
      setCeremonyState(data.ceremony_state);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Error connecting to ceremony server.');
    } finally {
      setLoading(false);
    }
  }, [activeToken]);

  // Establish WebSocket connection with fallback
  useEffect(() => {
    if (!activeToken) return;
    fetchInfo();

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/ceremony/ws/${encodeURIComponent(activeToken)}`;
    const ws = new WebSocket(wsUrl);
    socketRef.current = ws;

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.status) {
          setCeremonyState(data);
        }
      } catch (e) {
        console.error('WS parse error:', e);
      }
    };

    ws.onopen = () => {
      pingIntervalRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'PING' }));
        }
      }, 5000);
    };

    ws.onerror = () => {
      // Fallback polling every 4s
    };

    const pollingInterval = setInterval(async () => {
      if (!socketRef.current || socketRef.current.readyState !== WebSocket.OPEN) {
        try {
          const res = await fetch(`/api/ceremony/heartbeat/${encodeURIComponent(activeToken)}`, { method: 'POST' });
          if (res.ok) {
            const data = await res.json();
            setCeremonyState(data);
          }
        } catch (_) {}
      }
    }, 4000);

    return () => {
      clearInterval(pollingInterval);
      if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        ws.close();
      }
    };
  }, [activeToken, fetchInfo]);

  // Load validation summary if unlocked
  useEffect(() => {
    if (ceremonyState?.status === 'UNLOCKED' || ceremonyState?.status === 'COMPLETED' || electionInfo?.is_unlocked) {
      fetchValidationSummary();
    }
  }, [ceremonyState?.status, electionInfo?.is_unlocked]);

  const fetchValidationSummary = async () => {
    if (!activeToken) return;
    try {
      const res = await fetch(`/api/ceremony/validation/summary/${encodeURIComponent(activeToken)}`);
      const data = await res.json().catch(() => ({}));
      if (res.ok) {
        setValidationSummary(data);
        setSummaryError(null);
      } else {
        setSummaryError(data.detail || 'Could not load the decrypted tally.');
      }
    } catch (e) {
      console.error(e);
      setSummaryError('Could not load the decrypted tally.');
    }
  };

  const handleSubmitCode = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputCode.trim() || !activeToken) return;

    setIsSubmittingCode(true);
    setSubmissionError(null);

    try {
      const res = await fetch(`/api/ceremony/submit-code/${encodeURIComponent(activeToken)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: inputCode.trim() }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Code entry failed.');
      }
      setInputCode('');
      if (data.is_unlocked) {
        setElectionInfo((prev) => (prev ? { ...prev, is_unlocked: true } : prev));
        setCeremonyState((prev) => (prev ? { ...prev, status: 'UNLOCKED' } : prev));
      }
    } catch (err: any) {
      setSubmissionError(err.message || 'Submission error');
    } finally {
      setIsSubmittingCode(false);
    }
  };

  const handleApprove = async () => {
    if (!activeToken) return;
    setIsApproving(true);
    try {
      const res = await fetch(`/api/ceremony/validation/approve/${encodeURIComponent(activeToken)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });

      const data = await res.json();
      if (res.ok) {
        setApprovalMessage(
          data.all_approved
            ? 'Every trustee approved. These results are now published to voters.'
            : (data.message || 'Your approval is recorded. Voters will see the results after every trustee agrees.')
        );
        fetchValidationSummary();
      } else {
        throw new Error(data.detail || 'Approval failed.');
      }
    } catch (err: any) {
      alert(err.message || 'Approval failed');
    } finally {
      setIsApproving(false);
    }
  };

  const handleDownloadExport = async () => {
    if (!activeToken) return;
    window.open(`/api/ceremony/bulletin-board-export/${encodeURIComponent(activeToken)}`, '_blank');
  };

  const handlePasteSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPasteError(null);
    const raw = pastedInput.trim();
    if (!raw) {
      setPasteError('Please enter your ceremony link or link token.');
      return;
    }
    // Extract token if a full URL or path was pasted
    let tokenCandidate = raw;
    if (raw.includes('/ceremony/')) {
      const parts = raw.split('/ceremony/');
      tokenCandidate = parts[parts.length - 1].split('?')[0].split('#')[0].trim();
    }
    if (!tokenCandidate) {
      setPasteError('Invalid ceremony link or token format.');
      return;
    }
    if (navigateTo) {
      navigateTo(`/ceremony/${encodeURIComponent(tokenCandidate)}`);
    } else {
      window.history.pushState(null, '', `/ceremony/${encodeURIComponent(tokenCandidate)}`);
      setActiveToken(tokenCandidate);
    }
  };

  // If no token provided yet, render the quiet entry portal
  if (!activeToken) {
    return (
      <div className="min-h-screen bg-ink text-on-ink flex flex-col justify-between select-none">
        <header className="border-b border-ink-3 bg-ink-2 px-6 py-4">
          <div className="max-w-6xl mx-auto flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="w-2.5 h-2.5 rounded-full bg-accent" />
              <div>
                <span className="font-display text-lg font-bold text-white tracking-tight">{APP_NAME}</span>
                <span className="text-[10px] font-mono uppercase bg-ink text-on-ink/60 px-2 py-0.5 rounded border border-ink-3 ml-2">
                  Trustee Entry Portal
                </span>
              </div>
            </div>
            {navigateTo && (
              <button
                onClick={() => navigateTo('/')}
                className="text-xs font-mono text-on-ink/60 hover:text-white transition"
              >
                &larr; Back to Home
              </button>
            )}
          </div>
        </header>

        <main className="max-w-md w-full mx-auto p-6 my-auto">
          <div className="bg-ink-2 border border-ink-3 rounded-xl p-8 shadow-2xl">
            <div className="w-12 h-12 bg-ink border border-ink-3 rounded-full flex items-center justify-center mx-auto mb-4 text-accent">
              <KeyRound className="w-6 h-6" />
            </div>
            <h2 className="font-display text-xl font-bold text-white mb-2 text-center">Trustee Access</h2>
            <p className="text-xs text-on-ink/70 leading-relaxed mb-6 text-center">
              Paste the ceremony link or private access token from your invitation email to enter your election ceremony room.
            </p>

            {pasteError && (
              <div className="mb-4 p-3 rounded bg-red-950/80 border border-red-800 text-red-200 text-xs flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0" />
                <span>{pasteError}</span>
              </div>
            )}

            <form onSubmit={handlePasteSubmit} className="space-y-4">
              <div>
                <label className="text-[11px] font-mono uppercase text-on-ink/50 block mb-1">
                  Ceremony Link or Access Token
                </label>
                <input
                  type="text"
                  value={pastedInput}
                  onChange={(e) => setPastedInput(e.target.value)}
                  placeholder="https://.../ceremony/TOKEN or raw token"
                  className="w-full px-4 py-3 bg-ink text-white border border-ink-3 rounded-lg font-mono text-xs focus:outline-none focus:border-on-ink placeholder:text-on-ink/30"
                  autoFocus
                />
              </div>

              <button
                type="submit"
                className="w-full py-3 px-6 bg-on-ink text-ink font-semibold rounded-lg text-xs hover:bg-white transition flex items-center justify-center gap-2"
              >
                <span>Enter Ceremony</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </form>
          </div>
        </main>

        <footer className="w-full px-6 py-4 border-t border-ink-3 text-center text-xs text-on-ink/40 font-mono">
          Threshold Trustees Only &bull; Access link issued via private notification
        </footer>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-ink text-on-ink flex items-center justify-center p-6 font-mono text-xs">
        <div className="flex items-center gap-3">
          <RefreshCw className="w-5 h-5 animate-spin text-accent" />
          <span>Connecting to cryptographic ceremony secure channel...</span>
        </div>
      </div>
    );
  }

  if (error || !electionInfo) {
    return (
      <div className="min-h-screen bg-ink text-on-ink flex items-center justify-center p-6">
        <div className="max-w-md w-full bg-ink-2 border border-red-800 rounded-xl p-8 text-center">
          <AlertCircle className="w-10 h-10 text-red-400 mx-auto mb-3" />
          <h2 className="font-display text-xl font-bold text-white mb-2">Access Denied</h2>
          <p className="text-xs text-on-ink/70 leading-relaxed mb-4">{error}</p>
          <span className="text-[11px] font-mono text-on-ink/40">
            Please verify your private link token from your official invitation email.
          </span>
        </div>
      </div>
    );
  }

  const isUnlocked = ceremonyState?.status === 'UNLOCKED' || ceremonyState?.status === 'COMPLETED' || electionInfo.is_unlocked;
  const isYourTurn = ceremonyState?.next_expected_position === electionInfo.your_position;
  const isVotingClosed = electionInfo.is_voting_closed;
  const allPresent = ceremonyState?.all_present || false;

  return (
    <div className="min-h-screen bg-ink text-on-ink flex flex-col justify-between select-none">
      {/* CEREMONY TOP HEADER */}
      <header className="border-b border-ink-3 bg-ink-2 px-6 py-4">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className="w-2.5 h-2.5 rounded-full bg-accent animate-pulse" />
            <div>
              <div className="flex items-center gap-2">
                <span className="font-display text-lg font-bold text-white tracking-tight">{APP_NAME}</span>
                <span className="text-[10px] font-mono uppercase bg-ink text-on-ink/60 px-2 py-0.5 rounded border border-ink-3">
                  All-Trustees Unlock Ceremony
                </span>
              </div>
              <span className="text-xs text-on-ink/60 font-mono truncate block">{electionInfo.election_title}</span>
            </div>
          </div>

          <div className="flex items-center gap-4 text-xs font-mono">
            <div className="bg-ink px-3 py-1.5 rounded border border-ink-3 flex items-center gap-2">
              <span className="text-on-ink/50">Your Slot:</span>
              <span className="text-white font-semibold">
                Trustee #{electionInfo.your_position} ({electionInfo.your_name})
              </span>
            </div>
            <div className="bg-ink px-3 py-1.5 rounded border border-ink-3 flex items-center gap-2">
              <Users className="w-3.5 h-3.5 text-on-ink/50" />
              <span className="text-white">
                {ceremonyState?.present_count || 1} / {electionInfo.total_trustees} Present
              </span>
            </div>
          </div>
        </div>
      </header>

      {/* MAIN CEREMONY CONTENT */}
      <main className="max-w-6xl w-full mx-auto p-6 flex-1 flex flex-col justify-center">
        {!isVotingClosed ? (
          /* STATE 1: VOTING IS NOT CLOSED YET */
          <div className="max-w-xl mx-auto bg-ink-2 border border-ink-3 rounded-xl p-8 text-center my-8 shadow-2xl">
            <div className="w-12 h-12 bg-amber-950/60 border border-amber-800 rounded-full flex items-center justify-center mx-auto mb-4 text-amber-400">
              <Lock className="w-6 h-6" />
            </div>
            <h2 className="font-display text-2xl font-bold text-white mb-2">Validation Not Open Yet</h2>
            <p className="text-xs text-on-ink/70 leading-relaxed max-w-md mx-auto mb-6">
              Voting is currently active. The All-Trustees Unlock Ceremony will become active once an administrator officially closes the ballot box.
            </p>
            {electionInfo.scheduled_close && (
              <div className="bg-ink p-3.5 rounded border border-ink-3 font-mono text-xs text-on-ink/80 inline-block">
                Scheduled Close: <span className="text-white font-semibold">{new Date(electionInfo.scheduled_close).toLocaleString()}</span>
              </div>
            )}
          </div>
        ) : !isUnlocked ? (
          /* STATE 2: ACTIVE CEREMONY UNLOCK PROTOCOL */
          <div className="space-y-8 my-6">
            {/* Countdown & Protocol Status Banner */}
            <div className="bg-ink-2 border border-ink-3 rounded-xl p-6 flex flex-col sm:flex-row items-center justify-between gap-4">
              <div>
                <span className="text-[10px] font-mono uppercase tracking-widest text-on-ink/50 block mb-1">
                  Ceremony Protocol Status
                </span>
                <h3 className="font-display text-xl font-bold text-white flex items-center gap-2">
                  {ceremonyState?.status === 'IN_PROGRESS' ? (
                    <>
                      <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-ping" />
                      Active Round in Progress
                    </>
                  ) : allPresent ? (
                    'All Trustees Connected — Ready for Sequential Entry'
                  ) : (
                    `Waiting for All ${electionInfo.total_trustees} Trustees (${ceremonyState?.present_count}/${electionInfo.total_trustees} online)`
                  )}
                </h3>
              </div>

              {ceremonyState?.status === 'IN_PROGRESS' && (
                <div className="bg-ink px-4 py-2.5 rounded-lg border border-ink-3 flex items-center gap-3 font-mono">
                  <Clock className="w-4 h-4 text-accent animate-spin" />
                  <div>
                    <span className="text-[10px] text-on-ink/50 uppercase block">Round Window Timer</span>
                    <span className="text-base font-bold text-white">
                      {Math.floor((ceremonyState.remaining_seconds || 0) / 60)}:
                      {((ceremonyState.remaining_seconds || 0) % 60).toString().padStart(2, '0')}
                    </span>
                  </div>
                </div>
              )}
            </div>

            {/* Reset / Error Banner */}
            {ceremonyState?.reset_reason && (
              <div className="p-4 rounded-lg bg-red-950/80 border border-red-800 text-red-200 text-xs flex items-center gap-3">
                <RotateCcw className="w-4 h-4 text-red-400 flex-shrink-0" />
                <span>
                  <strong>Round Reset:</strong> {ceremonyState.reset_reason}
                </span>
              </div>
            )}

            {/* N-OF-N SLOTS ROW */}
            <div>
              <div className="flex items-center justify-between mb-3 text-xs font-mono text-on-ink/50">
                <span>Ordered Passphrase Parts (Positions 1 to {electionInfo.total_trustees})</span>
                <span>N-of-N Unlock Rule Enforced</span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 lg:grid-cols-5 gap-3">
                {ceremonyState?.slots.map((slot) => {
                  const isAccepted = slot.is_accepted;
                  const isPresent = slot.is_present;
                  const isYou = slot.is_you;
                  const isNext = ceremonyState.next_expected_position === slot.position;

                  return (
                    <div
                      key={slot.position}
                      className={`p-4 rounded-lg border transition relative flex flex-col justify-between min-h-[140px] ${
                        isAccepted
                          ? 'bg-emerald-950/40 border-emerald-700/80 text-emerald-200'
                          : isYou
                          ? 'bg-ink-2 border-accent text-white shadow-lg'
                          : isNext
                          ? 'bg-ink-2 border-on-ink/40 text-on-ink'
                          : 'bg-ink-2/60 border-ink-3 text-on-ink/50'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-mono text-xs font-bold px-2 py-0.5 rounded bg-ink border border-ink-3">
                          Part #{slot.position}
                        </span>
                        <div className="flex items-center gap-1.5">
                          <span
                            className={`w-2 h-2 rounded-full ${
                              isPresent ? 'bg-emerald-400' : 'bg-red-500'
                            }`}
                            title={isPresent ? 'Online & Active' : 'Offline / Absent'}
                          />
                          <span className="text-[10px] font-mono uppercase text-on-ink/60">
                            {isPresent ? 'Online' : 'Waiting'}
                          </span>
                        </div>
                      </div>

                      <div className="my-2">
                        <span className="text-xs font-semibold block truncate">{slot.name}</span>
                        {isYou && (
                          <span className="text-[10px] font-mono text-accent uppercase font-bold">
                            &bull; This is your slot
                          </span>
                        )}
                      </div>

                      <div className="pt-2 border-t border-ink-3/50 text-right">
                        {isAccepted ? (
                          <span className="text-[11px] font-mono text-emerald-400 font-semibold flex items-center justify-end gap-1">
                            <CheckCircle2 className="w-3.5 h-3.5" /> Accepted
                          </span>
                        ) : slot.is_locked ? (
                          <span className="text-[10px] font-mono text-red-400">
                            Locked ({slot.lockout_remaining_seconds}s)
                          </span>
                        ) : isNext ? (
                          <span className="text-[10px] font-mono text-accent animate-pulse font-semibold">
                            &rarr; Awaiting Entry
                          </span>
                        ) : (
                          <span className="text-[10px] font-mono text-on-ink/30">Pending Order</span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* TRUSTEE CODE ENTRY FORM */}
            <div className="bg-ink-2 border border-ink-3 rounded-xl p-6 sm:p-8 max-w-xl mx-auto shadow-2xl">
              <div className="flex items-center gap-2 mb-2">
                <KeyRound className="w-4 h-4 text-accent" />
                <span className="font-display text-base font-bold text-white">
                  Enter Your Secret Code (Part #{electionInfo.your_position})
                </span>
              </div>
              <p className="text-xs text-on-ink/70 mb-6 leading-relaxed">
                Paste the 16-character Crockford-32 code received in your private invitation email.
              </p>

              {submissionError && (
                <div className="mb-4 p-3 rounded bg-red-950/80 border border-red-800 text-red-200 text-xs flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0" />
                  <span>{submissionError}</span>
                </div>
              )}

              <form onSubmit={handleSubmitCode} className="space-y-4">
                <div>
                  <input
                    type="text"
                    value={inputCode}
                    onChange={(e) => setInputCode(e.target.value)}
                    placeholder={`e.g. T${electionInfo.your_position}-XXXX-XXXX-XXXX-XXXX-X`}
                    disabled={!allPresent || !isYourTurn || isSubmittingCode}
                    className="w-full px-4 py-3 bg-ink text-white border border-ink-3 rounded-lg font-mono text-sm tracking-wider uppercase focus:outline-none focus:border-on-ink placeholder:text-on-ink/30 disabled:opacity-40"
                  />
                </div>

                <div>
                  <button
                    type="submit"
                    disabled={!allPresent || !isYourTurn || isSubmittingCode || !inputCode.trim()}
                    className="w-full py-3 px-6 bg-on-ink text-ink font-semibold rounded-lg text-xs hover:bg-white transition flex items-center justify-center gap-2 disabled:opacity-40"
                  >
                    {isSubmittingCode ? (
                      <>
                        <RefreshCw className="w-3.5 h-3.5 animate-spin" /> Verifying Code & Decrypting Share...
                      </>
                    ) : (
                      <>
                        Submit Part #{electionInfo.your_position} & Unlock Next <ArrowRight className="w-3.5 h-3.5" />
                      </>
                    )}
                  </button>
                </div>

                {!allPresent && (
                  <p className="text-[11px] font-mono text-amber-400 text-center">
                    Submission disabled: All {electionInfo.total_trustees} trustees must be online simultaneously.
                  </p>
                )}
                {allPresent && !isYourTurn && (
                  <p className="text-[11px] font-mono text-on-ink/50 text-center">
                    Sequential gate: Trustee #{ceremonyState?.next_expected_position} must submit their code first.
                  </p>
                )}
              </form>
            </div>
          </div>
        ) : (
          /* STATE 3: UNLOCKED — VALIDATION CONSOLE */
          <div className="space-y-8 my-6">
            <div className="bg-ink-2 border border-emerald-700/60 rounded-xl p-6 sm:p-8 flex flex-col sm:flex-row items-center justify-between gap-4 shadow-2xl">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <Unlock className="w-4 h-4 text-emerald-400" />
                  <span className="text-[10px] font-mono uppercase tracking-widest text-emerald-400 font-bold">
                    Ceremony Unlocked
                  </span>
                </div>
                <h2 className="font-display text-2xl font-bold text-white">Trustee Validation Console</h2>
                <p className="text-xs text-on-ink/70 mt-1">
                  Threshold private key shares have been decrypted into secure memory. Run independent cryptographic verification and submit your partial decryption.
                </p>
              </div>

              <button
                type="button"
                onClick={handleDownloadExport}
                className="py-2.5 px-4 bg-ink border border-ink-3 rounded text-xs text-on-ink font-mono hover:bg-ink-3 transition flex items-center gap-2"
              >
                <Download className="w-3.5 h-3.5" /> Export Bulletin Board (.json)
              </button>
            </div>

            {/* Summary Metrics */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="bg-ink-2 border border-ink-3 rounded-lg p-5">
                <span className="text-[10px] font-mono uppercase text-on-ink/50 block mb-1">Ballots Cast</span>
                <span className="font-display text-2xl font-bold text-white">
                  {validationSummary?.total_ballots ?? 0}
                </span>
              </div>

              <div className="bg-ink-2 border border-ink-3 rounded-lg p-5">
                <span className="text-[10px] font-mono uppercase text-on-ink/50 block mb-1">Bulletin Board Head Hash</span>
                <p className="text-xs font-mono text-on-ink truncate bg-ink p-1.5 rounded border border-ink-3 mt-1" title={validationSummary?.head_hash}>
                  {validationSummary?.head_hash || '0x00000000000000000000000000000000'}
                </p>
              </div>

              <div className="bg-ink-2 border border-ink-3 rounded-lg p-5">
                <span className="text-[10px] font-mono uppercase text-on-ink/50 block mb-1">Governance Approvals</span>
                <span className="font-display text-2xl font-bold text-white">
                  {validationSummary?.approvals?.filter((a: any) => a.has_approved).length ?? 0} / {electionInfo.total_trustees}
                </span>
              </div>
            </div>

            {/* ELECTION TALLY REVIEW (FOR TRUSTEES TO AUDIT & SAY OKAY) */}
            <div className="bg-ink-2 border border-purple-800/60 rounded-xl p-6 shadow-xl">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4 border-b border-ink-3 pb-4">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <BarChart3 className="w-4 h-4 text-purple-400" />
                    <span className="text-[10px] font-mono uppercase tracking-widest text-purple-300 font-bold">
                      Decrypted Tally Audit (Trustee Preview)
                    </span>
                  </div>
                  <h3 className="font-display text-lg font-bold text-white">
                    Candidate Voting Results
                  </h3>
                  <p className="text-xs text-on-ink/70 mt-1">
                    These totals are visible to trustees and the administrator now. Voters see them only after every trustee approves.
                  </p>
                </div>

                <div className="text-left sm:text-right flex-shrink-0">
                  <span className="text-[10px] font-mono uppercase text-on-ink/50 block">Your Certification Status</span>
                  <span className={`text-xs font-mono font-bold px-2.5 py-1 rounded border inline-block mt-0.5 ${
                    validationSummary?.has_approved
                      ? 'bg-emerald-950 text-emerald-300 border-emerald-800'
                      : 'bg-amber-950 text-amber-300 border-amber-800'
                  }`}>
                    {validationSummary?.has_approved ? '✓ CERTIFIED BY YOU' : '⏳ AWAITING YOUR APPROVAL'}
                  </span>
                </div>
              </div>

              {validationSummary?.results_published && (
                <div className="mb-4 p-3 rounded bg-emerald-950/80 border border-emerald-800 text-emerald-200 text-xs">
                  Every trustee has approved. Voters can now see these results.
                </div>
              )}

              {summaryError && (
                <div className="mb-4 p-3 rounded bg-red-950/80 border border-red-800 text-red-200 text-xs">
                  {summaryError}
                </div>
              )}

              {validationSummary?.results && Object.keys(validationSummary.results).length > 0 ? (
                (() => {
                  const entries = Object.entries(validationSummary.results);
                  const maxVotes = Math.max(...entries.map(([_, count]: [string, any]) => Number(count) || 0), 0);
                  const total = validationSummary.total_ballots || entries.reduce((acc, [_, v]) => acc + Number(v), 0) || 1;

                  return (
                    <div className="space-y-3">
                      {entries.map(([candidate, count]: [string, any]) => {
                        const cCount = Number(count) || 0;
                        const pct = ((cCount / total) * 100).toFixed(1);
                        const isLeader = cCount === maxVotes && maxVotes > 0;

                        return (
                          <div key={candidate} className="p-3.5 bg-ink rounded-lg border border-ink-3">
                            <div className="flex items-center justify-between text-xs font-mono mb-2">
                              <div className="flex items-center gap-2">
                                <span className="font-bold text-white text-sm">{candidate}</span>
                                {isLeader && (
                                  <span className="inline-flex items-center gap-1 text-[10px] uppercase font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40 px-2 py-0.5 rounded-full">
                                    <Trophy className="w-3 h-3 text-amber-400" />
                                    Current Leader / Winner
                                  </span>
                                )}
                              </div>
                              <div className="text-right">
                                <span className="text-sm font-bold text-white">{cCount} {cCount === 1 ? 'vote' : 'votes'}</span>
                                <span className="text-on-ink/50 ml-2">({pct}%)</span>
                              </div>
                            </div>
                            <div className="w-full h-2 bg-ink-3 rounded-full overflow-hidden">
                              <div
                                className={`h-full transition-all duration-500 ${isLeader ? 'bg-amber-400' : 'bg-purple-500'}`}
                                style={{ width: `${pct}%` }}
                              />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  );
                })()
              ) : (
                <div className="p-4 bg-ink rounded text-center text-xs font-mono text-on-ink/50">
                  {validationSummary ? 'No votes recorded yet.' : 'Loading decrypted totals...'}
                </div>
              )}
            </div>

            {/* APPROVE AND SUBMIT PARTIAL DECRYPTION */}
            <div className="bg-ink-2 border border-ink-3 rounded-xl p-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4">
                <div>
                  <h3 className="font-display text-base font-bold text-white mb-1">
                    Approve Election & Compute Partial Decryptions
                  </h3>
                  <p className="text-xs text-on-ink/60">
                    Approving certifies the totals above. Once every trustee agrees, the same totals are published to voters. The administrator can already see them.
                  </p>
                </div>

                {!validationSummary?.has_approved ? (
                  <button
                    type="button"
                    onClick={handleApprove}
                    disabled={isApproving}
                    className="py-2.5 px-6 bg-emerald-600 text-white font-semibold rounded text-xs hover:bg-emerald-500 transition flex items-center gap-2"
                  >
                    <ShieldCheck className="w-4 h-4" />
                    {isApproving ? 'Submitting DLEQ Proofs...' : 'Approve & Submit Partial Decryption'}
                  </button>
                ) : (
                  <span className="py-2 px-4 rounded bg-emerald-950 text-emerald-300 border border-emerald-800 text-xs font-mono flex items-center gap-1.5">
                    <CheckCircle2 className="w-4 h-4" /> You Have Approved (Share Wiped)
                  </span>
                )}
              </div>

              {approvalMessage && (
                <div className="p-3 bg-emerald-950/80 border border-emerald-800 text-emerald-200 text-xs rounded">
                  {approvalMessage}
                </div>
              )}
            </div>
          </div>
        )}
      </main>

      {/* FOOTER */}
      <footer className="border-t border-ink-3 bg-ink-2 px-6 py-4 text-center text-xs font-mono text-on-ink/40">
        {APP_NAME} Institutional Cryptographic Threshold Voting Protocol &bull; Zero-Knowledge Decryption Ceremony
      </footer>
    </div>
  );
};
export default CeremonyPage;

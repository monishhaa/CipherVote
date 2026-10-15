import React, { useState, useEffect, useMemo } from 'react';
import {
  ArrowRight,
  ShieldCheck,
  Bell,
  ExternalLink,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  Clock,
  ChevronDown,
  ChevronUp,
  FileCheck,
  Vote,
  BarChart3,
  Trophy,
} from 'lucide-react';
import { APP_NAME } from '../constants';

interface VoterOverviewProps {
  navigateTo: (path: string) => void;
  electionId?: string;
  electionTitle?: string;
  isOpen?: boolean;
  electionStatus?: string;
}

interface MyElectionItem {
  election_id: string;
  title: string;
  status: string;
  is_open: boolean;
  scheduled_start?: string | null;
  scheduled_end?: string | null;
  timezone?: string;
  scheduled_window: string;
  results_published: boolean;
  progress: {
    registered: boolean;
    registered_at?: string | null;
    credential_delivered: boolean;
    delivery_status: string;
    token_issued: boolean;
    ballot_cast: boolean;
    receipt_code?: string | null;
    results_published: boolean;
  };
}

export const VoterOverview: React.FC<VoterOverviewProps> = ({
  navigateTo,
  electionId: propElectionId = '',
}) => {
  const token = sessionStorage.getItem('voter_session_token');
  const voterId = sessionStorage.getItem('voter_id');

  const [myElections, setMyElections] = useState<MyElectionItem[]>([]);
  const [selectedElectionId, setSelectedElectionId] = useState<string>(
    () => propElectionId || sessionStorage.getItem('voter_election_id') || ''
  );
  const [electionData, setElectionData] = useState<any>(null);
  const [voterMe, setVoterMe] = useState<any>(null);
  const [notifications, setNotifications] = useState<any[]>([]);
  const [tallyResults, setTallyResults] = useState<any | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isProtectedExpanded, setIsProtectedExpanded] = useState<boolean>(false);

  // Reissue modal state
  const [showReissueModal, setShowReissueModal] = useState<boolean>(false);
  const [reissuePassword, setReissuePassword] = useState<string>('');
  const [isReissuing, setIsReissuing] = useState<boolean>(false);
  const [reissueMsg, setReissueMsg] = useState<string | null>(null);
  const [reissueError, setReissueError] = useState<string | null>(null);

  // Sync propElectionId
  useEffect(() => {
    if (propElectionId && propElectionId !== selectedElectionId) {
      setSelectedElectionId(propElectionId);
    }
  }, [propElectionId]);

  // Fetch my registered elections
  useEffect(() => {
    if (!token) {
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    fetch('/api/voter/my-elections', {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data && data.elections) {
          setMyElections(data.elections);
          if (!selectedElectionId && data.elections.length > 0) {
            setSelectedElectionId(data.elections[0].election_id);
            sessionStorage.setItem('voter_election_id', data.elections[0].election_id);
          }
        }
      })
      .catch(() => {})
      .finally(() => setIsLoading(false));
  }, [token]);

  const activeElectionId = selectedElectionId || (myElections.length > 0 ? myElections[0].election_id : '');
  const activeMyElection = myElections.find((e) => e.election_id === activeElectionId) || (myElections.length > 0 ? myElections[0] : null);

  // Fetch live election details and voter me
  useEffect(() => {
    if (!activeElectionId) return;

    // Public election status
    fetch(`/api/public/status?election_id=${encodeURIComponent(activeElectionId)}`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data) setElectionData(data);
      })
      .catch(() => {});

    // Voter profile
    if (token) {
      fetch(`/api/voter/me?election_id=${encodeURIComponent(activeElectionId)}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
        .then((res) => (res.ok ? res.json() : null))
        .then((data) => {
          if (data) setVoterMe(data);
        })
        .catch(() => {});

      // Recent notifications (last 5)
      fetch(`/api/voter/notifications?election_id=${encodeURIComponent(activeElectionId)}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
        .then((res) => (res.ok ? res.json() : null))
        .then((data) => {
          if (data && data.notifications) {
            setNotifications(data.notifications.slice(0, 5));
          }
        })
        .catch(() => {});

      // Results if completed
      fetch(`/api/public/results?election_id=${encodeURIComponent(activeElectionId)}`)
        .then((res) => (res.ok ? res.json() : null))
        .then((data) => {
          if (data && data.published) {
            setTallyResults(data);
          } else {
            setTallyResults(null);
          }
        })
        .catch(() => {});
    }
  }, [token, activeElectionId]);

  // Reissue credential handler
  const handleReissueCredential = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reissuePassword.trim()) return;

    setIsReissuing(true);
    setReissueError(null);
    setReissueMsg(null);

    try {
      const res = await fetch('/api/voter/reissue-credential', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          voter_id: voterId,
          password: reissuePassword,
          election_id: activeElectionId,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail?.message || data.detail || 'Reissue request failed.');
      }

      setReissueMsg(data.message || 'A new credential was successfully generated and dispatched to your email.');
      setTimeout(() => setShowReissueModal(false), 2500);
    } catch (err: any) {
      setReissueError(err.message || 'Failed to reissue credential.');
    } finally {
      setIsReissuing(false);
    }
  };

  // State derivation
  const title = activeMyElection?.title || electionData?.title || activeElectionId || 'Official Election';
  const status = electionData?.status || activeMyElection?.status || 'REGISTRATION';
  const hasVoted = Boolean(voterMe?.token_issued || activeMyElection?.progress?.ballot_cast);
  const resultsPublished = Boolean(electionData?.results_published_at || activeMyElection?.results_published || tallyResults?.published);

  // Check stored receipt
  const storedReceipt = useMemo(() => {
    if (!voterId || !activeElectionId) return null;
    return sessionStorage.getItem(`securevote_receipt_${voterId}_${activeElectionId}`) ||
           localStorage.getItem(`securevote_receipt_${voterId}_${activeElectionId}`);
  }, [voterId, activeElectionId]);

  // Plain-English sentence of where the voter stands
  const statusHeadline = useMemo(() => {
    if (resultsPublished) {
      return 'Results are published.';
    }
    if (hasVoted) {
      return storedReceipt ? `You voted. Receipt ${storedReceipt}` : 'You voted. Your ballot is sealed and audited on the bulletin board.';
    }
    if (status === 'OPEN') {
      return electionData?.formatted_window
        ? `Voting is open until ${electionData.scheduled_end ? new Date(electionData.scheduled_end).toLocaleString() : 'closing'}.`
        : 'Voting is currently open.';
    }
    if (status === 'CLOSED' || status === 'TALLYING') {
      return 'Voting has closed. Results will be published after the trustees validate them.';
    }
    if (status === 'REGISTRATION') {
      return electionData?.scheduled_start
        ? `Voting opens on ${new Date(electionData.scheduled_start).toLocaleString()} (${electionData.timezone || 'UTC'}).`
        : 'Registration is open. Voting dates will be announced by the election committee.';
    }
    return `Status: ${status}`;
  }, [status, hasVoted, resultsPublished, storedReceipt, electionData]);

  // UN-AUTHENTICATED STATE: Clean gateway prompt
  if (!token || !voterId) {
    return (
      <div className="min-h-[calc(100vh-4rem)] bg-paper flex items-center justify-center p-4">
        <div className="max-w-md w-full p-8 bg-paper-2 border border-line rounded-xl text-center shadow-sm">
          <div className="w-12 h-12 rounded-full bg-paper border border-line flex items-center justify-center mx-auto mb-4 text-accent">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <h1 className="font-display text-2xl font-bold text-ink mb-2">Sign in to see your elections</h1>
          <p className="text-xs text-ink/70 mb-6 leading-relaxed">
            Enter your official Voter ID and account password to view your active election registrations, credentials, and voting progress.
          </p>
          <div className="flex flex-col sm:flex-row gap-3">
            <button
              type="button"
              onClick={() => navigateTo('/user/login')}
              className="flex-1 py-2.5 px-4 bg-primary text-white text-xs font-semibold font-mono uppercase tracking-wider rounded hover:bg-primary/90 transition"
            >
              Sign In
            </button>
            <button
              type="button"
              onClick={() => navigateTo('/user/register')}
              className="flex-1 py-2.5 px-4 bg-paper border border-line text-ink text-xs font-semibold font-mono uppercase tracking-wider rounded hover:bg-paper-2 transition"
            >
              Register
            </button>
          </div>
        </div>
      </div>
    );
  }

  // AUTHENTICATED STATE: Detailed election dashboard
  if (isLoading) {
    return (
      <div className="min-h-[calc(100vh-4rem)] bg-paper flex items-center justify-center p-8">
        <div className="flex items-center gap-2 text-xs font-mono text-ink/50">
          <RefreshCw className="w-4 h-4 animate-spin text-accent" />
          <span>Loading election status...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-[calc(100vh-4rem)] bg-paper py-8 px-4 sm:px-6 lg:px-8 max-w-5xl mx-auto space-y-8">
      {/* 1. STATUS HEADER */}
      <div className="border-b border-line pb-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-2">
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-mono uppercase tracking-wider text-ink/50">Personal Election Status</span>
            <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase border ${
              status === 'OPEN'
                ? 'bg-emerald-50 text-emerald-700 border-emerald-300'
                : status === 'CLOSED'
                ? 'bg-blue-50 text-blue-700 border-blue-300'
                : 'bg-paper-2 text-ink/70 border-line'
            }`}>
              {status}
            </span>
          </div>
        </div>

        <h1 className="font-display text-2xl sm:text-4xl font-bold text-ink tracking-tight mb-2">
          {title}
        </h1>

        <p className="text-base text-ink/80 font-medium">
          {statusHeadline}
        </p>

        {/* Primary Action Button */}
        <div className="mt-6 flex flex-wrap items-center gap-3">
          {status === 'OPEN' && !hasVoted && (
            <button
              type="button"
              onClick={() => navigateTo(`/user/e/${activeElectionId}/vote`)}
              className="py-3 px-6 bg-primary text-white text-xs font-mono uppercase font-semibold tracking-wider rounded hover:bg-primary/90 transition shadow-sm flex items-center gap-2"
            >
              <span>Cast your ballot</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          )}

          {hasVoted && (
            <button
              type="button"
              onClick={() => navigateTo(`/user/e/${activeElectionId}/vote`)}
              className="py-3 px-5 bg-emerald-600 text-white text-xs font-mono uppercase font-semibold tracking-wider rounded hover:bg-emerald-500 transition shadow-sm flex items-center gap-2"
            >
              <FileCheck className="w-4 h-4" />
              <span>View my receipt</span>
            </button>
          )}

          {status === 'REGISTRATION' && (
            <button
              type="button"
              disabled
              className="py-3 px-5 bg-paper-2 border border-line text-ink/60 text-xs font-mono uppercase font-medium rounded cursor-not-allowed flex items-center gap-2"
            >
              <Clock className="w-4 h-4 text-accent" />
              <span>{electionData?.formatted_window || 'Voting window to be announced'}</span>
            </button>
          )}

          {resultsPublished && (
            <button
              type="button"
              onClick={() => {
                const el = document.getElementById('results-section');
                el?.scrollIntoView({ behavior: 'smooth' });
              }}
              className="py-3 px-5 bg-purple-700 text-white text-xs font-mono uppercase font-semibold tracking-wider rounded hover:bg-purple-600 transition flex items-center gap-2"
            >
              <BarChart3 className="w-4 h-4" />
              <span>View Results</span>
            </button>
          )}

          <button
            type="button"
            onClick={() => navigateTo(`/user/e/${activeElectionId}/audit`)}
            className="py-3 px-4 bg-paper border border-line text-ink/80 text-xs font-mono uppercase rounded hover:bg-paper-2 transition flex items-center gap-2"
          >
            <ExternalLink className="w-3.5 h-3.5 text-ink/60" />
            <span>Bulletin Board</span>
          </button>
        </div>
      </div>

      {/* 4. MY ELECTIONS TABLE (Shown if voter is registered in several elections) */}
      {myElections.length > 1 && (
        <div className="bg-paper-2 border border-line rounded-xl p-5 shadow-xs">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-display text-sm font-bold text-ink uppercase tracking-wider">My Registered Elections ({myElections.length})</h3>
            <span className="text-[11px] font-mono text-ink/50">Click an election to view status</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="border-b border-line text-[11px] text-ink/50 uppercase">
                  <th className="py-2 pr-4 font-medium">Election</th>
                  <th className="py-2 px-4 font-medium">Status</th>
                  <th className="py-2 px-4 font-medium">My Progress</th>
                  <th className="py-2 pl-4 text-right font-medium">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {myElections.map((item) => {
                  const isCurrent = item.election_id === activeElectionId;
                  const voted = item.progress.ballot_cast;
                  return (
                    <tr key={item.election_id} className={`hover:bg-paper/50 transition ${isCurrent ? 'bg-accent/5' : ''}`}>
                      <td className="py-3 pr-4 font-medium text-ink">
                        <div className="flex items-center gap-1.5">
                          {isCurrent && <span className="w-1.5 h-1.5 rounded-full bg-accent" />}
                          <span>{item.title}</span>
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase border ${
                          item.status === 'OPEN'
                            ? 'bg-emerald-50 text-emerald-700 border-emerald-300'
                            : item.status === 'CLOSED'
                            ? 'bg-blue-50 text-blue-700 border-blue-300'
                            : 'bg-paper text-ink/70 border-line'
                        }`}>
                          {item.status}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-ink/70">
                        {voted ? (
                          <span className="text-emerald-700 font-semibold flex items-center gap-1">
                            <CheckCircle2 className="w-3.5 h-3.5" /> Ballot Cast
                          </span>
                        ) : item.status === 'OPEN' ? (
                          <span className="text-accent font-semibold">Ready to Vote</span>
                        ) : (
                          <span>Registered</span>
                        )}
                      </td>
                      <td className="py-3 pl-4 text-right">
                        <button
                          type="button"
                          onClick={() => {
                            setSelectedElectionId(item.election_id);
                            sessionStorage.setItem('voter_election_id', item.election_id);
                            navigateTo(`/user/e/${item.election_id}/overview`);
                          }}
                          className={`px-3 py-1 text-xs rounded border transition ${
                            isCurrent
                              ? 'bg-paper text-ink border-line font-bold'
                              : 'bg-paper-2 text-ink/80 border-line hover:bg-paper'
                          }`}
                        >
                          {isCurrent ? 'Viewing' : 'Switch'}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 2. PERSONAL STEP TRACKER FOR THIS ELECTION */}
      <div className="bg-paper border border-line rounded-xl p-6 sm:p-8">
        <h2 className="font-display text-lg font-bold text-ink mb-6">
          Your Election Journey & Progress
        </h2>

        <div className="space-y-6">
          {/* Step 1: Registered */}
          <div className="flex items-start gap-4">
            <div className="w-8 h-8 rounded-full bg-emerald-100 border border-emerald-300 flex items-center justify-center text-emerald-700 flex-shrink-0">
              <CheckCircle2 className="w-4 h-4" />
            </div>
            <div className="flex-1">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1">
                <h4 className="text-xs font-mono font-bold uppercase text-ink">1. Identity Verified & Registered</h4>
                <span className="text-[11px] font-mono text-ink/50">
                  {voterMe?.registered_at || 'Completed'}
                </span>
              </div>
              <p className="text-xs text-ink/70 mt-1">
                Biometric template encrypted with zero-knowledge commitment stored securely on the ledger.
              </p>
            </div>
          </div>

          {/* Step 2: Credential emailed */}
          <div className="flex items-start gap-4">
            <div className={`w-8 h-8 rounded-full border flex items-center justify-center flex-shrink-0 ${
              activeMyElection?.progress?.delivery_status === 'FAILED'
                ? 'bg-red-100 border-red-300 text-red-700'
                : 'bg-emerald-100 border-emerald-300 text-emerald-700'
            }`}>
              {activeMyElection?.progress?.delivery_status === 'FAILED' ? (
                <AlertCircle className="w-4 h-4" />
              ) : (
                <CheckCircle2 className="w-4 h-4" />
              )}
            </div>
            <div className="flex-1">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1">
                <h4 className="text-xs font-mono font-bold uppercase text-ink">2. Secret Share A Emailed</h4>
                <span className="text-[11px] font-mono text-ink/50">
                  {activeMyElection?.progress?.delivery_status === 'FAILED' ? 'Delivery Failed' : 'Delivered to Official Email'}
                </span>
              </div>
              <p className="text-xs text-ink/70 mt-1">
                Secret Share A was dispatched directly to your registered email address ({voterMe?.email || 'registered address'}).
              </p>
              {/* Only show "Send credential again" if delivery status is FAILED */}
              {activeMyElection?.progress?.delivery_status === 'FAILED' && (
                <div className="mt-2">
                  <button
                    type="button"
                    onClick={() => {
                      setReissuePassword('');
                      setReissueError(null);
                      setReissueMsg(null);
                      setShowReissueModal(true);
                    }}
                    className="px-3 py-1 bg-red-50 text-red-700 border border-red-200 text-xs font-mono rounded hover:bg-red-100 transition flex items-center gap-1.5"
                  >
                    <RefreshCw className="w-3 h-3" />
                    <span>Send credential again (Reissue)</span>
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Step 3: Voting window announced */}
          <div className="flex items-start gap-4">
            <div className={`w-8 h-8 rounded-full border flex items-center justify-center flex-shrink-0 ${
              electionData?.scheduled_start
                ? 'bg-emerald-100 border-emerald-300 text-emerald-700'
                : 'bg-paper-2 border-line text-ink/40'
            }`}>
              <Clock className="w-4 h-4" />
            </div>
            <div className="flex-1">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1">
                <h4 className="text-xs font-mono font-bold uppercase text-ink">3. Voting Window Announced</h4>
                <span className="text-[11px] font-mono text-ink/50">
                  {electionData?.formatted_window || 'Pending announcement'}
                </span>
              </div>
              <p className="text-xs text-ink/70 mt-1">
                Official election timetable announced by administrators and anchored in audit logs.
              </p>
            </div>
          </div>

          {/* Step 4: Voting open */}
          <div className="flex items-start gap-4">
            <div className={`w-8 h-8 rounded-full border flex items-center justify-center flex-shrink-0 ${
              status === 'OPEN' || hasVoted || status === 'CLOSED' || resultsPublished
                ? 'bg-emerald-100 border-emerald-300 text-emerald-700'
                : 'bg-paper-2 border-line text-ink/40'
            }`}>
              <Vote className="w-4 h-4" />
            </div>
            <div className="flex-1">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1">
                <h4 className="text-xs font-mono font-bold uppercase text-ink">4. Voting Open</h4>
                <span className="text-[11px] font-mono text-ink/50">
                  {status === 'OPEN' ? 'Currently Open' : (hasVoted || status === 'CLOSED' ? 'Completed' : 'Upcoming')}
                </span>
              </div>
              <p className="text-xs text-ink/70 mt-1">
                Time-lock expired and server Share B unlocked for anonymous blind-token issuance.
              </p>
            </div>
          </div>

          {/* Step 5: I voted */}
          <div className="flex items-start gap-4">
            <div className={`w-8 h-8 rounded-full border flex items-center justify-center flex-shrink-0 ${
              hasVoted
                ? 'bg-emerald-100 border-emerald-300 text-emerald-700'
                : 'bg-paper-2 border-line text-ink/40'
            }`}>
              <FileCheck className="w-4 h-4" />
            </div>
            <div className="flex-1">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1">
                <h4 className="text-xs font-mono font-bold uppercase text-ink">5. Ballot Cast & Verified</h4>
                <span className="text-[11px] font-mono text-ink/50">
                  {hasVoted ? 'Recorded on ledger' : 'Pending ballot submission'}
                </span>
              </div>
              <p className="text-xs text-ink/70 mt-1">
                {hasVoted ? (
                  <span>
                    Your encrypted ballot was verified with zero-knowledge proofs and appended to the ledger.{' '}
                    {storedReceipt && (
                      <span className="font-mono font-bold text-ink">Receipt: {storedReceipt}. </span>
                    )}
                    <button
                      type="button"
                      onClick={() => navigateTo(`/user/e/${activeElectionId}/audit`)}
                      className="text-accent underline font-semibold inline-flex items-center gap-0.5"
                    >
                      Verify my receipt on the bulletin board
                    </button>
                  </span>
                ) : (
                  'Cast your encrypted ballot once voting is open.'
                )}
              </p>
            </div>
          </div>

          {/* Step 6: Results published */}
          <div className="flex items-start gap-4">
            <div className={`w-8 h-8 rounded-full border flex items-center justify-center flex-shrink-0 ${
              resultsPublished
                ? 'bg-purple-100 border-purple-300 text-purple-700'
                : 'bg-paper-2 border-line text-ink/40'
            }`}>
              <BarChart3 className="w-4 h-4" />
            </div>
            <div className="flex-1">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1">
                <h4 className="text-xs font-mono font-bold uppercase text-ink">6. Results Published</h4>
                <span className="text-[11px] font-mono text-ink/50">
                  {resultsPublished ? 'Certified & Published' : 'Pending trustee unlock ceremony'}
                </span>
              </div>
              <p className="text-xs text-ink/70 mt-1">
                {resultsPublished
                  ? 'Trustee sequential ceremony concluded. Homomorphic decryption proof published.'
                  : 'Following election closure, trustees will run the sequential unlock ceremony to certify final results.'}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* 5. RECENT NOTIFICATIONS (LAST 5) */}
      <div className="bg-paper-2 border border-line rounded-xl p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Bell className="w-4 h-4 text-accent" />
            <h3 className="font-display text-sm font-bold text-ink uppercase tracking-wider">
              Recent Notifications ({notifications.length})
            </h3>
          </div>
          <button
            type="button"
            onClick={() => navigateTo(`/user/e/${activeElectionId}/notifications`)}
            className="text-xs font-mono text-accent hover:underline flex items-center gap-1"
          >
            <span>View all</span>
            <ArrowRight className="w-3 h-3" />
          </button>
        </div>

        {notifications.length === 0 ? (
          <p className="text-xs font-mono text-ink/50 py-3">No notifications for this election yet.</p>
        ) : (
          <div className="divide-y divide-line">
            {notifications.map((n) => (
              <div key={n.id} className="py-3 first:pt-0 last:pb-0">
                <div className="flex items-center justify-between gap-2">
                  <h4 className="text-xs font-semibold text-ink">{n.title}</h4>
                  <span className="text-[10px] font-mono text-ink/50">
                    {new Date(n.created_at).toLocaleDateString()}
                  </span>
                </div>
                <p className="text-xs text-ink/70 mt-0.5">{n.body}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 6. RESULTS TABLE (IF PUBLISHED) */}
      {resultsPublished && tallyResults && (
        <div id="results-section" className="bg-paper border border-purple-200 rounded-xl p-6 shadow-sm">
          <div className="flex items-center justify-between mb-4 border-b border-line pb-3">
            <div className="flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-purple-600" />
              <h3 className="font-display text-base font-bold text-ink">Certified Election Results</h3>
            </div>
            <span className="text-xs font-mono bg-purple-50 text-purple-700 px-2.5 py-1 rounded border border-purple-200 font-semibold">
              Audited & Approved by Trustees
            </span>
          </div>

          {(() => {
            const entries = Object.entries(tallyResults.results || {});
            const maxVotes = Math.max(...entries.map(([_, count]: [string, any]) => Number(count) || 0), 0);
            const total = tallyResults.total_ballots || entries.reduce((acc, [_, v]) => acc + Number(v), 0) || 1;

            return (
              <div className="space-y-3 mb-5">
                {entries.map(([candidate, count]: [string, any]) => {
                  const cCount = Number(count) || 0;
                  const pct = ((cCount / total) * 100).toFixed(1);
                  const isWinner = cCount === maxVotes && maxVotes > 0;

                  return (
                    <div key={candidate} className="p-3.5 bg-paper-2 rounded-lg border border-line">
                      <div className="flex items-center justify-between text-xs font-mono mb-2">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-ink text-sm">{candidate}</span>
                          {isWinner && (
                            <span className="inline-flex items-center gap-1 text-[10px] uppercase font-bold bg-amber-100 text-amber-800 border border-amber-300 px-2 py-0.5 rounded-full">
                              <Trophy className="w-3 h-3 text-amber-600" />
                              Winner
                            </span>
                          )}
                        </div>
                        <div className="text-right">
                          <span className="text-sm font-bold text-ink">{cCount} {cCount === 1 ? 'vote' : 'votes'}</span>
                          <span className="text-ink/60 ml-2">({pct}%)</span>
                        </div>
                      </div>
                      <div className="w-full h-2.5 bg-line rounded-full overflow-hidden">
                        <div
                          className={`h-full transition-all duration-500 ${isWinner ? 'bg-amber-500' : 'bg-purple-600'}`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            );
          })()}

          <div className="text-[11px] font-mono text-ink/60 bg-paper-2 p-3 rounded border border-line flex flex-wrap items-center justify-between gap-2">
            <span>Total Ballots Cast: <strong className="text-ink">{tallyResults.total_ballots}</strong></span>
            {tallyResults.root_hash && (
              <span>Bulletin Board Root Hash: <span className="text-accent font-bold">{tallyResults.root_hash.substring(0, 16)}...</span></span>
            )}
          </div>
        </div>
      )}

      {/* 7. COLLAPSIBLE "HOW IS MY VOTE PROTECTED?" DISCLOSURE */}
      <div className="border border-line rounded-xl overflow-hidden bg-paper-2">
        <button
          type="button"
          onClick={() => setIsProtectedExpanded(!isProtectedExpanded)}
          className="w-full p-4 flex items-center justify-between text-left hover:bg-paper transition"
        >
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-accent" />
            <span className="font-display text-sm font-bold text-ink">How is my vote protected?</span>
          </div>
          {isProtectedExpanded ? (
            <ChevronUp className="w-4 h-4 text-ink/50" />
          ) : (
            <ChevronDown className="w-4 h-4 text-ink/50" />
          )}
        </button>

        {isProtectedExpanded && (
          <div className="p-4 pt-0 border-t border-line text-xs font-mono text-ink/70 space-y-2 leading-relaxed bg-paper">
            <p>
              • <strong>2-of-2 Shamir Secret Sharing:</strong> Your voting credential is split into Share A (emailed to you) and Share B (time-locked until election day). Neither part alone can cast a vote.
            </p>
            <p>
              • <strong>RSA Blind Signatures:</strong> The server signs your vote authorization token without ever seeing the token nonce or your ballot choices.
            </p>
            <p>
              • <strong>ElGamal Homomorphic Encryption & ZKPs:</strong> Each candidate choice is encrypted on your device. Zero-knowledge proofs guarantee your choices are valid without revealing candidate selections.
            </p>
            <p>
              • <strong>Public Bulletin Board:</strong> Every ballot block is chained cryptographically. Anyone can audit the Merkle tree to verify their vote was included.
            </p>
          </div>
        )}
      </div>

      {/* REISSUE CREDENTIAL MODAL */}
      {showReissueModal && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center p-4 z-50">
          <div className="bg-paper border border-line rounded-xl p-6 max-w-md w-full shadow-xl">
            <h3 className="font-display text-lg font-bold text-ink mb-2">Reissue Voting Credential</h3>
            <p className="text-xs text-ink/70 mb-4 leading-relaxed">
              Because {APP_NAME} never stores raw secret shares, requesting credential delivery generates a brand new secret share pair, invalidates previous credentials, and sends Share A to your registered email.
            </p>

            {reissueMsg && (
              <div className="p-3 mb-4 rounded bg-emerald-50 border border-emerald-300 text-emerald-800 text-xs">
                {reissueMsg}
              </div>
            )}

            {reissueError && (
              <div className="p-3 mb-4 rounded bg-red-50 border border-red-300 text-red-800 text-xs">
                {reissueError}
              </div>
            )}

            <form onSubmit={handleReissueCredential} className="space-y-4">
              <div>
                <label className="block text-xs font-mono text-ink/70 mb-1">Confirm Account Password:</label>
                <input
                  type="password"
                  value={reissuePassword}
                  onChange={(e) => setReissuePassword(e.target.value)}
                  placeholder="Enter your voter account password"
                  required
                  className="w-full px-3 py-2 bg-paper-2 border border-line rounded text-xs font-mono text-ink focus:outline-none focus:border-accent"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowReissueModal(false)}
                  className="px-4 py-2 border border-line bg-paper text-xs font-mono text-ink/70 rounded hover:bg-paper-2"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isReissuing}
                  className="px-4 py-2 bg-primary text-white text-xs font-mono font-semibold rounded hover:bg-primary/90 disabled:opacity-50"
                >
                  {isReissuing ? 'Generating...' : 'Reissue Credential'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

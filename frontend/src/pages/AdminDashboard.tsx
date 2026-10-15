import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Vote,
  LayoutDashboard,
  Calendar,
  Sliders,
  Users,
  Shield,
  RotateCcw,
  CheckCircle2,
  LogOut,
  Search,
  Send,
  AlertCircle,
  Plus,
  Trash2,
  KeyRound,
  AlertTriangle,
  GripVertical,
  ExternalLink,
  BarChart3,
  Lock,
  Unlock,
  Settings as SettingsIcon,
  Copy,
  Trophy,
} from 'lucide-react';
import { APP_NAME } from '../constants';
import { CreateElection } from './CreateElection';
import { CustomSelect } from '../components/FormControls';
import { formatApiError } from '../utils/apiError';

export interface TrusteeItem {
  id: string; // Stable client-side UUID or ID
  trustee_id?: number;
  name: string;
  email: string;
  position?: number;
  email_status?: string;
  email_sent_at?: string;
  link_opened_at?: string;
  has_approved?: boolean;
  approved_at?: string;
}

interface AdminDashboardProps {
  currentElectionId?: string;
  initialSection?: AdminSection;
  onSelectElection?: (electionId: string) => void;
  onStatusChange?: () => void;
  onLogout?: () => void;
  navigateTo?: (path: string) => void;
}

export type AdminSection = 'elections' | 'overview' | 'schedule' | 'voting-control' | 'trustees' | 'tally-results' | 'voter-roll' | 'audit-log' | 'settings';

export const adminSectionToSlug: Record<AdminSection, string> = {
  'overview': 'overview',
  'schedule': 'schedule',
  'voting-control': 'voting',
  'trustees': 'trustees',
  'tally-results': 'tally',
  'voter-roll': 'voters',
  'audit-log': 'audit',
  'elections': 'elections',
  'settings': 'settings',
};

export const slugToAdminSection: Record<string, AdminSection> = {
  'overview': 'overview',
  'schedule': 'schedule',
  'voting': 'voting-control',
  'voting-control': 'voting-control',
  'trustees': 'trustees',
  'tally': 'tally-results',
  'tally-results': 'tally-results',
  'voters': 'voter-roll',
  'voter-roll': 'voter-roll',
  'audit': 'audit-log',
  'audit-log': 'audit-log',
  'elections': 'elections',
  'settings': 'settings',
};

// Helper to create a new unique draft trustee
const createNewTrusteeSlot = (position: number): TrusteeItem => ({
  id: `trustee-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`,
  position,
  trustee_id: position,
  name: '',
  email: '',
  email_status: 'NOT_INVITED',
});

// Module-level Trustee Row component to prevent unmounting/remounting on parent renders
interface TrusteeRowProps {
  trustee: TrusteeItem;
  index: number;
  isRosterLocked: boolean;
  isLast: boolean;
  onUpdateName: (id: string, name: string) => void;
  onUpdateEmail: (id: string, email: string) => void;
  onRemove: (id: string) => void;
  onAddNext: () => void;
  nameRef: (el: HTMLInputElement | null) => void;
  emailRef: (el: HTMLInputElement | null) => void;
  duplicateEmail?: boolean;
}

const TrusteeRow: React.FC<TrusteeRowProps> = React.memo(({
  trustee,
  index,
  isRosterLocked,
  isLast,
  onUpdateName,
  onUpdateEmail,
  onRemove,
  onAddNext,
  nameRef,
  emailRef,
  duplicateEmail,
}) => {
  const isEmailValid = !trustee.email || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trustee.email.trim());

  return (
    <div className="flex flex-col gap-1 p-3.5 bg-ink border border-ink-3 rounded-lg text-xs font-mono">
      <div className="flex flex-col sm:flex-row items-center gap-3">
        <div className="flex items-center gap-2 text-on-ink/50 w-20 flex-shrink-0 select-none">
          <GripVertical className="w-3.5 h-3.5 opacity-40 cursor-grab" />
          <span>Slot #{index + 1}</span>
        </div>

        <div className="flex-1 w-full">
          <input
            ref={nameRef}
            type="text"
            placeholder="Full Name"
            value={trustee.name}
            disabled={isRosterLocked}
            onChange={(e) => onUpdateName(trustee.id, e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                // Focus corresponding email
                const emailEl = document.getElementById(`trustee-email-${trustee.id}`) as HTMLInputElement;
                if (emailEl) emailEl.focus();
              }
            }}
            className="w-full px-3 py-1.5 bg-ink-2 text-white border border-ink-3 rounded text-xs font-mono disabled:opacity-60 focus:outline-none focus:border-on-ink"
          />
        </div>

        <div className="flex-1 w-full">
          <input
            id={`trustee-email-${trustee.id}`}
            ref={emailRef}
            type="email"
            placeholder="Email Address"
            value={trustee.email}
            disabled={isRosterLocked}
            onChange={(e) => onUpdateEmail(trustee.id, e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                if (isLast && !isRosterLocked) {
                  onAddNext();
                }
              }
            }}
            className={`w-full px-3 py-1.5 bg-ink-2 text-white border rounded text-xs font-mono disabled:opacity-60 focus:outline-none ${
              !isEmailValid || duplicateEmail
                ? 'border-red-500 focus:border-red-400'
                : 'border-ink-3 focus:border-on-ink'
            }`}
          />
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          {isRosterLocked ? (
            <span
              className={`px-2 py-0.5 rounded text-[10px] ${
                trustee.has_approved
                  ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                  : trustee.link_opened_at
                  ? 'bg-blue-950 text-blue-300 border border-blue-800'
                  : 'bg-amber-950 text-amber-300 border border-amber-800'
              }`}
            >
              {trustee.has_approved ? 'APPROVED' : trustee.link_opened_at ? 'LINK OPENED' : 'INVITED'}
            </span>
          ) : (
            <span className="px-2 py-0.5 rounded text-[10px] bg-ink-3 text-on-ink/60 border border-ink-3">
              Not invited
            </span>
          )}

          {!isRosterLocked && (
            <button
              type="button"
              onClick={() => onRemove(trustee.id)}
              className="p-1.5 text-on-ink/40 hover:text-red-400 transition"
              title="Remove slot"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Inline validation errors */}
      {(!isEmailValid || duplicateEmail) && (
        <div className="text-[11px] text-red-400 pl-24">
          {!isEmailValid && '• Invalid email address format.'}
          {duplicateEmail && ' • Email already used in another slot.'}
        </div>
      )}
    </div>
  );
});

export const AdminDashboard: React.FC<AdminDashboardProps> = ({
  currentElectionId,
  initialSection,
  onSelectElection,
  onStatusChange,
  onLogout,
  navigateTo,
}) => {
  const [activeSection, setActiveSection] = useState<AdminSection>(initialSection || 'overview');
  const [isCreatingElection, setIsCreatingElection] = useState<boolean>(false);
  const [editingElection, setEditingElection] = useState<any | null>(null);
  const [activeElectionId, setActiveElectionId] = useState<string>(currentElectionId || '');
  const [electionList, setElectionList] = useState<any[]>([]);
  const [status, setStatus] = useState<string>('REGISTRATION');
  const [isOpen, setIsOpen] = useState<boolean>(false);
  const [totalBallots, setTotalBallots] = useState<number>(0);
  const [electionTitle, setElectionTitle] = useState<string>('');
  const [emailDeliveryWarning, setEmailDeliveryWarning] = useState<boolean>(false);

  useEffect(() => {
    if (initialSection && initialSection !== activeSection) {
      setActiveSection(initialSection);
    }
  }, [initialSection]);

  useEffect(() => {
    if (currentElectionId && currentElectionId !== activeElectionId) {
      setActiveElectionId(currentElectionId);
    }
  }, [currentElectionId]);

  const changeSection = useCallback((sec: AdminSection) => {
    setActiveSection(sec);
    if (activeElectionId) {
      navigateTo?.(`/admin/e/${activeElectionId}/${adminSectionToSlug[sec]}`);
    }
  }, [activeElectionId, navigateTo]);

  // Schedule State (Starts empty, no now-based pre-fill)
  const [scheduledStart, setScheduledStart] = useState<string>('');
  const [scheduledEnd, setScheduledEnd] = useState<string>('');
  const [timezoneStr, setTimezoneStr] = useState<string>('UTC');
  const [formattedWindow, setFormattedWindow] = useState<string>('Dates to be announced');
  const [isSavingSchedule, setIsSavingSchedule] = useState<boolean>(false);
  const [showAnnounceConfirmModal, setShowAnnounceConfirmModal] = useState<boolean>(false);

  // Voting Control Modals
  const [showOpenConfirmModal, setShowOpenConfirmModal] = useState<boolean>(false);
  const [showCloseConfirmModal, setShowCloseConfirmModal] = useState<boolean>(false);
  const [deleteStep, setDeleteStep] = useState<0 | 1 | 2>(0);
  const [pendingDelete, setPendingDelete] = useState<{
    election_id: string;
    title: string;
    registered_voters: number;
    ballots_cast: number;
  } | null>(null);
  const [closeConfirmInput, setCloseConfirmInput] = useState<string>('');

  // Trustee Portal State (Starts EMPTY for clean state)
  const [trustees, setTrustees] = useState<TrusteeItem[]>([]);
  const [hasLocalTrusteeEdits, setHasLocalTrusteeEdits] = useState<boolean>(false);
  const [ceremonyWindowMinutes, setCeremonyWindowMinutes] = useState<number>(5);
  const [resultsPublishedAt, setResultsPublishedAt] = useState<string | null>(null);
  const [isRosterLocked, setIsRosterLocked] = useState<boolean>(false);
  const [invitationsSentAt, setInvitationsSentAt] = useState<string | null>(null);

  // Focus management refs
  const nameInputRefs = useRef<Record<string, HTMLInputElement | null>>({});
  const emailInputRefs = useRef<Record<string, HTMLInputElement | null>>({});
  const newlyAddedIdRef = useRef<string | null>(null);

  // Modals for Trustee Portal
  const [showInviteModal, setShowInviteModal] = useState<boolean>(false);
  const [isInviting, setIsInviting] = useState<boolean>(false);
  const [showReissueModal, setShowReissueModal] = useState<boolean>(false);
  const [reissuePassword, setReissuePassword] = useState<string>('');
  const [isReissuing, setIsReissuing] = useState<boolean>(false);
  const [isPublishing, setIsPublishing] = useState<boolean>(false);

  // Live Ceremony Monitor & Tally State
  const [ceremonyMonitor, setCeremonyMonitor] = useState<any | null>(null);
  const [publishedTally, setPublishedTally] = useState<any | null>(null);

  // Voter Roll State
  const [voterRoll, setVoterRoll] = useState<any[]>([]);
  const [voterSearch, setVoterSearch] = useState<string>('');

  // Audit State
  const [bulletinBoard, setBulletinBoard] = useState<any[]>([]);

  // Email Settings State
  const [emailSettings, setEmailSettings] = useState<{
    configured: boolean;
    smtp_host: string;
    smtp_port: number;
    smtp_user: string;
    smtp_from: string;
    effective_from: string;
    tls_mode: string;
    is_gmail: boolean;
  } | null>(null);
  const [testEmailAddress, setTestEmailAddress] = useState<string>('');
  const [isSendingTestEmail, setIsSendingTestEmail] = useState<boolean>(false);
  const [testEmailResult, setTestEmailResult] = useState<{ success: boolean; message: string; detail?: string } | null>(null);
  const [bulletinBoardHeadHash, setBulletinBoardHeadHash] = useState<string>('');

  // Resend ceremony link state
  const [resendingTrusteeId, setResendingTrusteeId] = useState<number | null>(null);

  // Feedback Messages
  const [msg, setMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [scheduleWarning, setScheduleWarning] = useState<string | null>(null);
  const [isLoadingAction, setIsLoadingAction] = useState<boolean>(false);

  // Auto-dismiss banners after 8 seconds
  useEffect(() => {
    if (!msg) return;
    const t = setTimeout(() => setMsg(null), 8000);
    return () => clearTimeout(t);
  }, [msg]);

  useEffect(() => {
    if (!errorMsg) return;
    const t = setTimeout(() => setErrorMsg(null), 8000);
    return () => clearTimeout(t);
  }, [errorMsg]);

  // Clear banners on tab or election change
  useEffect(() => {
    setMsg(null);
    setErrorMsg(null);
    setScheduleWarning(null);
  }, [activeSection, activeElectionId]);

  // Reset Modal
  const [showResetConfirm, setShowResetConfirm] = useState<boolean>(false);
  const [isResetting, setIsResetting] = useState<boolean>(false);

  const getAuthHeaders = () => {
    const token = sessionStorage.getItem('ciphervote_admin_token') || 'admin_session_valid_2026';
    return {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    };
  };

  // Fetch elections list
  const fetchElectionsList = useCallback(async () => {
    try {
      const res = await fetch('/api/admin/elections', { headers: getAuthHeaders() });
      if (res.ok) {
        const data = await res.json();
        const els = data.elections || [];
        setElectionList(els);

        if (els.length > 0) {
          if (!activeElectionId || !els.some((e: any) => e.election_id === activeElectionId)) {
            const firstId = els[0].election_id;
            setActiveElectionId(firstId);
            if (onSelectElection) onSelectElection(firstId);
          }
        } else {
          setActiveElectionId('');
        }
      }
    } catch (e) {
      console.error(e);
    }
  }, [activeElectionId, onSelectElection]);

  const fetchStatus = useCallback(async (elId: string) => {
    if (!elId) return;
    try {
      const res = await fetch(`/api/admin/overview?election_id=${encodeURIComponent(elId)}`, {
        headers: getAuthHeaders(),
      });
      if (res.ok) {
        const data = await res.json();
        setStatus(data.status);
        setIsOpen(data.is_open);
        setTotalBallots(data.ballots_cast);
        setElectionTitle(data.title);
        setTimezoneStr(data.timezone || 'UTC');
        setFormattedWindow(data.formatted_window || 'Dates to be announced');
        setInvitationsSentAt(data.invitations_sent_at);
        setEmailDeliveryWarning(Boolean(data.email_delivery_warning));
        if (data.bulletin_board_head_hash) {
          setBulletinBoardHeadHash(data.bulletin_board_head_hash);
        }
      }
    } catch (e) {
      console.error(e);
    }
  }, []);

  const fetchEmailSettings = useCallback(async () => {
    try {
      const res = await fetch('/api/admin/settings/email', { headers: getAuthHeaders() });
      if (res.ok) {
        const data = await res.json();
        setEmailSettings(data);
      }
    } catch (_) {}
  }, []);

  const fetchSchedule = useCallback(async (elId: string) => {
    if (!elId) return;
    try {
      const res = await fetch(`/api/admin/schedule?election_id=${encodeURIComponent(elId)}`, {
        headers: getAuthHeaders(),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.timezone) setTimezoneStr(data.timezone);
        if (data.formatted_window) setFormattedWindow(data.formatted_window);
        if (data.scheduled_start) {
          const dStart = new Date(data.scheduled_start);
          const tzOffset = dStart.getTimezoneOffset() * 60000;
          const localISO = new Date(dStart.getTime() - tzOffset).toISOString().slice(0, 16);
          setScheduledStart(localISO);
        }
        if (data.scheduled_end) {
          const dEnd = new Date(data.scheduled_end);
          const tzOffset = dEnd.getTimezoneOffset() * 60000;
          const localISO = new Date(dEnd.getTime() - tzOffset).toISOString().slice(0, 16);
          setScheduledEnd(localISO);
        }
      }
    } catch (e) {
      console.error(e);
    }
  }, []);

  const fetchVoterRoll = useCallback(async (elId: string) => {
    if (!elId) return;
    try {
      const res = await fetch(`/api/admin/voters?election_id=${encodeURIComponent(elId)}`, {
        headers: getAuthHeaders(),
      });
      if (res.ok) {
        const data = await res.json();
        setVoterRoll(data.voters || []);
      }
    } catch (_) {
      setVoterRoll([]);
    }
  }, []);

  const fetchTrustees = useCallback(async (elId: string, force = false) => {
    if (!elId) return;
    try {
      const res = await fetch(`/api/admin/trustees?election_id=${encodeURIComponent(elId)}`, {
        headers: getAuthHeaders(),
      });
      if (res.ok) {
        const data = await res.json();
        setCeremonyWindowMinutes(data.ceremony_window_minutes || 5);
        setResultsPublishedAt(data.results_published_at);
        setIsRosterLocked(Boolean(data.is_roster_locked));
        setInvitationsSentAt(data.invitations_sent_at);

        // Only overwrite local trustees if forced, or if roster is already locked, or if no local unsaved edits
        if (force || data.is_roster_locked || !hasLocalTrusteeEdits) {
          const loaded: TrusteeItem[] = (data.trustees || []).map((t: any, idx: number) => ({
            id: t.id ? String(t.id) : `trustee-server-${idx}-${t.trustee_id}`,
            trustee_id: t.trustee_id,
            name: t.name || '',
            email: t.email || '',
            position: t.position || idx + 1,
            email_status: t.email_status,
            email_sent_at: t.email_sent_at,
            link_opened_at: t.link_opened_at,
            has_approved: t.has_approved,
            approved_at: t.approved_at,
          }));
          setTrustees(loaded);
        }
      }
    } catch (_) {
      if (force) setTrustees([]);
    }
  }, [hasLocalTrusteeEdits]);

  const fetchCeremonyMonitor = useCallback(async (elId: string) => {
    if (!elId) return;
    try {
      const res = await fetch(`/api/admin/trustees/ceremony-monitor?election_id=${encodeURIComponent(elId)}`, {
        headers: getAuthHeaders(),
      });
      if (res.ok) {
        const data = await res.json();
        setCeremonyMonitor(data);
      }
    } catch (_) {}
  }, []);

  const fetchAuditData = useCallback(async (elId: string) => {
    if (!elId) return;
    try {
      const res = await fetch(`/api/public/bulletin-board?election_id=${encodeURIComponent(elId)}`);
      if (res.ok) {
        const data = await res.json();
        setBulletinBoard(data.ballots || []);
      }
    } catch (_) {}
  }, []);

  const fetchPublishedResults = useCallback(async (elId: string) => {
    if (!elId) return;
    try {
      const res = await fetch(`/api/public/results?election_id=${encodeURIComponent(elId)}`);
      if (res.ok) {
        const data = await res.json();
        if (data && data.published) {
          setPublishedTally(data);
        } else {
          setPublishedTally(null);
        }
      }
    } catch (_) {}
  }, []);

  useEffect(() => {
    fetchElectionsList();
    fetchEmailSettings();
  }, [fetchElectionsList, fetchEmailSettings]);

  useEffect(() => {
    if (activeElectionId) {
      fetchStatus(activeElectionId);
      fetchSchedule(activeElectionId);
      fetchVoterRoll(activeElectionId);
      fetchTrustees(activeElectionId, true);
      fetchCeremonyMonitor(activeElectionId);
      fetchAuditData(activeElectionId);
      fetchPublishedResults(activeElectionId);
    }
  }, [activeElectionId, fetchStatus, fetchSchedule, fetchVoterRoll, fetchTrustees, fetchCeremonyMonitor, fetchAuditData, fetchPublishedResults]);

  // Periodic polling (does NOT wipe local draft edits)
  useEffect(() => {
    if (!activeElectionId) return;
    const interval = setInterval(() => {
      fetchStatus(activeElectionId);
      if (activeSection === 'trustees' || activeSection === 'tally-results') {
        fetchTrustees(activeElectionId, false);
        fetchCeremonyMonitor(activeElectionId);
        fetchPublishedResults(activeElectionId);
      }
    }, 4000);
    return () => clearInterval(interval);
  }, [activeElectionId, activeSection, fetchStatus, fetchTrustees, fetchCeremonyMonitor, fetchPublishedResults]);

  // Focus newly added trustee row name input
  useEffect(() => {
    if (newlyAddedIdRef.current) {
      const el = nameInputRefs.current[newlyAddedIdRef.current];
      if (el) {
        el.focus();
      }
      newlyAddedIdRef.current = null;
    }
  }, [trustees]);

  const handleElectionChange = (newId: string) => {
    setActiveElectionId(newId);
    setHasLocalTrusteeEdits(false);
    setMsg(null);
    setErrorMsg(null);
    setCloseConfirmInput('');
    if (onSelectElection) onSelectElection(newId);
    navigateTo?.(`/admin/e/${encodeURIComponent(newId)}/${adminSectionToSlug[activeSection]}`);
  };

  const handleElectionCreated = (newId: string) => {
    setIsCreatingElection(false);
    setActiveElectionId(newId);
    setActiveSection('overview');
    setHasLocalTrusteeEdits(false);
    fetchElectionsList();
    setMsg('New election created successfully. Follow the Setup Checklist to complete configuration.');
  };

  const closeDeleteDialog = () => {
    setDeleteStep(0);
    setPendingDelete(null);
  };

  const handleDeleteElection = async () => {
    if (!pendingDelete || deleteStep !== 2) return;
    const elId = pendingDelete.election_id;
    const title = pendingDelete.title;
    try {
      const res = await fetch(`/api/admin/elections/${encodeURIComponent(elId)}`, {
        method: 'DELETE',
        headers: getAuthHeaders(),
      });
      const data = await res.json();
      if (!res.ok) {
        const parsed = formatApiError(data);
        throw new Error(parsed.message);
      }
      closeDeleteDialog();
      setMsg(data.message || `Election "${title}" deleted.`);
      if (activeElectionId === elId) {
        setActiveElectionId('');
        navigateTo?.('/admin/elections');
      }
      fetchElectionsList();
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to delete election.');
    }
  };

  const handleArchiveElection = async (elId: string) => {
    try {
      const res = await fetch(`/api/admin/elections/${encodeURIComponent(elId)}/archive`, {
        method: 'POST',
        headers: getAuthHeaders(),
      });
      const data = await res.json();
      if (!res.ok) {
        const parsed = formatApiError(data);
        throw new Error(parsed.message);
      }
      setMsg(data.message || 'Election archived.');
      fetchElectionsList();
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to archive election.');
    }
  };

  // Schedule Validation & Saving
  const handlePreAnnounceClick = () => {
    setErrorMsg(null);
    setScheduleWarning(null);

    if (!scheduledStart || !scheduledEnd) {
      setErrorMsg('Please enter both Voting Start and Voting End date-times.');
      return;
    }

    const startDate = new Date(scheduledStart);
    const endDate = new Date(scheduledEnd);

    if (endDate <= startDate) {
      setErrorMsg('Voting End date-time must be strictly after the Start date-time.');
      return;
    }

    const durationMinutes = (endDate.getTime() - startDate.getTime()) / 60000;
    if (durationMinutes < 1) {
      setErrorMsg('Voting window must be at least 1 minute long.');
      return;
    }

    if (startDate.getTime() < Date.now()) {
      setScheduleWarning('This start time has already passed. Voters will still be told the window.');
    }

    setShowAnnounceConfirmModal(true);
  };

  const handleSaveAndAnnounceSchedule = async () => {
    if (!scheduledStart || !scheduledEnd || !activeElectionId) return;

    const startDate = new Date(scheduledStart);
    const endDate = new Date(scheduledEnd);

    setIsSavingSchedule(true);
    setErrorMsg(null);
    setMsg(null);

    try {
      const payload = {
        election_id: activeElectionId,
        scheduled_start: startDate.toISOString(),
        scheduled_end: endDate.toISOString(),
        timezone: timezoneStr || 'UTC',
        announce: true,
      };

      const res = await fetch('/api/admin/schedule', {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (!res.ok) {
        const parsed = formatApiError(data);
        throw new Error(parsed.message);
      }

      setMsg(data.message || `Voting window saved: ${data.formatted_window}`);
      setFormattedWindow(data.formatted_window);
      setShowAnnounceConfirmModal(false);
      fetchStatus(activeElectionId);
      if (onStatusChange) onStatusChange();
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to save schedule.');
    } finally {
      setIsSavingSchedule(false);
    }
  };

  const handleOpenVoting = async () => {
    setIsLoadingAction(true);
    setErrorMsg(null);
    setMsg(null);

    try {
      const res = await fetch('/api/admin/voting/open', {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ election_id: activeElectionId }),
      });

      const data = await res.json();
      if (!res.ok) {
        const parsed = formatApiError(data);
        throw new Error(parsed.message);
      }

      setMsg(data.message || 'Voting is now officially open.');
      setShowOpenConfirmModal(false);
      fetchStatus(activeElectionId);
      if (onStatusChange) onStatusChange();
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to open voting.');
    } finally {
      setIsLoadingAction(false);
    }
  };

  const handleCloseVoting = async () => {
    setIsLoadingAction(true);
    setErrorMsg(null);
    setMsg(null);

    try {
      const res = await fetch('/api/admin/voting/close', {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ election_id: activeElectionId }),
      });

      const data = await res.json();
      if (!res.ok) {
        const parsed = formatApiError(data);
        throw new Error(parsed.message);
      }

      setMsg(data.message || 'Voting closed. Ballot box sealed.');
      setShowCloseConfirmModal(false);
      fetchStatus(activeElectionId);
      fetchTrustees(activeElectionId, true);
      if (onStatusChange) onStatusChange();
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to close voting.');
    } finally {
      setIsLoadingAction(false);
    }
  };

  // Trustee Handlers
  const handleAddTrustee = () => {
    if (isRosterLocked || trustees.length >= 9) return;
    const nextPos = trustees.length + 1;
    const newSlot = createNewTrusteeSlot(nextPos);
    newlyAddedIdRef.current = newSlot.id;
    setHasLocalTrusteeEdits(true);
    setTrustees((prev) => [...prev, newSlot]);
  };

  const handleUpdateTrusteeName = useCallback((id: string, name: string) => {
    setHasLocalTrusteeEdits(true);
    setTrustees((prev) => prev.map((t) => (t.id === id ? { ...t, name } : t)));
  }, []);

  const handleUpdateTrusteeEmail = useCallback((id: string, email: string) => {
    setHasLocalTrusteeEdits(true);
    setTrustees((prev) => prev.map((t) => (t.id === id ? { ...t, email } : t)));
  }, []);

  const handleRemoveTrustee = useCallback((id: string) => {
    setHasLocalTrusteeEdits(true);
    setTrustees((prev) => {
      const filtered = prev.filter((t) => t.id !== id);
      return filtered.map((t, idx) => ({ ...t, position: idx + 1, trustee_id: idx + 1 }));
    });
  }, []);

  // Validation calculations
  const emailCounts = trustees.reduce<Record<string, number>>((acc, t) => {
    const em = t.email.trim().toLowerCase();
    if (em) acc[em] = (acc[em] || 0) + 1;
    return acc;
  }, {});

  const isRosterValid =
    trustees.length >= 3 &&
    trustees.length <= 9 &&
    trustees.every((t) => t.name.trim().length > 0 && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(t.email.trim())) &&
    trustees.every((t) => emailCounts[t.email.trim().toLowerCase()] <= 1);

  const handleSaveDraftTrustees = async () => {
    if (!activeElectionId) return;
    if (trustees.length < 3 || trustees.length > 9) {
      setErrorMsg(`Please configure between 3 and 9 trustees (currently ${trustees.length}).`);
      return;
    }

    try {
      const payload = {
        election_id: activeElectionId,
        trustees: trustees.map((t, idx) => ({
          name: t.name.trim(),
          email: t.email.trim(),
          position: idx + 1,
        })),
        ceremony_window_minutes: ceremonyWindowMinutes,
      };

      const res = await fetch('/api/admin/trustees', {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (!res.ok) {
        const parsed = formatApiError(data);
        throw new Error(parsed.message);
      }

      setHasLocalTrusteeEdits(false);
      setMsg(data.message || `Saved draft roster of ${trustees.length} trustees.`);
      fetchTrustees(activeElectionId, true);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to save draft roster.');
    }
  };

  const handleSendInvitations = async () => {
    setIsInviting(true);
    setErrorMsg(null);
    setMsg(null);

    try {
      // First save the current roster draft
      const saveRes = await fetch('/api/admin/trustees', {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          election_id: activeElectionId,
          trustees: trustees.map((t, idx) => ({
            name: t.name.trim(),
            email: t.email.trim(),
            position: idx + 1,
          })),
          ceremony_window_minutes: ceremonyWindowMinutes,
        }),
      });
      const saveData = await saveRes.json();
      if (!saveRes.ok) {
        const parsed = formatApiError(saveData);
        throw new Error(parsed.message);
      }

      // Dispatch invitations
      const res = await fetch('/api/admin/trustees/invite', {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          election_id: activeElectionId,
          portal_base_url: window.location.origin,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        const parsed = formatApiError(data);
        throw new Error(parsed.message);
      }

      setHasLocalTrusteeEdits(false);
      setMsg(data.message || `Dispatched invitations to all ${trustees.length} trustees.`);
      setShowInviteModal(false);
      fetchTrustees(activeElectionId, true);
      fetchStatus(activeElectionId);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to dispatch invitations.');
    } finally {
      setIsInviting(false);
    }
  };

  const handleReissueCodes = async () => {
    if (!reissuePassword.trim()) {
      setErrorMsg('Please enter administrator password to authorize code reissue.');
      return;
    }

    setIsReissuing(true);
    setErrorMsg(null);
    try {
      const res = await fetch('/api/admin/trustees/reissue', {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          election_id: activeElectionId,
          admin_password: reissuePassword.trim(),
          portal_base_url: window.location.origin,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        const parsed = formatApiError(data);
        throw new Error(parsed.message);
      }

      setMsg(data.message || 'All old codes invalidated and new invitations dispatched.');
      setShowReissueModal(false);
      setReissuePassword('');
      fetchTrustees(activeElectionId, true);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to reissue codes.');
    } finally {
      setIsReissuing(false);
    }
  };

  const handlePublishResults = async () => {
    setIsPublishing(true);
    setErrorMsg(null);
    setMsg(null);

    try {
      const res = await fetch('/api/admin/results/publish', {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ election_id: activeElectionId }),
      });

      const data = await res.json();
      if (!res.ok) {
        const parsed = formatApiError(data);
        throw new Error(parsed.message);
      }

      setMsg(data.message || 'Election results decrypted and published to public ledger.');
      fetchTrustees(activeElectionId, true);
      fetchStatus(activeElectionId);
      fetchPublishedResults(activeElectionId);
      if (onStatusChange) onStatusChange();
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to publish results.');
    } finally {
      setIsPublishing(false);
    }
  };

  const handleDevResetData = async () => {
    setIsResetting(true);
    try {
      const res = await fetch('/api/admin/reset', {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ election_id: activeElectionId }),
      });
      if (res.ok) {
        setMsg('Demo test data reset to clean state.');
        setShowResetConfirm(false);
        setHasLocalTrusteeEdits(false);
        fetchElectionsList();
        if (activeElectionId) {
          fetchStatus(activeElectionId);
          fetchTrustees(activeElectionId, true);
          fetchVoterRoll(activeElectionId);
        }
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to reset demo data.');
    } finally {
      setIsResetting(false);
    }
  };

  // If currently on Create Election screen
  if (isCreatingElection) {
    return (
      <div className="min-h-screen bg-ink text-on-ink">
        <CreateElection
          onSuccess={handleElectionCreated}
          onCancel={() => {
            setIsCreatingElection(false);
            setEditingElection(null);
          }}
          editElection={editingElection}
        />
      </div>
    );
  }

  // Election switcher options
  const electionOptions = electionList.map((el) => ({
    value: el.election_id,
    label: el.title,
    badge: el.status,
    description: `${el.registered_voters || 0} voters • ${el.formatted_window || 'No schedule'}`,
  }));

  return (
    <div className="min-h-screen bg-ink text-on-ink flex flex-col md:flex-row">
      {/* SIDEBAR */}
      <aside className="w-full md:w-64 bg-ink-2 border-r border-ink-3 p-4 flex flex-col justify-between">
        <div>
          {/* Brand */}
          <div className="flex items-center gap-2.5 px-3 py-3 mb-4 border-b border-ink-3">
            <span className="w-2 h-2 rounded-full bg-accent" />
            <span className="font-display font-bold text-lg tracking-tight text-white">{APP_NAME}</span>
            <span className="text-[10px] font-mono text-on-ink/50 ml-auto uppercase border border-ink-3 px-1 rounded">
              Console
            </span>
          </div>

          {/* Active Election Switcher */}
          <div className="px-1 mb-6">
            <label className="block text-[10px] font-mono text-on-ink/50 uppercase mb-1">Active Election</label>
            {electionList.length === 0 ? (
              <div className="p-2.5 bg-ink rounded border border-ink-3 text-xs text-on-ink/60 flex items-center justify-between">
                <span>No elections</span>
                <button
                  type="button"
                  onClick={() => setIsCreatingElection(true)}
                  className="text-accent hover:underline font-mono text-[11px]"
                >
                  Create
                </button>
              </div>
            ) : electionList.length === 1 ? (
              <div className="p-2.5 bg-ink rounded border border-ink-3 text-xs">
                <div className="font-semibold text-white truncate">{electionList[0].title}</div>
                <div className="text-[10px] text-on-ink/50 font-mono mt-0.5">{electionList[0].status}</div>
              </div>
            ) : (
              <CustomSelect
                options={electionOptions}
                value={activeElectionId}
                onChange={handleElectionChange}
                variant="dark"
              />
            )}
          </div>

          {/* Nav Links */}
          <nav className="space-y-1">
            <button
              type="button"
              onClick={() => setActiveSection('elections')}
              className={`w-full flex items-center gap-3 px-3 py-2 text-xs rounded font-medium transition ${
                activeSection === 'elections' ? 'bg-ink text-white border border-ink-3' : 'text-on-ink/70 hover:text-white hover:bg-ink/50'
              }`}
            >
              <Vote className="w-4 h-4" />
              <span>Elections</span>
              {/* Only show badge if multiple elections exist */}
              <span className="ml-auto text-[10px] font-mono bg-ink px-1.5 py-0.5 rounded text-on-ink/60 border border-ink-3">
                {electionList.filter((el) => el.status !== 'ARCHIVED').length}
              </span>
            </button>

            <button
              type="button"
              onClick={() => changeSection('overview')}
              className={`w-full flex items-center gap-3 px-3 py-2 text-xs rounded font-medium transition ${
                activeSection === 'overview' ? 'bg-ink text-white border border-ink-3' : 'text-on-ink/70 hover:text-white hover:bg-ink/50'
              }`}
            >
              <LayoutDashboard className="w-4 h-4" />
              <span>Overview</span>
            </button>

            <button
              type="button"
              onClick={() => changeSection('trustees')}
              className={`w-full flex items-center gap-3 px-3 py-2 text-xs rounded font-medium transition ${
                activeSection === 'trustees' ? 'bg-ink text-white border border-ink-3' : 'text-on-ink/70 hover:text-white hover:bg-ink/50'
              }`}
            >
              <KeyRound className="w-4 h-4" />
              <span>Trustee Portal</span>
              {isRosterLocked && (
                <span className="ml-auto text-[9px] font-mono bg-emerald-950 text-emerald-300 px-1 py-0.5 rounded border border-emerald-800">
                  Invited
                </span>
              )}
            </button>

            <button
              type="button"
              onClick={() => changeSection('schedule')}
              className={`w-full flex items-center gap-3 px-3 py-2 text-xs rounded font-medium transition ${
                activeSection === 'schedule' ? 'bg-ink text-white border border-ink-3' : 'text-on-ink/70 hover:text-white hover:bg-ink/50'
              }`}
            >
              <Calendar className="w-4 h-4" />
              <span>Voting Schedule</span>
            </button>

            <button
              type="button"
              onClick={() => changeSection('voting-control')}
              className={`w-full flex items-center gap-3 px-3 py-2 text-xs rounded font-medium transition ${
                activeSection === 'voting-control' ? 'bg-ink text-white border border-ink-3' : 'text-on-ink/70 hover:text-white hover:bg-ink/50'
              }`}
            >
              <Sliders className="w-4 h-4" />
              <span>Voting Control</span>
              {isOpen && <span className="ml-auto w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />}
            </button>

            <button
              type="button"
              onClick={() => changeSection('tally-results')}
              className={`w-full flex items-center gap-3 px-3 py-2 text-xs rounded font-medium transition ${
                activeSection === 'tally-results' ? 'bg-ink text-white border border-ink-3' : 'text-on-ink/70 hover:text-white hover:bg-ink/50'
              }`}
            >
              <BarChart3 className="w-4 h-4" />
              <span>Tally & Results</span>
              {(status === 'CLOSED' || status === 'COMPLETED') && (
                <span className="ml-auto text-[9px] font-mono bg-blue-950 text-blue-300 px-1 py-0.5 rounded border border-blue-800">
                  {status}
                </span>
              )}
            </button>

            <button
              type="button"
              onClick={() => changeSection('voter-roll')}
              className={`w-full flex items-center gap-3 px-3 py-2 text-xs rounded font-medium transition ${
                activeSection === 'voter-roll' ? 'bg-ink text-white border border-ink-3' : 'text-on-ink/70 hover:text-white hover:bg-ink/50'
              }`}
            >
              <Users className="w-4 h-4" />
              <span>Voter Roll</span>
              {voterRoll.length > 0 && (
                <span className="ml-auto text-[10px] font-mono bg-ink px-1.5 py-0.5 rounded text-on-ink/60 border border-ink-3">
                  {voterRoll.length}
                </span>
              )}
            </button>

            <button
              type="button"
              onClick={() => changeSection('audit-log')}
              className={`w-full flex items-center gap-3 px-3 py-2 text-xs rounded font-medium transition ${
                activeSection === 'audit-log' ? 'bg-ink text-white border border-ink-3' : 'text-on-ink/70 hover:text-white hover:bg-ink/50'
              }`}
            >
              <Shield className="w-4 h-4" />
              <span>Audit Ledger</span>
            </button>

            <button
              type="button"
              onClick={() => changeSection('settings')}
              className={`w-full flex items-center gap-3 px-3 py-2 text-xs rounded font-medium transition ${
                activeSection === 'settings' ? 'bg-ink text-white border border-ink-3' : 'text-on-ink/70 hover:text-white hover:bg-ink/50'
              }`}
            >
              <SettingsIcon className="w-4 h-4" />
              <span>Settings</span>
            </button>
          </nav>
        </div>

        {/* Bottom user & dev reset bar */}
        <div className="pt-4 border-t border-ink-3 space-y-2">
          <button
            type="button"
            onClick={() => setShowResetConfirm(true)}
            className="w-full text-left px-3 py-1.5 text-[11px] font-mono text-on-ink/40 hover:text-amber-400 transition flex items-center gap-1.5"
            title="DEV Reset Demo Data"
          >
            <RotateCcw className="w-3 h-3" /> Reset Demo Data
          </button>
          <div className="flex items-center justify-between px-3 py-1 text-xs">
            <span className="font-mono text-on-ink/50 truncate">admin@system</span>
            <button
              type="button"
              onClick={onLogout}
              className="text-on-ink/60 hover:text-red-400 transition flex items-center gap-1 font-mono text-[11px]"
              title="Sign Out"
            >
              <LogOut className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </aside>

      {/* MAIN CONTENT AREA */}
      <main className="flex-1 p-6 sm:p-10 max-w-6xl overflow-y-auto">
        {/* Email Delivery Warning Banner */}
        {emailDeliveryWarning && (
          <div className="mb-6 p-4 rounded bg-amber-950/80 border border-amber-700 text-amber-200 text-xs flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0" />
              <span>
                Emails are not being delivered: email settings are missing or failing. See SMTP configuration in README.md.
              </span>
            </div>
            <span className="text-[10px] font-mono uppercase bg-amber-900/60 px-2 py-0.5 rounded border border-amber-700">
              SMTP Alert
            </span>
          </div>
        )}

        {/* Feedback alerts */}
        {msg && (
          <div className="mb-6 p-4 rounded bg-emerald-950/80 border border-emerald-700 text-emerald-200 text-xs flex items-center justify-between">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
              <span>{msg}</span>
            </div>
            <button type="button" onClick={() => setMsg(null)} className="text-emerald-400 hover:text-white text-xs">
              Dismiss
            </button>
          </div>
        )}

        {errorMsg && (
          <div className="mb-6 p-4 rounded bg-red-950/80 border border-red-800 text-red-200 text-xs flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0" />
              <span>{errorMsg}</span>
            </div>
            <button type="button" onClick={() => setErrorMsg(null)} className="text-red-400 hover:text-white text-xs">
              Dismiss
            </button>
          </div>
        )}

        {/* SECTION: ELECTIONS LIST */}
        {activeSection === 'elections' && (
          <div>
            <div className="mb-8 border-b border-ink-3 pb-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <span className="text-[11px] font-mono uppercase tracking-widest text-on-ink/50">Elections Directory</span>
                <h1 className="font-display text-2xl font-bold text-white mt-1">Managed Elections</h1>
              </div>
              <button
                type="button"
                onClick={() => setIsCreatingElection(true)}
                className="px-4 py-2 bg-on-ink text-ink font-semibold rounded text-xs font-mono uppercase tracking-wider hover:bg-white transition flex items-center gap-1.5 self-start"
              >
                <Plus className="w-3.5 h-3.5" /> Create Election
              </button>
            </div>

            {electionList.length === 0 ? (
              <div className="p-12 text-center bg-ink-2 border border-ink-3 rounded-xl">
                <Vote className="w-10 h-10 text-on-ink/30 mx-auto mb-3" />
                <h3 className="font-display text-base font-bold text-white mb-1">No election yet</h3>
                <p className="text-xs text-on-ink/60 max-w-sm mx-auto mb-6">
                  Create your first election to begin configuring candidates, trustees, and cryptographic voting windows.
                </p>
                <button
                  type="button"
                  onClick={() => setIsCreatingElection(true)}
                  className="px-5 py-2.5 bg-on-ink text-ink font-semibold rounded text-xs font-mono uppercase tracking-wider hover:bg-white transition inline-flex items-center gap-1.5"
                >
                  <Plus className="w-3.5 h-3.5" /> Create Election
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-4">
                {electionList.map((el) => {
                  const isSelected = el.election_id === activeElectionId;
                  return (
                    <div
                      key={el.election_id}
                      className={`p-5 rounded-lg border transition ${
                        isSelected ? 'bg-ink-2 border-accent/70 shadow-lg' : 'bg-ink-2/60 border-ink-3 hover:border-on-ink/30'
                      }`}
                    >
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-3">
                        <div>
                          <div className="flex items-center gap-2">
                            <h3 className="font-display text-lg font-bold text-white">{el.title}</h3>
                            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-ink border border-ink-3 text-on-ink/70">
                              {el.status}
                            </span>
                            {isSelected && (
                              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-accent/20 border border-accent/40 text-accent font-semibold">
                                ACTIVE
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-on-ink/50 font-mono mt-0.5">
                            Timezone: {el.timezone}
                            {el.description ? ` • ${el.description}` : ''}
                          </p>
                        </div>
                        <div className="flex items-center gap-2">
                          {!isSelected && (
                            <button
                              type="button"
                              onClick={() => handleElectionChange(el.election_id)}
                              className="px-3 py-1.5 bg-ink text-xs font-mono text-white border border-ink-3 rounded hover:bg-ink-3"
                            >
                              Switch To
                            </button>
                          )}
                          {['REGISTRATION', 'SETUP'].includes(el.status) && (
                            <button
                              type="button"
                              onClick={() => {
                                setEditingElection(el);
                                setIsCreatingElection(true);
                              }}
                              className="px-3 py-1.5 bg-ink text-xs font-mono text-white border border-ink-3 rounded hover:bg-ink-3"
                            >
                              Edit
                            </button>
                          )}
                          {el.status !== 'ARCHIVED' && (
                            <button
                              type="button"
                              onClick={() => handleArchiveElection(el.election_id)}
                              className="px-3 py-1.5 bg-ink text-xs font-mono text-on-ink/80 border border-ink-3 rounded hover:bg-ink-3"
                            >
                              Archive
                            </button>
                          )}
                          <button
                            type="button"
                            onClick={() => {
                              setPendingDelete({
                                election_id: el.election_id,
                                title: el.title,
                                registered_voters: el.registered_voters || 0,
                                ballots_cast: el.ballots_cast || 0,
                              });
                              setDeleteStep(1);
                            }}
                            className="px-3 py-1.5 bg-ink text-xs font-mono text-red-300 border border-ink-3 rounded hover:bg-ink-3"
                          >
                            Delete
                          </button>
                        </div>
                      </div>

                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono text-on-ink/70 pt-3 border-t border-ink-3/60">
                        <div>Voters: <span className="text-white font-bold">{el.registered_voters}</span></div>
                        <div>Ballots: <span className="text-white font-bold">{el.ballots_cast}</span></div>
                        <div>Trustees: <span className="text-white font-bold">{el.trustees_count}</span></div>
                        <div>Window: <span className="text-white">{el.formatted_window}</span></div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* SECTION: OVERVIEW WITH SETUP CHECKLIST */}
        {activeSection === 'overview' && (
          <div>
            {!activeElectionId ? (
              <div className="p-12 text-center bg-ink-2 border border-ink-3 rounded-xl">
                <Vote className="w-10 h-10 text-on-ink/30 mx-auto mb-3" />
                <h3 className="font-display text-base font-bold text-white mb-1">No election selected</h3>
                <p className="text-xs text-on-ink/60 max-w-sm mx-auto mb-6">
                  Please create or select an election to begin administration.
                </p>
                <button
                  type="button"
                  onClick={() => setIsCreatingElection(true)}
                  className="px-5 py-2.5 bg-on-ink text-ink font-semibold rounded text-xs font-mono uppercase tracking-wider hover:bg-white transition"
                >
                  Create Election
                </button>
              </div>
            ) : (
              <div>
                <div className="mb-8 border-b border-ink-3 pb-4 flex items-center justify-between">
                  <div>
                    <span className="text-[11px] font-mono uppercase tracking-widest text-on-ink/50">Dashboard</span>
                    <h1 className="font-display text-2xl font-bold text-white mt-1">{electionTitle || activeElectionId}</h1>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`w-2.5 h-2.5 rounded-full ${isOpen ? 'bg-emerald-500 animate-pulse' : 'bg-amber-500'}`} />
                    <span className="text-sm font-bold text-white font-mono">{status}</span>
                  </div>
                </div>

                {/* SETUP CHECKLIST */}
                <div className="border border-ink-3 bg-ink-2 rounded-xl p-6 mb-8 shadow-xl">
                  <h3 className="font-display text-base font-bold text-white mb-1">Election Setup Checklist</h3>
                  <p className="text-xs text-on-ink/60 mb-5">
                    Follow these required operational steps to securely launch and validate your election.
                  </p>

                  <div className="space-y-3">
                    {/* Step 1: Election Created */}
                    <div className="flex items-center justify-between p-3.5 bg-ink rounded-lg border border-ink-3">
                      <div className="flex items-center gap-3">
                        <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                        <div>
                          <div className="text-xs font-semibold text-white">1. Election Created</div>
                          <div className="text-[11px] text-on-ink/50 font-mono">Title and candidates initialized</div>
                        </div>
                      </div>
                      <span className="text-[10px] font-mono bg-emerald-950 text-emerald-300 px-2 py-0.5 rounded border border-emerald-800">
                        DONE
                      </span>
                    </div>

                    {/* Step 2: Add Trustees & Send Invitations */}
                    <div className="flex items-center justify-between p-3.5 bg-ink rounded-lg border border-ink-3">
                      <div className="flex items-center gap-3">
                        <span className={`w-4 h-4 rounded-full flex items-center justify-center text-[10px] font-bold ${
                          invitationsSentAt ? 'bg-emerald-500 text-ink' : 'bg-ink-3 text-on-ink'
                        }`}>
                          2
                        </span>
                        <div>
                          <div className="text-xs font-semibold text-white">2. Add Trustees & Send Invitations</div>
                          <div className="text-[11px] text-on-ink/50 font-mono">
                            {invitationsSentAt ? `${trustees.length} trustees invited • Keys generated` : 'Configure 3 to 9 trustees and dispatch secret code shares'}
                          </div>
                        </div>
                      </div>
                      {invitationsSentAt ? (
                        <span className="text-[10px] font-mono bg-emerald-950 text-emerald-300 px-2 py-0.5 rounded border border-emerald-800">
                          DONE
                        </span>
                      ) : (
                        <button
                          type="button"
                          onClick={() => setActiveSection('trustees')}
                          className="px-3 py-1 bg-ink-2 text-xs font-mono text-on-ink hover:text-white border border-ink-3 rounded"
                        >
                          Configure →
                        </button>
                      )}
                    </div>

                    {/* Step 3: Set Voting Schedule */}
                    <div className="flex items-center justify-between p-3.5 bg-ink rounded-lg border border-ink-3">
                      <div className="flex items-center gap-3">
                        <span className={`w-4 h-4 rounded-full flex items-center justify-center text-[10px] font-bold ${
                          formattedWindow !== 'Dates to be announced' ? 'bg-emerald-500 text-ink' : 'bg-ink-3 text-on-ink'
                        }`}>
                          3
                        </span>
                        <div>
                          <div className="text-xs font-semibold text-white">3. Set Voting Schedule</div>
                          <div className="text-[11px] text-on-ink/50 font-mono">{formattedWindow}</div>
                        </div>
                      </div>
                      {formattedWindow !== 'Dates to be announced' ? (
                        <span className="text-[10px] font-mono bg-emerald-950 text-emerald-300 px-2 py-0.5 rounded border border-emerald-800">
                          SET
                        </span>
                      ) : (
                        <button
                          type="button"
                          onClick={() => setActiveSection('schedule')}
                          className="px-3 py-1 bg-ink-2 text-xs font-mono text-on-ink hover:text-white border border-ink-3 rounded"
                        >
                          Set Dates →
                        </button>
                      )}
                    </div>

                    {/* Step 4: Open Voting */}
                    <div className="flex items-center justify-between p-3.5 bg-ink rounded-lg border border-ink-3">
                      <div className="flex items-center gap-3">
                        <span className={`w-4 h-4 rounded-full flex items-center justify-center text-[10px] font-bold ${
                          isOpen ? 'bg-emerald-500 text-ink' : 'bg-ink-3 text-on-ink'
                        }`}>
                          4
                        </span>
                        <div>
                          <div className="text-xs font-semibold text-white">4. Open Voting</div>
                          <div className="text-[11px] text-on-ink/50 font-mono">
                            {isOpen ? 'Ballot box is open' : 'Requires trustee invitations sent'}
                          </div>
                        </div>
                      </div>
                      {isOpen ? (
                        <span className="text-[10px] font-mono bg-emerald-950 text-emerald-300 px-2 py-0.5 rounded border border-emerald-800">
                          ACTIVE
                        </span>
                      ) : (
                        <button
                          type="button"
                          onClick={() => setActiveSection('voting-control')}
                          className="px-3 py-1 bg-ink-2 text-xs font-mono text-on-ink hover:text-white border border-ink-3 rounded"
                        >
                          Voting Control →
                        </button>
                      )}
                    </div>

                    {/* Step 5: Close and Validate */}
                    <div className="flex items-center justify-between p-3.5 bg-ink rounded-lg border border-ink-3">
                      <div className="flex items-center gap-3">
                        <span className={`w-4 h-4 rounded-full flex items-center justify-center text-[10px] font-bold ${
                          status === 'COMPLETED' ? 'bg-emerald-500 text-ink' : 'bg-ink-3 text-on-ink'
                        }`}>
                          5
                        </span>
                        <div>
                          <div className="text-xs font-semibold text-white">5. Close & Validate</div>
                          <div className="text-[11px] text-on-ink/50 font-mono">
                            {status === 'COMPLETED' ? 'Results tallied & published' : 'Trustees perform unlock ceremony to decrypt tally'}
                          </div>
                        </div>
                      </div>
                      {status === 'COMPLETED' ? (
                        <span className="text-[10px] font-mono bg-emerald-950 text-emerald-300 px-2 py-0.5 rounded border border-emerald-800">
                          COMPLETED
                        </span>
                      ) : (
                        <button
                          type="button"
                          onClick={() => setActiveSection('trustees')}
                          className="px-3 py-1 bg-ink-2 text-xs font-mono text-on-ink hover:text-white border border-ink-3 rounded"
                        >
                          Ceremony →
                        </button>
                      )}
                    </div>
                  </div>
                </div>

                {/* METRICS CARDS */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
                  <div className="bg-ink-2 border border-ink-3 rounded-lg p-5">
                    <span className="text-[11px] font-mono text-on-ink/50 uppercase block mb-1">Registered Voters</span>
                    <span className="font-display text-2xl font-bold text-white block mt-1">{voterRoll.length}</span>
                  </div>

                  <div className="bg-ink-2 border border-ink-3 rounded-lg p-5">
                    <span className="text-[11px] font-mono text-on-ink/50 uppercase block mb-1">Ballots Cast</span>
                    <span className="font-display text-2xl font-bold text-white block mt-1">{totalBallots}</span>
                  </div>

                  <div className="bg-ink-2 border border-ink-3 rounded-lg p-5">
                    <span className="text-[11px] font-mono text-on-ink/50 uppercase block mb-1">Trustees</span>
                    <span className="font-display text-2xl font-bold text-white block mt-1">{trustees.length}</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* SECTION: TRUSTEE PORTAL */}
        {activeSection === 'trustees' && (
          <div>
            {!activeElectionId ? (
              <div className="p-12 text-center bg-ink-2 border border-ink-3 rounded-xl">
                <KeyRound className="w-10 h-10 text-on-ink/30 mx-auto mb-3" />
                <h3 className="font-display text-base font-bold text-white mb-1">No Election Selected</h3>
                <p className="text-xs text-on-ink/60 mb-6">Create an election to configure the Trustee Portal.</p>
                <button
                  type="button"
                  onClick={() => setIsCreatingElection(true)}
                  className="px-5 py-2.5 bg-on-ink text-ink font-semibold rounded text-xs font-mono uppercase tracking-wider hover:bg-white"
                >
                  Create Election
                </button>
              </div>
            ) : (
              <div>
                <div className="mb-8 border-b border-ink-3 pb-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div>
                    <span className="text-[11px] font-mono uppercase tracking-widest text-on-ink/50">Threshold Governance</span>
                    <h1 className="font-display text-2xl font-bold text-white mt-1">Trustee Portal</h1>
                  </div>

                  {isRosterLocked && !resultsPublishedAt && (
                    <button
                      type="button"
                      onClick={() => setShowReissueModal(true)}
                      className="px-3.5 py-2 bg-ink border border-ink-3 text-xs font-mono text-amber-400 hover:text-white rounded flex items-center gap-1.5 self-start"
                    >
                      <RotateCcw className="w-3.5 h-3.5" /> Reissue Codes
                    </button>
                  )}
                </div>

                {/* ROSTER TABLE */}
                <div className="bg-ink-2 border border-ink-3 rounded-lg p-6 mb-8">
                  <div className="flex items-center justify-between mb-4">
                    <div>
                      <h3 className="font-display text-base font-bold text-white">Trustee Roster</h3>
                      <p className="text-xs text-on-ink/60 mt-0.5">
                        {isRosterLocked
                          ? 'Roster and keys are locked. Each trustee holds an independent 80-bit code.'
                          : 'Configure 3 to 9 trustees. Order determines sequential ceremony entry position.'}
                      </p>
                    </div>
                    {isRosterLocked && (
                      <span className="px-2.5 py-1 rounded bg-emerald-950 border border-emerald-800 text-emerald-300 font-mono text-[11px] flex items-center gap-1">
                        <CheckCircle2 className="w-3.5 h-3.5" /> Invitations Dispatched
                      </span>
                    )}
                  </div>

                  {trustees.length === 0 ? (
                    <div className="p-8 text-center bg-ink border border-ink-3 rounded-lg mb-6">
                      <p className="text-xs text-on-ink/60 mb-4 font-mono">
                        No trustees added yet. Click below to add trustee slots (minimum 3 required).
                      </p>
                      {!isRosterLocked && (
                        <button
                          type="button"
                          onClick={handleAddTrustee}
                          className="px-4 py-2 bg-on-ink text-ink font-semibold rounded text-xs font-mono uppercase tracking-wider hover:bg-white inline-flex items-center gap-1.5"
                        >
                          <Plus className="w-3.5 h-3.5" /> Add Trustee
                        </button>
                      )}
                    </div>
                  ) : (
                    <div className="space-y-3 mb-6">
                      {trustees.map((t, index) => (
                        <TrusteeRow
                          key={t.id}
                          trustee={t}
                          index={index}
                          isRosterLocked={isRosterLocked}
                          isLast={index === trustees.length - 1}
                          onUpdateName={handleUpdateTrusteeName}
                          onUpdateEmail={handleUpdateTrusteeEmail}
                          onRemove={handleRemoveTrustee}
                          onAddNext={handleAddTrustee}
                          nameRef={(el) => {
                            nameInputRefs.current[t.id] = el;
                          }}
                          emailRef={(el) => {
                            emailInputRefs.current[t.id] = el;
                          }}
                          duplicateEmail={emailCounts[t.email.trim().toLowerCase()] > 1}
                        />
                      ))}
                    </div>
                  )}

                  {!isRosterLocked && (
                    <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-4 border-t border-ink-3">
                      <div className="flex items-center gap-2">
                        {trustees.length < 9 && (
                          <button
                            type="button"
                            onClick={handleAddTrustee}
                            className="px-3 py-1.5 bg-ink border border-ink-3 rounded text-xs text-on-ink hover:text-white flex items-center gap-1 font-mono"
                          >
                            <Plus className="w-3.5 h-3.5" /> Add Trustee
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={handleSaveDraftTrustees}
                          className="px-3 py-1.5 bg-ink border border-ink-3 rounded text-xs text-on-ink/70 hover:text-white font-mono"
                        >
                          Save Draft
                        </button>
                      </div>

                      <div className="flex items-center gap-4">
                        <div className="flex items-center gap-2 text-xs font-mono">
                          <label className="text-on-ink/60">Round window:</label>
                          <input
                            type="number"
                            min={2}
                            max={15}
                            value={ceremonyWindowMinutes}
                            onChange={(e) => setCeremonyWindowMinutes(Number(e.target.value))}
                            className="w-16 px-2 py-1 bg-ink text-white border border-ink-3 rounded text-xs font-mono"
                          />
                          <span className="text-on-ink/50">min</span>
                        </div>

                        <button
                          type="button"
                          disabled={!isRosterValid}
                          onClick={() => setShowInviteModal(true)}
                          className="px-4 py-2 bg-on-ink text-ink font-semibold rounded text-xs font-mono uppercase tracking-wider hover:bg-white transition flex items-center gap-1.5 disabled:opacity-40"
                        >
                          <Send className="w-3.5 h-3.5" /> Send Invitations ({trustees.length})
                        </button>
                      </div>
                    </div>
                  )}

                  {!isRosterLocked && trustees.length > 0 && !isRosterValid && (
                    <div className="mt-3 text-[11px] font-mono text-on-ink/60 space-y-0.5">
                      {trustees.length < 3 && <div>• Minimum 3 trustees required (currently {trustees.length}).</div>}
                      {trustees.length > 9 && <div>• Maximum 9 trustees allowed (currently {trustees.length}).</div>}
                      {!trustees.every((t) => t.name.trim().length > 0) && <div>• All trustee names must be entered.</div>}
                      {!trustees.every((t) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(t.email.trim())) && <div>• All emails must be valid addresses.</div>}
                      {Object.values(emailCounts).some((c) => c > 1) && <div>• All trustee emails must be unique.</div>}
                    </div>
                  )}
                </div>

                {/* LIVE CEREMONY MONITOR */}
                {isRosterLocked && ceremonyMonitor && (
                  <div className="bg-ink-2 border border-ink-3 rounded-lg p-6">
                    <div className="flex items-center justify-between mb-4">
                      <div>
                        <h3 className="font-display text-base font-bold text-white">Unlock Ceremony Monitor</h3>
                        <p className="text-xs text-on-ink/60">
                          Real-time presence and sequential unlock verification state across all {trustees.length} trustees.
                        </p>
                      </div>
                      <span className="font-mono text-xs text-on-ink/50">
                        Status: <span className="text-white font-bold">{ceremonyMonitor.ceremony_state?.status || 'WAITING'}</span>
                      </span>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-6">
                      {(ceremonyMonitor.ceremony_state?.presence || []).map((p: any) => (
                        <div key={p.position} className="p-3 bg-ink border border-ink-3 rounded-lg text-xs font-mono">
                          <div className="flex items-center justify-between mb-1">
                            <span className="font-bold text-white">Trustee #{p.position}</span>
                            <span className={`w-2 h-2 rounded-full ${p.is_online ? 'bg-emerald-400' : 'bg-on-ink/20'}`} />
                          </div>
                          <div className="text-on-ink/60 truncate">{p.name}</div>
                          <div className="text-[10px] text-on-ink/40 mt-1">
                            {p.code_accepted ? '✓ Code Entered' : p.is_online ? 'Present' : 'Absent'}
                          </div>
                        </div>
                      ))}
                    </div>

                    {status === 'CLOSED' && ceremonyMonitor.approvals_count === trustees.length && !resultsPublishedAt && (
                      <div className="p-4 bg-emerald-950/40 border border-emerald-800 rounded-lg flex items-center justify-between">
                        <div>
                          <div className="text-xs font-bold text-emerald-300">All Trustees Approved Partial Decryptions</div>
                          <div className="text-[11px] text-emerald-200/70">The election tally is ready for final publication.</div>
                        </div>
                        <button
                          type="button"
                          onClick={handlePublishResults}
                          disabled={isPublishing}
                          className="px-4 py-2 bg-emerald-600 text-white font-semibold text-xs rounded hover:bg-emerald-500 font-mono"
                        >
                          {isPublishing ? 'Publishing...' : 'Publish Official Results'}
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* SECTION: SCHEDULE */}
        {activeSection === 'schedule' && (
          <div>
            {!activeElectionId ? (
              <div className="p-12 text-center bg-ink-2 border border-ink-3 rounded-xl">
                <Calendar className="w-10 h-10 text-on-ink/30 mx-auto mb-3" />
                <h3 className="font-display text-base font-bold text-white mb-1">No Election Selected</h3>
                <p className="text-xs text-on-ink/60 mb-6">Create an election before setting its voting schedule.</p>
                <button
                  type="button"
                  onClick={() => setIsCreatingElection(true)}
                  className="px-5 py-2.5 bg-on-ink text-ink font-semibold rounded text-xs font-mono uppercase tracking-wider hover:bg-white"
                >
                  Create Election
                </button>
              </div>
            ) : (
              <div>
                <div className="mb-8 border-b border-ink-3 pb-4">
                  <span className="text-[11px] font-mono uppercase tracking-widest text-on-ink/50">Timing Configuration</span>
                  <h1 className="font-display text-2xl font-bold text-white mt-1">Voting Schedule</h1>
                </div>

                <div className="bg-ink-2 border border-ink-3 rounded-lg p-6 max-w-xl">
                  {/* Timezone Info Note */}
                  <div className="p-3 bg-ink rounded border border-ink-3 mb-5 flex items-center justify-between text-xs font-mono">
                    <span className="text-on-ink/70">
                      Times are configured in <strong className="text-white">{timezoneStr}</strong>
                    </span>
                    <button
                      type="button"
                      onClick={() => setActiveSection('elections')}
                      className="text-accent hover:underline flex items-center gap-1 text-[11px]"
                    >
                      Election Settings <ExternalLink className="w-3 h-3" />
                    </button>
                  </div>

                  {scheduleWarning && (
                    <div className="mb-5 p-3 rounded bg-amber-950/80 border border-amber-700 text-amber-200 text-xs flex items-center gap-2">
                      <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0" />
                      <span>{scheduleWarning}</span>
                    </div>
                  )}

                  <div className="space-y-4 mb-6">
                    <div>
                      <label className="block text-[11px] font-mono text-on-ink/70 uppercase mb-1.5">
                        Voting Start ({timezoneStr})
                      </label>
                      <input
                        type="datetime-local"
                        value={scheduledStart}
                        onChange={(e) => {
                          setScheduledStart(e.target.value);
                          setScheduleWarning(null);
                        }}
                        className="w-full px-3.5 py-2 bg-ink text-white border border-ink-3 rounded text-xs font-mono focus:outline-none focus:border-on-ink"
                      />
                    </div>

                    <div>
                      <label className="block text-[11px] font-mono text-on-ink/70 uppercase mb-1.5">
                        Voting End ({timezoneStr})
                      </label>
                      <input
                        type="datetime-local"
                        value={scheduledEnd}
                        onChange={(e) => setScheduledEnd(e.target.value)}
                        className="w-full px-3.5 py-2 bg-ink text-white border border-ink-3 rounded text-xs font-mono focus:outline-none focus:border-on-ink"
                      />
                    </div>
                  </div>

                  <div className="p-3 bg-ink border border-ink-3 rounded text-xs font-mono mb-6 text-on-ink/70">
                    <div>Current Announced Window:</div>
                    <div className="text-white font-bold mt-1">{formattedWindow}</div>
                  </div>

                  <button
                    type="button"
                    onClick={handlePreAnnounceClick}
                    className="w-full py-2.5 bg-on-ink text-ink font-semibold rounded text-xs font-mono uppercase tracking-wider hover:bg-white transition"
                  >
                    Save & Announce Schedule
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* SECTION: VOTING CONTROL */}
        {activeSection === 'voting-control' && (
          <div>
            {!activeElectionId ? (
              <div className="p-12 text-center bg-ink-2 border border-ink-3 rounded-xl">
                <Sliders className="w-10 h-10 text-on-ink/30 mx-auto mb-3" />
                <h3 className="font-display text-base font-bold text-white mb-1">No Election Selected</h3>
                <p className="text-xs text-on-ink/60 mb-6">Create an election before managing voting lifecycle.</p>
                <button
                  type="button"
                  onClick={() => setIsCreatingElection(true)}
                  className="px-5 py-2.5 bg-on-ink text-ink font-semibold rounded text-xs font-mono uppercase tracking-wider hover:bg-white"
                >
                  Create Election
                </button>
              </div>
            ) : (
              <div>
                <div className="mb-8 border-b border-ink-3 pb-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div>
                    <span className="text-[11px] font-mono uppercase tracking-widest text-on-ink/50">Lifecycle State</span>
                    <h1 className="font-display text-2xl font-bold text-white mt-1">Voting Lifecycle Control</h1>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`px-2.5 py-1 rounded text-xs font-mono font-bold uppercase border ${
                      status === 'OPEN'
                        ? 'bg-emerald-950 text-emerald-300 border-emerald-800'
                        : status === 'CLOSED'
                        ? 'bg-blue-950 text-blue-300 border-blue-800'
                        : status === 'COMPLETED'
                        ? 'bg-purple-950 text-purple-300 border-purple-800'
                        : 'bg-amber-950 text-amber-300 border-amber-800'
                    }`}>
                      Current Status: {status}
                    </span>
                  </div>
                </div>

                {/* SINGLE STATE-DRIVEN PANEL */}
                <div className="bg-ink-2 border border-ink-3 rounded-xl p-8 max-w-2xl">
                  {status === 'REGISTRATION' && (
                    <div className="space-y-6">
                      <div className="flex items-start gap-4">
                        <div className="w-12 h-12 rounded-lg bg-emerald-950/60 border border-emerald-800 flex items-center justify-center flex-shrink-0 text-emerald-400">
                          <Unlock className="w-6 h-6" />
                        </div>
                        <div>
                          <h3 className="font-display text-lg font-bold text-white">Ballot Box Ready to Open</h3>
                          <p className="text-xs text-on-ink/70 mt-1 leading-relaxed">
                            Opening voting transitions the election from voter registration to active ballot collection. Server time-lock keys will be activated and registered voters can cast encrypted ballots.
                          </p>
                        </div>
                      </div>

                      <div className="p-4 bg-ink border border-ink-3 rounded-lg text-xs font-mono space-y-1.5 text-on-ink/80">
                        <div className="flex justify-between">
                          <span>Registered Voters:</span>
                          <span className="text-white font-bold">{voterRoll.length}</span>
                        </div>
                        <div className="flex justify-between">
                          <span>Trustee Invitations:</span>
                          <span className={invitationsSentAt ? 'text-emerald-400 font-bold' : 'text-amber-400 font-bold'}>
                            {invitationsSentAt ? 'Dispatched' : 'Pending (Required)'}
                          </span>
                        </div>
                      </div>

                      {!invitationsSentAt ? (
                        <div className="p-4 rounded-lg bg-amber-950/70 border border-amber-800 text-amber-200 text-xs flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0" />
                            <span>Trustee invitations must be sent from Trustee Portal before voting can be opened.</span>
                          </div>
                          <button
                            type="button"
                            onClick={() => setActiveSection('trustees')}
                            className="px-3 py-1 bg-amber-900 border border-amber-700 text-amber-100 rounded text-xs font-mono hover:bg-amber-800 flex-shrink-0"
                          >
                            Go to Trustees
                          </button>
                        </div>
                      ) : (
                        <button
                          type="button"
                          onClick={() => setShowOpenConfirmModal(true)}
                          className="w-full py-3 bg-emerald-600 text-white font-semibold rounded text-xs font-mono uppercase tracking-wider hover:bg-emerald-500 transition shadow-lg flex items-center justify-center gap-2"
                        >
                          <Unlock className="w-4 h-4" />
                          <span>Open Voting Now</span>
                        </button>
                      )}
                    </div>
                  )}

                  {status === 'OPEN' && (
                    <div className="space-y-6">
                      <div className="flex items-start gap-4">
                        <div className="w-12 h-12 rounded-lg bg-red-950/60 border border-red-800 flex items-center justify-center flex-shrink-0 text-red-400">
                          <Lock className="w-6 h-6" />
                        </div>
                        <div>
                          <h3 className="font-display text-lg font-bold text-white">Ballot Box Currently Open</h3>
                          <p className="text-xs text-on-ink/70 mt-1 leading-relaxed">
                            Eligible voters are currently casting encrypted ballots on the public ledger. Closing voting will permanently seal the bulletin board and calculate homomorphic aggregates.
                          </p>
                        </div>
                      </div>

                      <div className="p-4 bg-ink border border-ink-3 rounded-lg text-xs font-mono space-y-1.5 text-on-ink/80">
                        <div className="flex justify-between">
                          <span>Ballots Cast on Ledger:</span>
                          <span className="text-emerald-400 font-bold">{totalBallots}</span>
                        </div>
                        <div className="flex justify-between">
                          <span>Active Registered Roll:</span>
                          <span className="text-white font-bold">{voterRoll.length}</span>
                        </div>
                      </div>

                      <button
                        type="button"
                        onClick={() => {
                          setCloseConfirmInput('');
                          setShowCloseConfirmModal(true);
                        }}
                        className="w-full py-3 bg-red-600 text-white font-semibold rounded text-xs font-mono uppercase tracking-wider hover:bg-red-500 transition shadow-lg flex items-center justify-center gap-2"
                      >
                        <Lock className="w-4 h-4" />
                        <span>Close Voting and Start Tally</span>
                      </button>
                    </div>
                  )}

                  {(status === 'CLOSED' || status === 'COMPLETED') && (
                    <div className="space-y-6">
                      <div className="flex items-start gap-4">
                        <div className="w-12 h-12 rounded-lg bg-blue-950/60 border border-blue-800 flex items-center justify-center flex-shrink-0 text-blue-400">
                          <CheckCircle2 className="w-6 h-6" />
                        </div>
                        <div>
                          <h3 className="font-display text-lg font-bold text-white">Voting Concluded & Sealed</h3>
                          <p className="text-xs text-on-ink/70 mt-1 leading-relaxed">
                            The ballot box is closed. The public bulletin board is sealed and trustee ceremony validation is {status === 'COMPLETED' ? 'published' : 'active'}.
                          </p>
                        </div>
                      </div>

                      <div className="p-4 bg-ink border border-ink-3 rounded-lg text-xs font-mono space-y-1.5 text-on-ink/80">
                        <div className="flex justify-between">
                          <span>Total Cast Ballots:</span>
                          <span className="text-white font-bold">{totalBallots}</span>
                        </div>
                        <div className="flex justify-between">
                          <span>Ceremony Status:</span>
                          <span className={status === 'COMPLETED' ? 'text-purple-400 font-bold' : 'text-blue-400 font-bold'}>
                            {status === 'COMPLETED' ? 'OFFICIAL RESULTS PUBLISHED' : 'CEREMONY IN PROGRESS'}
                          </span>
                        </div>
                      </div>

                      <button
                        type="button"
                        onClick={() => setActiveSection('tally-results')}
                        className="w-full py-3 bg-on-ink text-ink font-semibold rounded text-xs font-mono uppercase tracking-wider hover:bg-white transition flex items-center justify-center gap-2"
                      >
                        <BarChart3 className="w-4 h-4" />
                        <span>View Tally & Trustee Results</span>
                      </button>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* SECTION: TALLY & RESULTS */}
        {activeSection === 'tally-results' && (
          <div>
            {!activeElectionId ? (
              <div className="p-12 text-center bg-ink-2 border border-ink-3 rounded-xl">
                <BarChart3 className="w-10 h-10 text-on-ink/30 mx-auto mb-3" />
                <h3 className="font-display text-base font-bold text-white mb-1">No Election Selected</h3>
                <p className="text-xs text-on-ink/60 mb-6">Select an election to view tally and ceremony progress.</p>
              </div>
            ) : (
              <div>
                <div className="mb-8 border-b border-ink-3 pb-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div>
                    <span className="text-[11px] font-mono uppercase tracking-widest text-on-ink/50">Tally Governance</span>
                    <h1 className="font-display text-2xl font-bold text-white mt-1">Tally & Results Ceremony</h1>
                  </div>

                  {status === 'CLOSED' && ceremonyMonitor?.all_present && ceremonyMonitor?.all_approved && !resultsPublishedAt && (
                    <button
                      type="button"
                      onClick={handlePublishResults}
                      disabled={isPublishing}
                      className="px-4 py-2 bg-emerald-600 text-white font-semibold rounded text-xs font-mono uppercase tracking-wider hover:bg-emerald-500 transition flex items-center gap-1.5 self-start"
                    >
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      <span>{isPublishing ? 'Publishing...' : 'Publish Official Results'}</span>
                    </button>
                  )}
                </div>

                {/* ADMIN PREVIEW: DECRYPTED TALLY (VISIBLE TO ADMIN EVEN BEFORE TRUSTEES APPROVE) */}
                {(status === 'CLOSED' || status === 'COMPLETED') && !resultsPublishedAt && ceremonyMonitor?.preliminary_results && (
                  <div className="mb-8 p-6 bg-ink-2 border border-purple-800/60 rounded-xl shadow-xl max-w-4xl">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4 border-b border-ink-3 pb-4">
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <BarChart3 className="w-4 h-4 text-purple-400" />
                          <span className="text-[10px] font-mono uppercase tracking-widest text-purple-300 font-bold">
                            Admin Preliminary Tally (Confidential Preview)
                          </span>
                        </div>
                        <h2 className="font-display text-lg font-bold text-white">
                          Current Candidate Results
                        </h2>
                        <p className="text-xs text-on-ink/70 mt-1">
                          Visible to administrators for audit. <strong>Hidden from voters</strong> until trustees complete sequential certification and you click &quot;Publish Official Results&quot;.
                        </p>
                      </div>

                      <div className="text-left sm:text-right flex-shrink-0">
                        <span className="text-[10px] font-mono uppercase text-on-ink/50 block">Trustee Governance</span>
                        <span className={`text-xs font-mono font-bold px-2.5 py-1 rounded border inline-block mt-0.5 ${
                          ceremonyMonitor?.all_approved
                            ? 'bg-emerald-950 text-emerald-300 border-emerald-800'
                            : 'bg-amber-950 text-amber-300 border-amber-800'
                        }`}>
                          {ceremonyMonitor?.approvals_count ?? 0} / {ceremonyMonitor?.total_trustees ?? 0} TRUSTEES APPROVED
                        </span>
                      </div>
                    </div>

                    {(() => {
                      const entries = Object.entries(ceremonyMonitor.preliminary_results || {});
                      if (entries.length === 0) {
                        return (
                          <p className="text-xs font-mono text-on-ink/50">
                            Decrypted totals are not available yet.
                          </p>
                        );
                      }
                      const maxVotes = Math.max(...entries.map(([_, count]: [string, any]) => Number(count) || 0), 0);
                      const total = ceremonyMonitor.total_ballots || entries.reduce((acc, [_, v]) => acc + Number(v), 0) || 1;

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
                    })()}
                  </div>
                )}

                {/* 5-STEP VERTICAL STEPPER */}
                <div className="space-y-6 max-w-4xl">
                  {/* Step 1: Voting Closed */}
                  <div className={`p-6 rounded-xl border ${
                    status === 'CLOSED' || status === 'COMPLETED'
                      ? 'bg-ink-2 border-emerald-800/60'
                      : 'bg-ink/50 border-ink-3 opacity-60'
                  }`}>
                    <div className="flex items-start gap-4">
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center font-mono text-xs font-bold ${
                        status === 'CLOSED' || status === 'COMPLETED'
                          ? 'bg-emerald-600 text-white'
                          : 'bg-ink-3 text-on-ink/50'
                      }`}>
                        1
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center justify-between">
                          <h3 className="font-display text-base font-bold text-white">Ballot Box Sealed & Closed</h3>
                          <span className={`text-[10px] font-mono uppercase px-2 py-0.5 rounded border ${
                            status === 'CLOSED' || status === 'COMPLETED'
                              ? 'bg-emerald-950 text-emerald-300 border-emerald-800'
                              : 'bg-ink-3 text-on-ink/50 border-ink-3'
                          }`}>
                            {status === 'CLOSED' || status === 'COMPLETED' ? 'COMPLETED' : 'PENDING CLOSE'}
                          </span>
                        </div>
                        <p className="text-xs text-on-ink/60 mt-1">
                          Bulletin board head hash locked, receipt sequence permanently immutable.
                        </p>
                        {(status === 'CLOSED' || status === 'COMPLETED') && (() => {
                          const headHash = bulletinBoardHeadHash || (bulletinBoard.length > 0 ? bulletinBoard[bulletinBoard.length - 1].block_hash : '');
                          return (
                            <div className="mt-3 p-3 bg-ink rounded border border-ink-3 text-xs font-mono text-on-ink/70 flex flex-wrap items-center gap-4">
                              <span>Ballots Cast: <strong className="text-white">{totalBallots}</strong></span>
                              <div className="flex items-center gap-2">
                                <span>Bulletin Board Head:</span>
                                {totalBallots === 0 && !headHash ? (
                                  <span className="text-on-ink/50 italic">No ballots</span>
                                ) : (
                                  <div className="flex items-center gap-1.5">
                                    <strong className="text-accent truncate max-w-xs" title={headHash}>
                                      {headHash || '0x00000000'}
                                    </strong>
                                    {headHash && (
                                      <button
                                        type="button"
                                        onClick={() => {
                                          navigator.clipboard.writeText(headHash);
                                          setMsg('Bulletin board head hash copied to clipboard.');
                                        }}
                                        className="p-1 hover:text-white text-on-ink/50 transition"
                                        title="Copy Bulletin Board Head Hash"
                                      >
                                        <Copy className="w-3.5 h-3.5" />
                                      </button>
                                    )}
                                  </div>
                                )}
                              </div>
                            </div>
                          );
                        })()}
                      </div>
                    </div>
                  </div>

                  {/* Step 2: Encrypted Tally Computed */}
                  <div className={`p-6 rounded-xl border ${
                    status === 'CLOSED' || status === 'COMPLETED'
                      ? 'bg-ink-2 border-emerald-800/60'
                      : 'bg-ink/50 border-ink-3 opacity-60'
                  }`}>
                    <div className="flex items-start gap-4">
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center font-mono text-xs font-bold ${
                        status === 'CLOSED' || status === 'COMPLETED'
                          ? 'bg-emerald-600 text-white'
                          : 'bg-ink-3 text-on-ink/50'
                      }`}>
                        2
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center justify-between">
                          <h3 className="font-display text-base font-bold text-white">Homomorphic Aggregate Computed</h3>
                          <span className={`text-[10px] font-mono uppercase px-2 py-0.5 rounded border ${
                            status === 'CLOSED' || status === 'COMPLETED'
                              ? 'bg-emerald-950 text-emerald-300 border-emerald-800'
                              : 'bg-ink-3 text-on-ink/50 border-ink-3'
                          }`}>
                            {status === 'CLOSED' || status === 'COMPLETED' ? 'COMPLETED' : 'AWAITING CLOSE'}
                          </span>
                        </div>
                        <p className="text-xs text-on-ink/60 mt-1">
                          Product of ElGamal ciphertexts aggregated without decrypting individual voter ballots.
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* Step 3: Trustee Unlock Ceremony */}
                  <div className={`p-6 rounded-xl border ${
                    status === 'CLOSED' || status === 'COMPLETED'
                      ? 'bg-ink-2 border-ink-3'
                      : 'bg-ink/50 border-ink-3 opacity-60'
                  }`}>
                    <div className="flex items-start gap-4">
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center font-mono text-xs font-bold ${
                        ceremonyMonitor?.all_present
                          ? 'bg-emerald-600 text-white'
                          : status === 'CLOSED'
                          ? 'bg-amber-600 text-white'
                          : 'bg-ink-3 text-on-ink/50'
                      }`}>
                        3
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center justify-between">
                          <h3 className="font-display text-base font-bold text-white">All-Trustees Sequential Unlock Ceremony</h3>
                          <span className={`text-[10px] font-mono uppercase px-2 py-0.5 rounded border ${
                            ceremonyMonitor?.all_present
                              ? 'bg-emerald-950 text-emerald-300 border-emerald-800'
                              : status === 'CLOSED'
                              ? 'bg-amber-950 text-amber-300 border-amber-800'
                              : 'bg-ink-3 text-on-ink/50 border-ink-3'
                          }`}>
                            {ceremonyMonitor?.all_present ? 'ALL TRUSTEES ENTERED' : status === 'CLOSED' ? 'AWAITING TRUSTEES' : 'LOCKED'}
                          </span>
                        </div>
                        <p className="text-xs text-on-ink/60 mt-1 leading-relaxed">
                          Each trustee opens the link from their invitation email and enters their unique code when it is their turn. Secrets are strictly hidden from the admin console.
                        </p>

                        <div className="mt-3 flex items-center gap-3">
                          <button
                            type="button"
                            onClick={() => {
                              const ceremonyAddress = `${window.location.origin}/ceremony`;
                              navigator.clipboard.writeText(ceremonyAddress);
                              setMsg(`Trustee ceremony page address (${ceremonyAddress}) copied to clipboard.`);
                            }}
                            className="px-3 py-1.5 bg-ink border border-ink-3 hover:border-on-ink/50 text-white rounded text-xs font-mono flex items-center gap-1.5 transition"
                          >
                            <Copy className="w-3.5 h-3.5" />
                            <span>Copy trustee page address</span>
                          </button>
                        </div>

                        {/* Trustee Presence Slots */}
                        {status === 'CLOSED' && (
                          <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-3">
                            {trustees.map((t, idx) => {
                              const presence = ceremonyMonitor?.trustee_presence?.[t.position || idx + 1];
                              const isEntered = presence?.entered || t.has_approved;
                              const trusteeId = t.trustee_id || (idx + 1);
                              const isResendingThis = resendingTrusteeId === trusteeId;

                              return (
                                <div key={t.id} className="p-3 bg-ink border border-ink-3 rounded text-xs font-mono space-y-1.5">
                                  <div className="flex items-center justify-between text-on-ink/60">
                                    <span>Slot #{t.position || idx + 1}</span>
                                    <span className={isEntered ? 'text-emerald-400 font-bold' : 'text-amber-400'}>
                                      {isEntered ? 'ENTERED' : 'AWAITING'}
                                    </span>
                                  </div>
                                  <div className="font-semibold text-white truncate">{t.name || `Trustee ${idx + 1}`}</div>
                                  <div className="text-[10px] text-on-ink/40 truncate">{t.email}</div>
                                  <div className="pt-1.5 border-t border-ink-3 flex items-center justify-between">
                                    <button
                                      type="button"
                                      disabled={isResendingThis}
                                      onClick={async () => {
                                        setResendingTrusteeId(trusteeId);
                                        setErrorMsg(null);
                                        setMsg(null);
                                        try {
                                          const res = await fetch('/api/admin/trustees/resend-link', {
                                            method: 'POST',
                                            headers: getAuthHeaders(),
                                            body: JSON.stringify({
                                              election_id: activeElectionId,
                                              trustee_id: trusteeId,
                                            }),
                                          });
                                          const data = await res.json();
                                          if (!res.ok) {
                                            throw new Error(data.detail || 'Failed to resend ceremony link.');
                                          }
                                          setMsg(data.message || `Ceremony link re-dispatched to ${t.email}.`);
                                        } catch (err: any) {
                                          setErrorMsg(err.message || 'Error resending link.');
                                        } finally {
                                          setResendingTrusteeId(null);
                                        }
                                      }}
                                      className="text-[10px] text-on-ink/60 hover:text-white transition underline underline-offset-2 disabled:opacity-40"
                                    >
                                      {isResendingThis ? 'Resending...' : 'Resend ceremony link'}
                                    </button>
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Step 4: Validation Approvals */}
                  <div className={`p-6 rounded-xl border ${
                    ceremonyMonitor?.all_approved
                      ? 'bg-ink-2 border-emerald-800/60'
                      : 'bg-ink/50 border-ink-3 opacity-60'
                  }`}>
                    <div className="flex items-start gap-4">
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center font-mono text-xs font-bold ${
                        ceremonyMonitor?.all_approved
                          ? 'bg-emerald-600 text-white'
                          : 'bg-ink-3 text-on-ink/50'
                      }`}>
                        4
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center justify-between">
                          <h3 className="font-display text-base font-bold text-white">Trustee Validation Approvals</h3>
                          <span className={`text-[10px] font-mono uppercase px-2 py-0.5 rounded border ${
                            ceremonyMonitor?.all_approved
                              ? 'bg-emerald-950 text-emerald-300 border-emerald-800'
                              : 'bg-ink-3 text-on-ink/50 border-ink-3'
                          }`}>
                            {ceremonyMonitor?.all_approved ? 'ALL APPROVED' : `${trustees.filter((t) => t.has_approved).length} OF ${trustees.length} APPROVED`}
                          </span>
                        </div>
                        <p className="text-xs text-on-ink/60 mt-1">
                          Decryption threshold verification and independent audit sign-off by trustees.
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* Step 5: Official Publish */}
                  <div className={`p-6 rounded-xl border ${
                    resultsPublishedAt || status === 'COMPLETED'
                      ? 'bg-ink-2 border-purple-800/60'
                      : 'bg-ink/50 border-ink-3 opacity-60'
                  }`}>
                    <div className="flex items-start gap-4">
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center font-mono text-xs font-bold ${
                        resultsPublishedAt || status === 'COMPLETED'
                          ? 'bg-purple-600 text-white'
                          : 'bg-ink-3 text-on-ink/50'
                      }`}>
                        5
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center justify-between">
                          <h3 className="font-display text-base font-bold text-white">Official Results Published</h3>
                          <span className={`text-[10px] font-mono uppercase px-2 py-0.5 rounded border ${
                            resultsPublishedAt || status === 'COMPLETED'
                              ? 'bg-purple-950 text-purple-300 border-purple-800'
                              : 'bg-ink-3 text-on-ink/50 border-ink-3'
                          }`}>
                            {resultsPublishedAt || status === 'COMPLETED' ? 'PUBLISHED' : 'PENDING APPROVAL'}
                          </span>
                        </div>
                        <p className="text-xs text-on-ink/60 mt-1">
                          Final tally counts made public on audit ledger and voter overview portals.
                        </p>
                        {(resultsPublishedAt || status === 'COMPLETED') && (
                          <div className="mt-4 space-y-4">
                            <div className="p-3 bg-purple-950/40 rounded border border-purple-800 text-xs font-mono text-purple-200 flex items-center justify-between">
                              <span>Results published to public audit ledger at {resultsPublishedAt || 'now'}.</span>
                              <span className="text-[11px] bg-purple-900/60 text-purple-300 px-2 py-0.5 rounded">Audited by Trustees</span>
                            </div>

                            {publishedTally && publishedTally.results && (
                              <div className="p-4 bg-ink border border-ink-3 rounded-lg">
                                <div className="flex items-center justify-between mb-3 border-b border-ink-3 pb-2">
                                  <div className="flex items-center gap-2">
                                    <BarChart3 className="w-4 h-4 text-purple-400" />
                                    <span className="font-display text-sm font-bold text-white">Certified Vote Count</span>
                                  </div>
                                  <span className="text-xs font-mono text-on-ink/70">
                                    Total Ballots: <strong className="text-white">{publishedTally.total_ballots || totalBallots}</strong>
                                  </span>
                                </div>

                                {(() => {
                                  const entries = Object.entries(publishedTally.results || {});
                                  const maxVotes = Math.max(...entries.map(([_, v]: [string, any]) => Number(v) || 0), 0);
                                  const total = publishedTally.total_ballots || entries.reduce((acc, [_, v]) => acc + Number(v), 0) || 1;

                                  return (
                                    <div className="space-y-3">
                                      {entries.map(([candidate, count]: [string, any]) => {
                                        const cCount = Number(count) || 0;
                                        const pct = ((cCount / total) * 100).toFixed(1);
                                        const isWinner = cCount === maxVotes && maxVotes > 0;

                                        return (
                                          <div key={candidate} className="p-3 bg-ink-2 rounded border border-ink-3">
                                            <div className="flex items-center justify-between text-xs font-mono mb-1.5">
                                              <div className="flex items-center gap-2">
                                                <span className="font-bold text-white text-sm">{candidate}</span>
                                                {isWinner && (
                                                  <span className="inline-flex items-center gap-1 text-[10px] uppercase font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40 px-2 py-0.5 rounded-full">
                                                    <Trophy className="w-3 h-3 text-amber-400" />
                                                    Winner
                                                  </span>
                                                )}
                                              </div>
                                              <div className="text-right">
                                                <span className="text-sm font-bold text-white">{cCount} votes</span>
                                                <span className="text-on-ink/50 ml-2">({pct}%)</span>
                                              </div>
                                            </div>
                                            <div className="w-full h-2 bg-ink-3 rounded-full overflow-hidden">
                                              <div
                                                className={`h-full transition-all duration-500 ${isWinner ? 'bg-amber-400' : 'bg-purple-500'}`}
                                                style={{ width: `${pct}%` }}
                                              />
                                            </div>
                                          </div>
                                        );
                                      })}
                                    </div>
                                  );
                                })()}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* SECTION: VOTER ROLL */}
        {activeSection === 'voter-roll' && (
          <div>
            <div className="mb-8 border-b border-ink-3 pb-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <span className="text-[11px] font-mono uppercase tracking-widest text-on-ink/50">Registry</span>
                <h1 className="font-display text-2xl font-bold text-white mt-1">Official Voter Roll</h1>
              </div>
              <div className="relative">
                <Search className="w-3.5 h-3.5 absolute left-3 top-3 text-on-ink/40" />
                <input
                  type="text"
                  placeholder="Search voter ID, email..."
                  value={voterSearch}
                  onChange={(e) => setVoterSearch(e.target.value)}
                  className="pl-8 pr-3.5 py-1.5 bg-ink text-xs font-mono text-white border border-ink-3 rounded focus:outline-none focus:border-on-ink"
                />
              </div>
            </div>

            <div className="bg-ink-2 border border-ink-3 rounded-lg overflow-hidden">
              <table className="w-full text-left text-xs font-mono">
                <thead className="bg-ink border-b border-ink-3 text-on-ink/60">
                  <tr>
                    <th className="px-4 py-3">Voter ID</th>
                    <th className="px-4 py-3">Full Name</th>
                    <th className="px-4 py-3">Email</th>
                    <th className="px-4 py-3">Registered At</th>
                    <th className="px-4 py-3">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-ink-3">
                  {voterRoll.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-4 py-8 text-center text-on-ink/40">
                        No registered voters in this election yet.
                      </td>
                    </tr>
                  ) : (
                    voterRoll
                      .filter(
                        (v) =>
                          v.voter_id.toLowerCase().includes(voterSearch.toLowerCase()) ||
                          v.email.toLowerCase().includes(voterSearch.toLowerCase()) ||
                          v.full_name.toLowerCase().includes(voterSearch.toLowerCase())
                      )
                      .map((v) => (
                        <tr key={v.id} className="hover:bg-ink/40">
                          <td className="px-4 py-3 text-white font-bold">{v.voter_id}</td>
                          <td className="px-4 py-3">{v.full_name}</td>
                          <td className="px-4 py-3 text-on-ink/70">{v.email}</td>
                          <td className="px-4 py-3 text-on-ink/50">{v.registered_at}</td>
                          <td className="px-4 py-3">
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] ${
                                v.status === 'BALLOT_CAST'
                                  ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                                  : 'bg-blue-950 text-blue-300 border border-blue-800'
                              }`}
                            >
                              {v.status}
                            </span>
                          </td>
                        </tr>
                      ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* SECTION: AUDIT LEDGER */}
        {activeSection === 'audit-log' && (
          <div>
            <div className="mb-8 border-b border-ink-3 pb-4">
              <span className="text-[11px] font-mono uppercase tracking-widest text-on-ink/50">Ledger</span>
              <h1 className="font-display text-2xl font-bold text-white mt-1">Public Bulletin Board Ledger</h1>
            </div>

            <div className="bg-ink-2 border border-ink-3 rounded-lg overflow-hidden">
              <table className="w-full text-left text-xs font-mono">
                <thead className="bg-ink border-b border-ink-3 text-on-ink/60">
                  <tr>
                    <th className="px-4 py-3">Seq #</th>
                    <th className="px-4 py-3">Receipt Code</th>
                    <th className="px-4 py-3">Block Hash</th>
                    <th className="px-4 py-3">Timestamp</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-ink-3">
                  {bulletinBoard.length === 0 ? (
                    <tr>
                      <td colSpan={4} className="px-4 py-8 text-center text-on-ink/40">
                        Zero ballots cast on the immutable ledger.
                      </td>
                    </tr>
                  ) : (
                    bulletinBoard.map((b) => (
                      <tr key={b.sequence_number} className="hover:bg-ink/40">
                        <td className="px-4 py-3 text-white font-bold">#{b.sequence_number}</td>
                        <td className="px-4 py-3 text-accent truncate max-w-xs">{b.receipt_code}</td>
                        <td className="px-4 py-3 text-on-ink/50 truncate max-w-xs">{b.block_hash}</td>
                        <td className="px-4 py-3 text-on-ink/50">
                          {new Date(b.timestamp * 1000).toLocaleString()}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* SECTION: SETTINGS */}
        {activeSection === 'settings' && (
          <div>
            <div className="mb-8 border-b border-ink-3 pb-4">
              <span className="text-[11px] font-mono uppercase tracking-widest text-on-ink/50">Configuration</span>
              <h1 className="font-display text-2xl font-bold text-white mt-1">Platform Settings</h1>
            </div>

            <div className="space-y-6 max-w-3xl">
              {/* Email settings card */}
              <div className="bg-ink-2 border border-ink-3 rounded-xl p-6 sm:p-8">
                <div className="flex items-center gap-3 mb-2">
                  <Send className="w-5 h-5 text-accent" />
                  <h2 className="font-display text-lg font-bold text-white">Email Settings</h2>
                </div>
                <p className="text-xs text-on-ink/70 mb-6 leading-relaxed">
                  {APP_NAME} delivers secret trustee invitations, unlock alerts, and voter credentials through SMTP. Check configuration and send a live test message to verify deliverability and DKIM compliance.
                </p>

                {emailSettings && (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6 p-4 bg-ink rounded-lg border border-ink-3 font-mono text-xs">
                    <div>
                      <span className="text-[10px] uppercase text-on-ink/50 block">SMTP Host</span>
                      <span className="text-white font-semibold">{emailSettings.smtp_host || 'Not set'}</span>
                    </div>
                    <div>
                      <span className="text-[10px] uppercase text-on-ink/50 block">SMTP Port</span>
                      <span className="text-white font-semibold">{emailSettings.smtp_port}</span>
                    </div>
                    <div>
                      <span className="text-[10px] uppercase text-on-ink/50 block">Transport Security</span>
                      <span className="text-white font-semibold">{emailSettings.tls_mode}</span>
                    </div>
                    <div>
                      <span className="text-[10px] uppercase text-on-ink/50 block">Effective From Address</span>
                      <span className="text-accent font-semibold">{emailSettings.effective_from || emailSettings.smtp_from}</span>
                    </div>
                  </div>
                )}

                {/* Send Test Email form */}
                <div className="pt-4 border-t border-ink-3 space-y-4">
                  <h3 className="text-xs font-mono uppercase tracking-wider text-white font-bold">Send Test Email</h3>
                  <div className="flex flex-col sm:flex-row gap-3">
                    <input
                      type="email"
                      value={testEmailAddress}
                      onChange={(e) => setTestEmailAddress(e.target.value)}
                      placeholder="Enter recipient email address (e.g. your Gmail)"
                      className="flex-1 px-3.5 py-2.5 bg-ink text-white border border-ink-3 rounded text-xs font-mono focus:outline-none focus:border-on-ink placeholder:text-on-ink/30"
                    />
                    <button
                      type="button"
                      disabled={isSendingTestEmail || !testEmailAddress.trim()}
                      onClick={async () => {
                        setIsSendingTestEmail(true);
                        setTestEmailResult(null);
                        setErrorMsg(null);
                        setMsg(null);
                        try {
                          const res = await fetch('/api/admin/settings/send-test-email', {
                            method: 'POST',
                            headers: getAuthHeaders(),
                            body: JSON.stringify({ to_email: testEmailAddress.trim() }),
                          });
                          const data = await res.json();
                          if (!res.ok) {
                            throw new Error(data.detail || 'Test email failed to send.');
                          }
                          setTestEmailResult({
                            success: true,
                            message: data.message,
                            detail: data.detail,
                          });
                        } catch (err: any) {
                          setTestEmailResult({
                            success: false,
                            message: err.message || 'Error dispatching test email.',
                          });
                        } finally {
                          setIsSendingTestEmail(false);
                        }
                      }}
                      className="px-5 py-2.5 bg-on-ink text-ink font-semibold rounded text-xs hover:bg-white transition flex items-center justify-center gap-2 disabled:opacity-40 font-mono"
                    >
                      {isSendingTestEmail ? 'Sending...' : 'Send Test Email'}
                    </button>
                  </div>

                  {testEmailResult && (
                    <div
                      className={`p-3.5 rounded-lg border text-xs font-mono ${
                        testEmailResult.success
                          ? 'bg-emerald-950/80 border-emerald-800 text-emerald-200'
                          : 'bg-red-950/80 border-red-800 text-red-200'
                      }`}
                    >
                      <div className="font-semibold">{testEmailResult.message}</div>
                      {testEmailResult.detail && (
                        <div className="text-[11px] text-on-ink/60 mt-1">{testEmailResult.detail}</div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* SEND INVITATIONS CONFIRM MODAL */}
        {showInviteModal && (
          <div className="fixed inset-0 bg-black/80 flex items-center justify-center p-4 z-50">
            <div className="bg-ink-2 border border-ink-3 rounded-xl p-6 max-w-md w-full shadow-2xl">
              <h3 className="font-display text-lg font-bold text-white mb-2">Send Trustee Invitations</h3>
              <p className="text-xs text-on-ink/70 mb-4 leading-relaxed">
                This will generate the election threshold master key and Shamir polynomial shares, compute unique 80-bit Crockford codes for all {trustees.length} trustees, and dispatch individual invitation emails.
              </p>
              <div className="p-3 bg-ink border border-ink-3 rounded-lg mb-6 text-xs font-mono space-y-1 text-on-ink/80">
                <div>• Total Trustees: <span className="text-white font-bold">{trustees.length}</span></div>
                <div>• Decryption Threshold: <span className="text-white font-bold">{Math.floor(trustees.length / 2) + 1} of {trustees.length}</span></div>
                <div>• Secret codes are sent directly to each trustee and cannot be viewed again.</div>
              </div>
              <div className="flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setShowInviteModal(false)}
                  className="px-4 py-2 bg-ink border border-ink-3 text-xs text-on-ink/80 rounded hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleSendInvitations}
                  disabled={isInviting}
                  className="px-4 py-2 bg-on-ink text-ink font-semibold text-xs rounded hover:bg-white font-mono"
                >
                  {isInviting ? 'Generating & Dispatching...' : 'Confirm and Send'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* REISSUE CODES CONFIRM MODAL */}
        {showReissueModal && (
          <div className="fixed inset-0 bg-black/80 flex items-center justify-center p-4 z-50">
            <div className="bg-ink-2 border border-ink-3 rounded-xl p-6 max-w-md w-full shadow-2xl">
              <h3 className="font-display text-lg font-bold text-white mb-2">Reissue Trustee Secret Codes</h3>
              <p className="text-xs text-on-ink/70 mb-4 leading-relaxed">
                Reissuing codes will invalidate all previously issued Crockford codes and ceremony links. A fresh key ceremony will be initialized and re-dispatched.
              </p>
              <div className="mb-6">
                <label className="block text-[11px] font-mono text-on-ink/70 uppercase mb-1.5">
                  Confirm Administrator Password
                </label>
                <input
                  type="password"
                  value={reissuePassword}
                  onChange={(e) => setReissuePassword(e.target.value)}
                  placeholder="Admin password"
                  className="w-full px-3.5 py-2 bg-ink text-white border border-ink-3 rounded text-xs font-mono focus:outline-none focus:border-on-ink"
                />
              </div>
              <div className="flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() => {
                    setShowReissueModal(false);
                    setReissuePassword('');
                  }}
                  className="px-4 py-2 bg-ink border border-ink-3 text-xs text-on-ink/80 rounded hover:text-white font-mono"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleReissueCodes}
                  disabled={isReissuing || !reissuePassword.trim()}
                  className="px-4 py-2 bg-amber-600 text-white font-semibold text-xs rounded hover:bg-amber-500 font-mono"
                >
                  {isReissuing ? 'Reissuing...' : 'Confirm Reissue'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ANNOUNCE SCHEDULE CONFIRM MODAL */}
        {showAnnounceConfirmModal && (
          <div className="fixed inset-0 bg-black/80 flex items-center justify-center p-4 z-50">
            <div className="bg-ink-2 border border-ink-3 rounded-xl p-6 max-w-md w-full shadow-2xl">
              <h3 className="font-display text-lg font-bold text-white mb-2">Publish & Announce Schedule</h3>
              <p className="text-xs text-on-ink/70 mb-4 leading-relaxed">
                This will save and announce the voting dates for <strong className="text-white">{electionTitle || activeElectionId}</strong>.
              </p>
              <div className="p-3 bg-ink border border-ink-3 rounded-lg mb-6 text-xs font-mono space-y-1.5 text-on-ink/80">
                <div>• Timezone: <span className="text-white font-bold">{timezoneStr}</span></div>
                <div>• Voters to Notify: <span className="text-white font-bold">{voterRoll.length} registered voter(s)</span></div>
                {scheduleWarning && (
                  <div className="text-amber-400 text-[11px] pt-1">
                    ⚠ {scheduleWarning}
                  </div>
                )}
              </div>
              <div className="flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setShowAnnounceConfirmModal(false)}
                  className="px-4 py-2 bg-ink border border-ink-3 text-xs text-on-ink/80 rounded hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleSaveAndAnnounceSchedule}
                  disabled={isSavingSchedule}
                  className="px-4 py-2 bg-on-ink text-ink font-semibold text-xs rounded hover:bg-white font-mono"
                >
                  {isSavingSchedule ? 'Broadcasting...' : 'Confirm and Announce'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* OPEN VOTING CONFIRM MODAL */}
        {showOpenConfirmModal && (
          <div className="fixed inset-0 bg-black/80 flex items-center justify-center p-4 z-50">
            <div className="bg-ink-2 border border-ink-3 rounded-xl p-6 max-w-md w-full shadow-2xl">
              <h3 className="font-display text-lg font-bold text-white mb-2">Open Voting</h3>
              <p className="text-xs text-on-ink/70 mb-6 leading-relaxed">
                Opening voting transitions the election into the active state, enabling eligible voters to cast encrypted ballots.
              </p>
              <div className="flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setShowOpenConfirmModal(false)}
                  className="px-4 py-2 bg-ink border border-ink-3 text-xs text-on-ink/80 rounded hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleOpenVoting}
                  disabled={isLoadingAction}
                  className="px-4 py-2 bg-emerald-600 text-white font-semibold text-xs rounded hover:bg-emerald-500 font-mono"
                >
                  {isLoadingAction ? 'Opening...' : 'Confirm Open Voting'}
                </button>
              </div>
            </div>
          </div>
        )}

        {pendingDelete && deleteStep > 0 && (
          <div className="fixed inset-0 bg-black/80 flex items-center justify-center p-4 z-50">
            <div className="bg-ink-2 border border-red-900/60 rounded-xl p-6 max-w-md w-full shadow-2xl">
              {deleteStep === 1 ? (
                <>
                  <h3 className="font-display text-lg font-bold text-white mb-2">Delete this election?</h3>
                  <p className="text-xs text-red-200 leading-relaxed mb-4">
                    Warning: deleting <span className="font-semibold text-white">{pendingDelete.title}</span> permanently removes that election from the database. Its voter roll ({pendingDelete.registered_voters}), ballots ({pendingDelete.ballots_cast}), trustees, notifications, and results are deleted with it. This cannot be undone.
                  </p>
                  <div className="flex justify-end gap-3">
                    <button
                      type="button"
                      onClick={closeDeleteDialog}
                      className="px-4 py-2 bg-ink border border-ink-3 text-xs text-on-ink/80 rounded hover:text-white"
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      onClick={() => setDeleteStep(2)}
                      className="px-4 py-2 bg-red-600 text-white font-semibold text-xs rounded hover:bg-red-500 font-mono"
                    >
                      Continue
                    </button>
                  </div>
                </>
              ) : (
                <>
                  <h3 className="font-display text-lg font-bold text-white mb-2">Confirm deletion</h3>
                  <p className="text-xs text-red-200 leading-relaxed mb-4">
                    This is the second confirmation. <span className="font-semibold text-white">{pendingDelete.title}</span> will be deleted now. There is no way to restore it.
                  </p>
                  <div className="flex justify-end gap-3">
                    <button
                      type="button"
                      onClick={closeDeleteDialog}
                      className="px-4 py-2 bg-ink border border-ink-3 text-xs text-on-ink/80 rounded hover:text-white"
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      onClick={handleDeleteElection}
                      className="px-4 py-2 bg-red-600 text-white font-semibold text-xs rounded hover:bg-red-500 font-mono"
                    >
                      Delete election
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        )}

        {/* CLOSE VOTING CONFIRM MODAL */}
        {showCloseConfirmModal && (
          <div className="fixed inset-0 bg-black/80 flex items-center justify-center p-4 z-50">
            <div className="bg-ink-2 border border-ink-3 rounded-xl p-6 max-w-md w-full shadow-2xl">
              <h3 className="font-display text-lg font-bold text-white mb-2">Close Voting & Seal Ledger</h3>
              <p className="text-xs text-on-ink/70 mb-4 leading-relaxed">
                Closing voting permanently seals the public bulletin board and prevents any new ballots from being cast. The All-Trustees Sequential Unlock Ceremony will immediately begin.
              </p>
              
              <div className="p-3 bg-ink border border-ink-3 rounded-lg mb-4 text-xs font-mono space-y-1 text-on-ink/80">
                <div>• Action: <span className="text-red-400 font-bold">Permanent Ballot Box Sealing</span></div>
                <div>• Current Election: <span className="text-white font-bold">{electionTitle || activeElectionId}</span></div>
              </div>

              <div className="mb-6">
                <label className="block text-xs font-mono text-on-ink/70 mb-1.5">
                  Type <span className="text-white font-bold">{electionTitle || activeElectionId}</span> to confirm:
                </label>
                <input
                  type="text"
                  value={closeConfirmInput}
                  onChange={(e) => setCloseConfirmInput(e.target.value)}
                  placeholder={`Type "${electionTitle || activeElectionId}"`}
                  className="w-full px-3 py-2 bg-ink text-white border border-ink-3 rounded text-xs font-mono focus:outline-none focus:border-red-500"
                />
              </div>

              <div className="flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() => {
                    setShowCloseConfirmModal(false);
                    setCloseConfirmInput('');
                  }}
                  className="px-4 py-2 bg-ink border border-ink-3 text-xs text-on-ink/80 rounded hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleCloseVoting}
                  disabled={isLoadingAction || closeConfirmInput.trim().toLowerCase() !== (electionTitle || activeElectionId).trim().toLowerCase()}
                  className="px-4 py-2 bg-red-600 text-white font-semibold text-xs rounded hover:bg-red-500 font-mono disabled:opacity-40"
                >
                  {isLoadingAction ? 'Sealing...' : 'Confirm and Seal Ballot Box'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* DEV RESET CONFIRM MODAL */}
        {showResetConfirm && (
          <div className="fixed inset-0 bg-black/80 flex items-center justify-center p-4 z-50">
            <div className="bg-ink-2 border border-ink-3 rounded-xl p-6 max-w-md w-full shadow-2xl">
              <h3 className="font-display text-lg font-bold text-white mb-2">Reset Demo Data</h3>
              <p className="text-xs text-on-ink/70 mb-6 leading-relaxed">
                This DEV action will clear all registered voters, cast ballots, notifications, and reset the election state to a clean draft.
              </p>
              <div className="flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setShowResetConfirm(false)}
                  className="px-4 py-2 bg-ink border border-ink-3 text-xs text-on-ink/80 rounded hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleDevResetData}
                  disabled={isResetting}
                  className="px-4 py-2 bg-amber-600 text-white font-semibold text-xs rounded hover:bg-amber-500 font-mono"
                >
                  {isResetting ? 'Resetting...' : 'Confirm Reset'}
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
};

export default AdminDashboard;

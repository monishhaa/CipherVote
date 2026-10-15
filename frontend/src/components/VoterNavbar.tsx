import React, { useState, useEffect } from 'react';
import { Bell, LogOut, Menu, X, ArrowLeft, User } from 'lucide-react';
import { APP_NAME } from '../constants';

interface MyElectionItem {
  election_id: string;
  title: string;
  status: string;
  is_open: boolean;
}

interface VoterNavbarProps {
  currentPath: string;
  navigateTo: (path: string) => void;
  voterSession: { voter_id: string; email: string } | null;
  onLogout: () => void;
  unreadNotificationsCount?: number;
  currentElectionId?: string;
  onSelectElection?: (electionId: string) => void;
}

export const VoterNavbar: React.FC<VoterNavbarProps> = ({
  currentPath,
  navigateTo,
  voterSession,
  onLogout,
  unreadNotificationsCount = 0,
  currentElectionId = '',
  onSelectElection,
}) => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [myElections, setMyElections] = useState<MyElectionItem[]>([]);

  // Fetch my registered elections when voter is signed in
  useEffect(() => {
    const token = sessionStorage.getItem('voter_session_token');
    if (!token || !voterSession) {
      setMyElections([]);
      return;
    }

    fetch('/api/voter/my-elections', {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data && data.elections) {
          setMyElections(data.elections);
          if (!currentElectionId && data.elections.length > 0) {
            onSelectElection?.(data.elections[0].election_id);
          }
        }
      })
      .catch(() => {});
  }, [voterSession, currentElectionId, onSelectElection]);

  const activeElectionId = currentElectionId || (myElections.length > 0 ? myElections[0].election_id : '');

  const handleElectionChange = (newElectionId: string) => {
    onSelectElection?.(newElectionId);
    sessionStorage.setItem('voter_election_id', newElectionId);
    // Determine target section
    const sec = currentPath.includes('/vote')
      ? 'vote'
      : currentPath.includes('/notifications')
      ? 'notifications'
      : currentPath.includes('/audit')
      ? 'audit'
      : 'overview';
    navigateTo(`/user/e/${encodeURIComponent(newElectionId)}/${sec}`);
  };

  const navLinks = [
    { label: 'Overview', path: activeElectionId ? `/user/e/${activeElectionId}/overview` : '/user/overview', key: 'overview' },
    { label: 'Register', path: '/user/register', key: 'register' },
    { label: 'Cast Ballot', path: activeElectionId ? `/user/e/${activeElectionId}/vote` : '/user/vote', key: 'vote' },
    { label: 'Public Audit', path: activeElectionId ? `/user/e/${activeElectionId}/audit` : '/user/audit', key: 'audit' },
  ];

  const isLinkActive = (key: string) => {
    if (key === 'overview') return currentPath.includes('/overview') || currentPath === '/user';
    if (key === 'register') return currentPath.includes('/register');
    if (key === 'vote') return currentPath.includes('/vote');
    if (key === 'audit') return currentPath.includes('/audit');
    return false;
  };

  return (
    <header className="w-full bg-paper border-b border-line sticky top-0 z-30">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Left: Brand & Return */}
        <div className="flex items-center gap-4 sm:gap-6">
          <button
            type="button"
            onClick={() => navigateTo('/')}
            className="flex items-center gap-1.5 text-xs text-ink/60 hover:text-ink transition group"
            title="Return to Gateway"
          >
            <ArrowLeft className="w-3.5 h-3.5 group-hover:-translate-x-0.5 transition" />
            <span className="hidden sm:inline font-mono">Gateway</span>
          </button>

          <button
            type="button"
            onClick={() => navigateTo(activeElectionId ? `/user/e/${activeElectionId}/overview` : '/user/overview')}
            className="flex items-center gap-2 text-left"
          >
            <span className="font-display font-bold text-xl tracking-tight text-ink">
              {APP_NAME}
            </span>
            <span className="text-[11px] font-mono uppercase bg-paper-2 text-ink/70 px-2 py-0.5 rounded border border-line hidden sm:inline">
              Voter
            </span>
          </button>

          {/* Header Election Chooser (Signed In) */}
          {voterSession && (
            <div className="hidden lg:flex items-center border-l border-line pl-4">
              {myElections.length === 0 ? (
                <div className="flex items-center gap-2 text-xs font-mono text-ink/60">
                  <span>Not registered for any election</span>
                  <button
                    type="button"
                    onClick={() => navigateTo('/user/register')}
                    className="text-xs text-accent font-semibold hover:underline"
                  >
                    Register
                  </button>
                </div>
              ) : myElections.length === 1 ? (
                <div className="flex items-center gap-2 text-xs font-mono text-ink">
                  <span className="font-medium text-ink truncate max-w-[200px]" title={myElections[0].title}>
                    {myElections[0].title}
                  </span>
                  <span className={`px-1.5 py-0.2 rounded text-[10px] font-bold uppercase border ${
                    myElections[0].status === 'OPEN'
                      ? 'bg-emerald-50 text-emerald-700 border-emerald-300'
                      : 'bg-paper-2 text-ink/60 border-line'
                  }`}>
                    {myElections[0].status}
                  </span>
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-mono uppercase text-ink/50">Election:</span>
                  <select
                    value={activeElectionId}
                    onChange={(e) => handleElectionChange(e.target.value)}
                    className="text-xs font-mono bg-paper-2 border border-line rounded px-2.5 py-1 text-ink focus:outline-none focus:border-accent"
                  >
                    {myElections.map((el) => (
                      <option key={el.election_id} value={el.election_id}>
                        {el.title} ({el.status})
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Center: Desktop Navigation Links */}
        <nav className="hidden md:flex items-center gap-1">
          {navLinks.map((link) => {
            const active = isLinkActive(link.key);
            return (
              <button
                key={link.key}
                type="button"
                onClick={() => navigateTo(link.path)}
                className={`px-3.5 py-1.5 text-xs font-medium rounded transition relative ${
                  active
                    ? 'text-ink bg-paper-2 font-semibold'
                    : 'text-ink/70 hover:text-ink hover:bg-paper-2/60'
                }`}
              >
                {link.label}
                {active && (
                  <span className="absolute bottom-0 left-3 right-3 h-[2px] bg-accent" />
                )}
              </button>
            );
          })}
        </nav>

        {/* Right: Notifications & Account */}
        <div className="flex items-center gap-3">
          {/* Notification Bell (Badge only when unread > 0) */}
          <button
            type="button"
            onClick={() => navigateTo(activeElectionId ? `/user/e/${activeElectionId}/notifications` : '/user/notifications')}
            className={`p-2 rounded border border-line hover:bg-paper-2 transition relative ${
              currentPath.includes('/notifications') ? 'bg-paper-2 text-ink' : 'text-ink/60'
            }`}
            title="View Notifications"
          >
            <Bell className="w-4 h-4" />
            {unreadNotificationsCount > 0 && (
              <span className="absolute -top-1 -right-1 min-w-[16px] h-4 px-1 bg-accent text-white text-[10px] font-bold rounded-full flex items-center justify-center">
                {unreadNotificationsCount > 9 ? '9+' : unreadNotificationsCount}
              </span>
            )}
          </button>

          {/* Account Status / Sign In */}
          {voterSession ? (
            <div className="flex items-center gap-2 border-l border-line pl-3">
              <button
                type="button"
                onClick={() => navigateTo(activeElectionId ? `/user/e/${activeElectionId}/overview` : '/user/overview')}
                className="flex items-center gap-2 text-xs font-medium text-ink hover:text-accent transition"
                title={`Signed in as Voter ID: ${voterSession.voter_id}`}
              >
                <div className="w-7 h-7 rounded-full bg-paper-2 border border-line flex items-center justify-center text-ink/70">
                  <User className="w-3.5 h-3.5" />
                </div>
                <span className="hidden lg:inline font-mono text-xs">{voterSession.voter_id}</span>
              </button>
              <button
                type="button"
                onClick={onLogout}
                className="p-1.5 text-ink/60 hover:text-red-700 transition"
                title="Sign Out"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => navigateTo('/user/login')}
              className="px-3.5 py-1.5 text-xs font-medium text-ink border border-line rounded bg-paper hover:bg-paper-2 transition font-mono"
            >
              Sign In
            </button>
          )}

          {/* Mobile Menu Toggle */}
          <button
            type="button"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="md:hidden p-2 text-ink/60 hover:text-ink border border-line rounded"
          >
            {mobileMenuOpen ? <X className="w-4 h-4" /> : <Menu className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Mobile Drawer */}
      {mobileMenuOpen && (
        <div className="md:hidden border-t border-line bg-paper px-4 py-3 space-y-2">
          {voterSession && myElections.length > 1 && (
            <div className="pb-2 mb-2 border-b border-line">
              <label className="block text-[11px] font-mono text-ink/60 uppercase mb-1">Active Election:</label>
              <select
                value={activeElectionId}
                onChange={(e) => {
                  handleElectionChange(e.target.value);
                  setMobileMenuOpen(false);
                }}
                className="w-full text-xs font-mono bg-paper-2 border border-line rounded p-2 text-ink"
              >
                {myElections.map((el) => (
                  <option key={el.election_id} value={el.election_id}>
                    {el.title} ({el.status})
                  </option>
                ))}
              </select>
            </div>
          )}

          {navLinks.map((link) => (
            <button
              key={link.key}
              type="button"
              onClick={() => {
                navigateTo(link.path);
                setMobileMenuOpen(false);
              }}
              className={`w-full text-left px-3 py-2 text-xs font-medium rounded ${
                isLinkActive(link.key) ? 'bg-paper-2 text-ink font-semibold' : 'text-ink/70'
              }`}
            >
              {link.label}
            </button>
          ))}
        </div>
      )}
    </header>
  );
};

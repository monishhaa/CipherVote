import { useState, useEffect, useCallback, lazy, Suspense } from 'react';
import { Landing } from './pages/Landing';
import { VoterLogin } from './pages/VoterLogin';
import { VoterRegister } from './pages/VoterRegister';
import { VoterOverview } from './pages/VoterOverview';
import { VoterVote } from './pages/VoterVote';
import { VoterNotifications } from './pages/VoterNotifications';
import { VoterAudit } from './pages/VoterAudit';
import { AdminLogin } from './pages/AdminLogin';
import { CeremonyPage } from './pages/CeremonyPage';
import { VoterNavbar } from './components/VoterNavbar';
import { parseRoute, ParsedRoute } from './utils/routeUtils';
import { slugToAdminSection } from './pages/AdminDashboard';
import { APP_NAME } from './constants';

// Lazy load the Admin Dashboard bundle
const AdminDashboard = lazy(() => import('./pages/AdminDashboard'));

export function App() {
  const [currentPath, setCurrentPath] = useState<string>(() => window.location.pathname || '/');
  const [parsedRoute, setParsedRoute] = useState<ParsedRoute>(() => parseRoute(window.location.pathname || '/'));
  const [currentElectionId, setCurrentElectionId] = useState<string>(() => {
    const route = parseRoute(window.location.pathname || '/');
    return route.electionId || sessionStorage.getItem('voter_election_id') || '';
  });
  const [electionTitle, setElectionTitle] = useState<string>(APP_NAME);
  const [electionStatus, setElectionStatus] = useState<string>('REGISTRATION');
  const [isOpen, setIsOpen] = useState<boolean>(false);
  const [unreadNotifications, setUnreadNotifications] = useState<number>(0);

  // Admin Auth State
  const [isAdmin, setIsAdmin] = useState<boolean>(() => {
    return Boolean(sessionStorage.getItem('ciphervote_admin_token'));
  });

  // Voter Auth State
  const [voterSession, setVoterSession] = useState<{ voter_id: string; email: string } | null>(() => {
    const token = sessionStorage.getItem('voter_session_token');
    const voterId = sessionStorage.getItem('voter_id');
    const email = sessionStorage.getItem('voter_email') || '';
    if (token && voterId) {
      return { voter_id: voterId, email };
    }
    return null;
  });

  // Client-side Navigation helper
  const navigateTo = useCallback((path: string) => {
    if (window.location.pathname !== path) {
      window.history.pushState(null, '', path);
    }
    setCurrentPath(path);
    const parsed = parseRoute(path);
    setParsedRoute(parsed);
    if (parsed.electionId) {
      setCurrentElectionId(parsed.electionId);
      sessionStorage.setItem('voter_election_id', parsed.electionId);
    }
    if (parsed.rawPath === '/audit') {
      const id = sessionStorage.getItem('voter_election_id');
      const dest = id ? `/user/e/${encodeURIComponent(id)}/audit` : '/user/audit';
      window.history.replaceState(null, '', dest);
      setCurrentPath(dest);
      setParsedRoute(parseRoute(dest));
    }
    window.scrollTo(0, 0);
  }, []);

  // Listen to browser Back/Forward navigation
  useEffect(() => {
    const handlePopState = () => {
      const p = window.location.pathname || '/';
      setCurrentPath(p);
      const parsed = parseRoute(p);
      setParsedRoute(parsed);
      if (parsed.electionId) {
        setCurrentElectionId(parsed.electionId);
        sessionStorage.setItem('voter_election_id', parsed.electionId);
      }
    };
    window.addEventListener('popstate', handlePopState);
    if (window.location.pathname === '/audit') {
      const id = sessionStorage.getItem('voter_election_id');
      navigateTo(id ? `/user/e/${encodeURIComponent(id)}/audit` : '/user/audit');
    }
    return () => window.removeEventListener('popstate', handlePopState);
  }, [navigateTo]);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch(currentElectionId ? `/api/public/status?election_id=${encodeURIComponent(currentElectionId)}` : '/api/public/status');
      if (res.ok) {
        const data = await res.json();
        setElectionStatus(data.status);
        setIsOpen(data.is_open);
        setElectionTitle(data.title);
        if (!currentElectionId && data.election_id) {
          setCurrentElectionId(data.election_id);
          sessionStorage.setItem('voter_election_id', data.election_id);
        }
      }
    } catch (e) {
      console.error(e);
    }
  }, [currentElectionId]);

  const fetchUnreadNotifications = useCallback(async () => {
    const token = sessionStorage.getItem('voter_session_token');
    if (!token) {
      setUnreadNotifications(0);
      return;
    }
    try {
      const res = await fetch('/api/voter/notifications', {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        const unread = (data.notifications || []).filter((n: any) => !n.read).length;
        setUnreadNotifications(unread);
      }
    } catch (e) {
      // Quiet fail
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 4000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  useEffect(() => {
    fetchUnreadNotifications();
  }, [fetchUnreadNotifications, currentPath]);

  const handleVoterLoginSuccess = (data: { voter_id: string; email: string }) => {
    setVoterSession(data);
    if (currentElectionId) {
      navigateTo(`/user/e/${currentElectionId}/overview`);
    } else {
      navigateTo('/user/overview');
    }
  };

  const handleVoterLogout = () => {
    sessionStorage.removeItem('voter_session_token');
    sessionStorage.removeItem('voter_id');
    sessionStorage.removeItem('voter_email');
    setVoterSession(null);
    navigateTo('/');
  };

  const handleAdminLoginSuccess = () => {
    setIsAdmin(true);
    if (currentElectionId) {
      navigateTo(`/admin/e/${currentElectionId}/overview`);
    } else {
      navigateTo('/admin');
    }
  };

  const handleAdminLogout = () => {
    sessionStorage.removeItem('ciphervote_admin_token');
    sessionStorage.removeItem('ciphervote_admin_user');
    setIsAdmin(false);
    navigateTo('/');
  };

  const isUserSection = parsedRoute.portal === 'user';
  const isAdminSection = parsedRoute.portal === 'admin';
  const isCeremonySection = parsedRoute.portal === 'ceremony';

  const ceremonyToken = parsedRoute.ceremonyToken || '';

  // Render voter content based on section
  const renderVoterPage = () => {
    const section = parsedRoute.section || 'overview';
    if (section === 'login') {
      return <VoterLogin onLoginSuccess={handleVoterLoginSuccess} navigateTo={navigateTo} />;
    }
    if (section === 'register') {
      return (
        <VoterRegister
          electionId={currentElectionId}
          electionTitle={electionTitle}
          navigateTo={navigateTo}
          onSelectElection={(id) => {
            setCurrentElectionId(id);
            sessionStorage.setItem('voter_election_id', id);
            navigateTo(`/user/e/${id}/register`);
          }}
        />
      );
    }
    if (section === 'vote') {
      return (
        <VoterVote
          key={currentElectionId || 'vote'}
          electionId={currentElectionId}
          electionTitle={electionTitle}
          navigateTo={navigateTo}
        />
      );
    }
    if (section === 'notifications') {
      return (
        <VoterNotifications
          key={currentElectionId || 'notifications'}
          electionId={currentElectionId}
          navigateTo={navigateTo}
        />
      );
    }
    if (section === 'audit' || section === 'trustee') {
      return <VoterAudit electionId={currentElectionId} navigateTo={navigateTo} />;
    }
    // Default: overview
    return (
      <VoterOverview
        key={currentElectionId || 'overview'}
        electionId={currentElectionId}
        electionTitle={electionTitle}
        isOpen={isOpen}
        electionStatus={electionStatus}
        navigateTo={navigateTo}
      />
    );
  };

  return (
    <div className={`min-h-screen flex flex-col font-sans ${isAdminSection || isCeremonySection ? 'bg-ink text-on-ink' : 'bg-paper text-ink'}`}>
      {/* Voter Navbar displayed for all voter-facing pages except landing, admin, and standalone ceremony */}
      {isUserSection && !isCeremonySection && (
        <VoterNavbar
          currentPath={currentPath}
          navigateTo={navigateTo}
          voterSession={voterSession}
          onLogout={handleVoterLogout}
          unreadNotificationsCount={unreadNotifications}
          currentElectionId={currentElectionId}
          onSelectElection={(id) => {
            setCurrentElectionId(id);
            sessionStorage.setItem('voter_election_id', id);
          }}
        />
      )}

      <main className="flex-1 w-full">
        {/* STANDALONE CEREMONY PAGE (/ceremony/:token) */}
        {isCeremonySection && (
          <CeremonyPage token={ceremonyToken} navigateTo={navigateTo} />
        )}

        {/* LANDING PAGE (/) */}
        {parsedRoute.portal === 'landing' && (
          <Landing
            navigateTo={navigateTo}
          />
        )}

        {/* VOTER PORTAL ROUTES */}
        {isUserSection && renderVoterPage()}

        {/* ADMIN PORTAL ROUTES */}
        {isAdminSection && (
          <>
            {!isAdmin ? (
              <AdminLogin
                onLoginSuccess={handleAdminLoginSuccess}
                onCancel={() => navigateTo('/')}
              />
            ) : (
              <Suspense fallback={<div className="p-8 text-center text-xs font-mono text-on-ink/50">Loading Admin Console...</div>}>
                <AdminDashboard
                  currentElectionId={currentElectionId}
                  initialSection={slugToAdminSection[parsedRoute.section || 'overview'] || 'overview'}
                  onSelectElection={(id) => {
                    setCurrentElectionId(id);
                    sessionStorage.setItem('voter_election_id', id);
                  }}
                  onStatusChange={fetchStatus}
                  onLogout={handleAdminLogout}
                  navigateTo={navigateTo}
                />
              </Suspense>
            )}
          </>
        )}
      </main>
    </div>
  );
}

export default App;

import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { ArrowRight, AlertCircle, ShieldCheck } from 'lucide-react';

interface VoterLoginProps {
  navigateTo: (path: string) => void;
  onLoginSuccess: (user: any) => void;
}

export const VoterLogin: React.FC<VoterLoginProps> = ({ navigateTo, onLoginSuccess }) => {
  const [elections, setElections] = useState<any[]>([]);
  const [selectedElectionId, setSelectedElectionId] = useState<string>(() => sessionStorage.getItem('voter_election_id') || '');
  const [voterId, setVoterId] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch('/api/public/elections')
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        const list = data?.elections || [];
        setElections(list);
        if (!selectedElectionId && list.length > 0) {
          const match = list.find((e: any) => e.is_open || e.registration_open) || list[0];
          setSelectedElectionId(match.election_id);
        }
      })
      .catch(() => {});
  }, [selectedElectionId]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!voterId.trim() || !password) {
      setError('Please enter both your Voter ID and account password.');
      return;
    }

    setLoading(true);
    try {
      const res = await fetch('/api/voter/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          voter_id: voterId.trim(),
          password: password,
          election_id: selectedElectionId || undefined,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Authentication failed. Please check your credentials.');
      }

      // Store voter session
      sessionStorage.setItem('securevote_voter_token', data.token);
      sessionStorage.setItem('voter_session_token', data.token);
      sessionStorage.setItem('securevote_voter_id', data.voter_id);
      sessionStorage.setItem('voter_id', data.voter_id);
      sessionStorage.setItem('securevote_voter_name', data.full_name);
      sessionStorage.setItem('securevote_voter_email', data.email);
      sessionStorage.setItem('voter_email', data.email);
      sessionStorage.setItem('voter_election_id', data.election_id || selectedElectionId);

      onLoginSuccess({
        voter_id: data.voter_id,
        full_name: data.full_name,
        email: data.email,
        election_id: data.election_id || selectedElectionId,
        token: data.token,
      });

      navigateTo('/user/overview');
    } catch (err: any) {
      setError(err.message || 'Unable to sign in. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center p-4 sm:p-8 bg-paper">
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-md bg-paper border border-line rounded p-8 sm:p-10"
      >
        <div className="mb-8">
          <div className="flex items-center gap-2 text-xs text-text-muted uppercase tracking-wider font-mono mb-2">
            <ShieldCheck className="w-4 h-4 text-accent" />
            <span>Voter Authentication</span>
          </div>
          <h1 className="font-display text-3xl sm:text-4xl font-semibold text-ink tracking-tight">
            Sign in to vote
          </h1>
          <p className="text-text-muted text-sm mt-2">
            Access your voter dashboard, review official schedule updates, and prepare to cast your ballot.
          </p>
        </div>

        {error && (
          <div className="mb-6 p-4 rounded bg-paper-2 border border-danger/40 text-danger text-xs flex items-start gap-2.5">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          {elections.length > 1 && (
            <div>
              <label htmlFor="login-election-select" className="block text-xs font-medium text-ink uppercase tracking-wider mb-1.5 font-mono">
                Election
              </label>
              <select
                id="login-election-select"
                value={selectedElectionId}
                onChange={(e) => setSelectedElectionId(e.target.value)}
                className="w-full px-3.5 py-2.5 bg-paper border border-line rounded text-sm text-ink focus:bg-white transition"
              >
                {elections.map((el) => (
                  <option key={el.election_id} value={el.election_id}>
                    {el.title} ({el.status})
                  </option>
                ))}
              </select>
            </div>
          )}

          <div>
            <label className="block text-xs font-medium text-ink uppercase tracking-wider mb-1.5 font-mono">
              Voter ID
            </label>
            <input
              type="text"
              value={voterId}
              onChange={(e) => setVoterId(e.target.value)}
              placeholder="e.g. voter-priya"
              required
              autoFocus
              className="w-full px-3.5 py-2.5 bg-paper border border-line rounded text-sm text-ink placeholder-text-muted/60 focus:bg-white transition"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-ink uppercase tracking-wider mb-1.5 font-mono">
              Account Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              className="w-full px-3.5 py-2.5 bg-paper border border-line rounded text-sm text-ink placeholder-text-muted/60 focus:bg-white transition"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 px-4 bg-primary text-white text-sm font-medium rounded hover:bg-primary-hover transition flex items-center justify-center gap-2 disabled:opacity-60"
          >
            {loading ? (
              <span>Authenticating...</span>
            ) : (
              <>
                <span>Sign in to Voter Portal</span>
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </form>

        <div className="mt-8 pt-6 border-t border-line text-center">
          <p className="text-xs text-text-muted">
            Not registered yet?{' '}
            <button
              type="button"
              onClick={() => navigateTo('/user/register')}
              className="text-ink font-medium underline underline-offset-4 hover:text-accent transition"
            >
              Register for election
            </button>
          </p>
        </div>
      </motion.div>
    </div>
  );
};

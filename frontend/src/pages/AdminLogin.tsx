import React, { useState } from 'react';
import { AlertCircle, ArrowLeft } from 'lucide-react';
import { APP_NAME } from '../constants';
import { FormInput, PasswordInput } from '../components/FormControls';
import { formatApiError } from '../utils/apiError';

interface AdminLoginProps {
  onLoginSuccess: () => void;
  onCancel: () => void;
}

export const AdminLogin: React.FC<AdminLoginProps> = ({ onLoginSuccess, onCancel }) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!username.trim() || !password.trim()) {
      setError('Please enter both administrative username and password.');
      return;
    }

    setIsLoading(true);
    try {
      const res = await fetch('/api/admin/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: username.trim(),
          password: password.trim(),
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(formatApiError(data).message || 'Invalid administrative credentials');
      }

      sessionStorage.setItem('ciphervote_admin_token', data.token);
      sessionStorage.setItem('ciphervote_admin_user', username.trim());
      onLoginSuccess();
    } catch (err: any) {
      setError(err.message || 'Login failed');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-ink text-on-ink flex flex-col justify-center items-center px-4 py-12">
      <div className="w-full max-w-md">
        <button
          type="button"
          onClick={onCancel}
          className="text-xs text-on-ink/60 hover:text-on-ink flex items-center gap-1.5 transition mb-6 font-mono"
        >
          <ArrowLeft className="w-3.5 h-3.5" /> Return to Gateway
        </button>

        <div className="border border-ink-3 bg-ink-2 rounded-xl p-8 shadow-2xl">
          <div className="flex items-center gap-2 mb-2">
            <span className="w-2 h-2 rounded-full bg-accent" />
            <span className="text-xs font-mono tracking-widest text-on-ink/50 uppercase">Restricted Area</span>
          </div>

          <h1 className="font-display text-2xl font-bold text-white mb-2">
            {APP_NAME} Administration
          </h1>
          <p className="text-xs text-on-ink/60 mb-6 leading-relaxed">
            Authorized portal for election authorities, cryptographic threshold management, and voting lifecycle operations.
          </p>

          {error && (
            <div className="mb-6 p-3.5 rounded bg-red-950/60 border border-red-800 text-red-200 text-xs flex items-start gap-2.5">
              <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5 text-red-400" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <FormInput
              label="Username"
              type="text"
              name="username"
              id="admin-username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="admin"
              autoFocus
              required
              variant="dark"
              autoComplete="username"
            />

            <PasswordInput
              label="Password"
              name="password"
              id="admin-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••••"
              required
              variant="dark"
              autoComplete="current-password"
            />

            <div className="pt-2">
              <button
                type="submit"
                disabled={isLoading}
                className="w-full py-2.5 px-4 bg-on-ink text-ink font-semibold rounded hover:bg-white transition text-xs font-mono uppercase tracking-wider flex items-center justify-center disabled:opacity-50"
              >
                {isLoading ? 'Authenticating...' : 'Sign In to Console'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};

import React, { useState, useEffect, useCallback } from 'react';
import { ArrowLeft, Mail, AlertCircle } from 'lucide-react';

interface NotificationItem {
  id: string;
  type: string;
  subject: string;
  message: string;
  created_at: string;
  read: boolean;
}

interface VoterNotificationsProps {
  navigateTo: (path: string) => void;
  electionId?: string;
}

export const VoterNotifications: React.FC<VoterNotificationsProps> = ({ navigateTo, electionId = '' }) => {
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchNotifications = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    const voterToken = sessionStorage.getItem('voter_session_token');
    if (!voterToken) {
      setIsLoading(false);
      return;
    }

    try {
      const query = electionId ? `?election_id=${encodeURIComponent(electionId)}` : '';
      const res = await fetch(`/api/voter/notifications${query}`, {
        headers: {
          'Authorization': `Bearer ${voterToken}`,
        },
      });
      if (res.ok) {
        const data = await res.json();
        setNotifications(data.notifications || []);
      } else {
        setError('Could not fetch notifications.');
      }
    } catch (e: any) {
      setError(e.message || 'Network error fetching notifications');
    } finally {
      setIsLoading(false);
    }
  }, [electionId]);

  useEffect(() => {
    fetchNotifications();
  }, [fetchNotifications]);

  const markAllRead = async () => {
    const voterToken = sessionStorage.getItem('voter_session_token');
    if (!voterToken) return;

    try {
      await fetch('/api/voter/notifications/mark-all-read', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${voterToken}`,
        },
      });
      setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="max-w-3xl mx-auto px-6 py-12">
      <div className="mb-8 flex items-center justify-between border-b border-line pb-4">
        <div>
          <span className="text-xs uppercase tracking-widest text-ink/50 font-mono">Voter Communications</span>
          <h1 className="font-display text-2xl font-bold text-ink mt-0.5">Inbox & Bulletins</h1>
        </div>
        <div className="flex items-center gap-4">
          {notifications.some((n) => !n.read) && (
            <button
              type="button"
              onClick={markAllRead}
              className="text-xs text-ink/70 hover:text-ink font-mono underline underline-offset-4"
            >
              Mark all as read
            </button>
          )}
          <button
            type="button"
            onClick={() => navigateTo('/user/overview')}
            className="text-xs text-ink/60 hover:text-ink transition flex items-center gap-1.5"
          >
            <ArrowLeft className="w-3.5 h-3.5" /> Return
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-6 p-4 rounded border border-red-300 bg-red-50 text-red-800 text-sm flex items-center gap-3">
          <AlertCircle className="w-4 h-4 text-red-600" />
          <span>{error}</span>
        </div>
      )}

      {isLoading ? (
        <div className="py-12 text-center text-sm text-ink/50 font-mono">Loading communications...</div>
      ) : notifications.length === 0 ? (
        <div className="border border-line bg-paper rounded-lg p-12 text-center">
          <Mail className="w-8 h-8 text-ink/30 mx-auto mb-3" />
          <h3 className="font-display text-base font-bold text-ink mb-1">No notifications yet</h3>
          <p className="text-xs text-ink/60 max-w-sm mx-auto">
            You will receive election schedule updates, time-lock milestones, and registration confirmations here.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {notifications.map((item) => (
            <div
              key={item.id}
              className={`p-5 rounded-lg border transition ${
                item.read ? 'bg-paper/60 border-line text-ink/70' : 'bg-white border-ink/40 text-ink shadow-sm'
              }`}
            >
              <div className="flex items-start justify-between gap-4 mb-2">
                <div className="flex items-center gap-2">
                  {!item.read && <span className="w-2 h-2 rounded-full bg-accent inline-block" />}
                  <h4 className="text-sm font-semibold">{item.subject}</h4>
                </div>
                <span className="text-[11px] font-mono text-ink/40 whitespace-nowrap">
                  {new Date(item.created_at).toLocaleDateString(undefined, {
                    month: 'short',
                    day: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </span>
              </div>
              <p className="text-xs leading-relaxed text-ink/80 whitespace-pre-wrap">{item.message}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

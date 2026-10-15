import { useState, useEffect, useCallback, useRef } from 'react';
import { APP_NAME } from '../constants';

export interface ElectionData {
  election_id: string;
  title: string;
  status: string;
  is_open: boolean;
  scheduled_start?: string | null;
  scheduled_end?: string | null;
  timezone?: string;
  formatted_window?: string;
  trustee_threshold?: number;
  num_trustees?: number;
  total_ballots?: number;
  actual_open_at?: string | null;
  actual_close_at?: string | null;
  results_published_at?: string | null;
}

export function useElection(electionId?: string, isAdmin: boolean = false) {
  const [election, setElection] = useState<ElectionData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const isMounted = useRef(true);

  const fetchElection = useCallback(async (targetId?: string) => {
    const id = targetId || electionId;
    if (!id) {
      setLoading(false);
      return;
    }

    try {
      const res = await fetch(`/api/public/status?election_id=${encodeURIComponent(id)}`);
      if (!isMounted.current) return;

      if (!res.ok) {
        if (res.status === 404) {
          setError(`Election "${id}" not found.`);
        } else {
          setError(`Failed to load election details (${res.status}).`);
        }
        setElection(null);
        setLoading(false);
        return;
      }

      const data = await res.json();
      if (!isMounted.current) return;

      setElection({
        election_id: data.election_id,
        title: data.title || data.election_id,
        status: data.status,
        is_open: data.is_open,
        scheduled_start: data.scheduled_start,
        scheduled_end: data.scheduled_end,
        timezone: data.timezone || 'UTC',
        formatted_window: data.formatted_window || 'Dates to be announced',
        trustee_threshold: data.trustee_threshold,
        total_ballots: data.bulletin_board_length,
        actual_open_at: data.actual_open_at,
        actual_close_at: data.actual_close_at,
        results_published_at: data.results_published_at,
      });
      setError(null);
      setLoading(false);

      // Synchronize document title
      const titlePrefix = data.title || data.election_id;
      if (isAdmin) {
        document.title = `${titlePrefix} - Admin | ${APP_NAME}`;
      } else {
        document.title = `${titlePrefix} - ${APP_NAME}`;
      }
    } catch (err: any) {
      if (isMounted.current) {
        setError(err.message || 'Network error fetching election.');
        setLoading(false);
      }
    }
  }, [electionId, isAdmin]);

  useEffect(() => {
    isMounted.current = true;
    setLoading(true);
    fetchElection();

    // Poll every 10 seconds per requirements
    const timer = setInterval(() => {
      fetchElection();
    }, 10000);

    return () => {
      isMounted.current = false;
      clearInterval(timer);
    };
  }, [fetchElection]);

  return {
    election,
    electionId: election?.election_id || electionId || '',
    title: election?.title || electionId || '',
    status: election?.status || 'REGISTRATION',
    isOpen: Boolean(election?.is_open),
    formattedWindow: election?.formatted_window || 'Dates to be announced',
    loading,
    error,
    refresh: fetchElection,
  };
}

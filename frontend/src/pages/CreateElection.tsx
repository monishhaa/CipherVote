import React, { useState } from 'react';
import { ArrowLeft, Plus, Trash2, AlertCircle } from 'lucide-react';
import { FormInput, FormTextarea, CustomSelect } from '../components/FormControls';
import { formatApiError } from '../utils/apiError';

interface EditElectionSeed {
  election_id: string;
  title: string;
  description?: string;
  timezone?: string;
  candidates?: { name: string }[];
}

interface CreateElectionProps {
  onSuccess: (electionId: string) => void;
  onCancel: () => void;
  editElection?: EditElectionSeed | null;
}

const COMMON_TIMEZONES = [
  { value: 'UTC', label: 'UTC (Coordinated Universal Time)' },
  { value: 'Asia/Kolkata', label: 'Asia/Kolkata (IST +05:30)' },
  { value: 'America/New_York', label: 'America/New_York (EST/EDT -05:00)' },
  { value: 'America/Los_Angeles', label: 'America/Los_Angeles (PST/PDT -08:00)' },
  { value: 'America/Chicago', label: 'America/Chicago (CST/CDT -06:00)' },
  { value: 'Europe/London', label: 'Europe/London (GMT/BST +00:00)' },
  { value: 'Europe/Paris', label: 'Europe/Paris (CET/CEST +01:00)' },
  { value: 'Asia/Tokyo', label: 'Asia/Tokyo (JST +09:00)' },
  { value: 'Asia/Singapore', label: 'Asia/Singapore (SGT +08:00)' },
  { value: 'Australia/Sydney', label: 'Australia/Sydney (AEST/AEDT +10:00)' },
];

export const CreateElection: React.FC<CreateElectionProps> = ({ onSuccess, onCancel, editElection = null }) => {
  const [title, setTitle] = useState(editElection?.title || '');
  const [description, setDescription] = useState(editElection?.description || '');
  const [candidates, setCandidates] = useState<string[]>(
    editElection?.candidates?.length ? editElection.candidates.map((c) => c.name) : ['', '']
  );
  const [timezoneStr, setTimezoneStr] = useState<string>(() => {
    if (editElection?.timezone) return editElection.timezone;
    try {
      return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
    } catch {
      return 'UTC';
    }
  });

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleAddCandidate = () => {
    if (candidates.length >= 10) return;
    setCandidates([...candidates, '']);
  };

  const handleRemoveCandidate = (index: number) => {
    if (candidates.length <= 2) {
      setError('An election must have at least 2 candidates.');
      return;
    }
    const updated = candidates.filter((_, i) => i !== index);
    setCandidates(updated);
  };

  const handleCandidateChange = (index: number, val: string) => {
    const updated = [...candidates];
    updated[index] = val;
    setCandidates(updated);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const cleanTitle = title.trim();
    if (!cleanTitle) {
      setError('Election title is required.');
      return;
    }

    const cleanCandidates: { name: string }[] = [];
    const seen = new Set<string>();

    for (let i = 0; i < candidates.length; i++) {
      const name = candidates[i].trim();
      if (!name) {
        setError(`Candidate #${i + 1} name cannot be empty.`);
        return;
      }
      if (seen.has(name.toLowerCase())) {
        setError(`Duplicate candidate name "${name}". Candidate names must be unique.`);
        return;
      }
      seen.add(name.toLowerCase());
      cleanCandidates.push({ name });
    }

    if (cleanCandidates.length < 2 || cleanCandidates.length > 10) {
      setError('Please provide between 2 and 10 candidates.');
      return;
    }

    setIsLoading(true);
    try {
      const token = sessionStorage.getItem('ciphervote_admin_token') || '';
      const payload = {
        title: cleanTitle,
        description: description.trim() || undefined,
        candidates: cleanCandidates,
        timezone: timezoneStr,
      };
      const res = await fetch(
        editElection
          ? `/api/admin/elections/${encodeURIComponent(editElection.election_id)}`
          : '/api/admin/elections',
        {
          method: editElection ? 'PUT' : 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify(payload),
        }
      );

      const data = await res.json();
      if (!res.ok) {
        throw new Error(formatApiError(data).message || 'Failed to save election.');
      }

      onSuccess(data.election_id);
    } catch (err: any) {
      setError(err.message || 'Error creating election');
    } finally {
      setIsLoading(false);
    }
  };

  const timezoneOptions = COMMON_TIMEZONES.some((tz) => tz.value === timezoneStr)
    ? COMMON_TIMEZONES
    : [{ value: timezoneStr, label: timezoneStr }, ...COMMON_TIMEZONES];

  return (
    <div className="max-w-2xl mx-auto py-8 px-4">
      <button
        type="button"
        onClick={onCancel}
        className="text-xs text-on-ink/60 hover:text-white flex items-center gap-1.5 transition mb-6 font-mono"
      >
        <ArrowLeft className="w-3.5 h-3.5" /> Back to Elections
      </button>

      <div className="bg-ink-2 border border-ink-3 rounded-xl p-8 shadow-2xl">
        <div className="border-b border-ink-3 pb-4 mb-6">
          <span className="text-[10px] font-mono text-on-ink/50 uppercase tracking-widest">Election Setup</span>
          <h1 className="font-display text-2xl font-bold text-white mt-1">
            {editElection ? 'Edit Election' : 'Create New Election'}
          </h1>
          <p className="text-xs text-on-ink/60 mt-1">
            Configure election metadata, candidate options, and election timezone. Schedule dates are configured separately in the Voting Schedule.
          </p>
        </div>

        {error && (
          <div className="mb-6 p-3.5 rounded bg-red-950/60 border border-red-800 text-red-200 text-xs flex items-start gap-2.5">
            <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5 text-red-400" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-6">
          <FormInput
            label="Election Title *"
            placeholder="e.g. Faculty Senate Presidential Election 2026"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
            variant="dark"
            helpText="The public title displayed on voter ballots and audit certificates."
          />

          <FormTextarea
            label="Description (Optional)"
            placeholder="Provide context, eligibility guidelines, or constitutional bylaws reference..."
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            variant="dark"
          />

          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="block text-[11px] font-mono uppercase tracking-wider text-on-ink/80">
                Candidates ({candidates.length}/10) *
              </label>
              {candidates.length < 10 && (
                <button
                  type="button"
                  onClick={handleAddCandidate}
                  className="text-xs font-mono text-accent hover:text-accent/80 flex items-center gap-1"
                >
                  <Plus className="w-3.5 h-3.5" /> Add Candidate
                </button>
              )}
            </div>
            <p className="text-[11px] text-on-ink/50 mb-3">
              Minimum 2, maximum 10 unique candidates.
            </p>

            <div className="space-y-2.5">
              {candidates.map((c, idx) => (
                <div key={idx} className="flex items-center gap-2">
                  <span className="text-xs font-mono text-on-ink/40 w-6">#{idx + 1}</span>
                  <input
                    type="text"
                    value={c}
                    onChange={(e) => handleCandidateChange(idx, e.target.value)}
                    placeholder={`Candidate name ${idx + 1}`}
                    required
                    className="flex-1 px-3.5 py-2 bg-ink text-white border border-ink-3 rounded text-sm focus:outline-none focus:border-on-ink"
                  />
                  {candidates.length > 2 && (
                    <button
                      type="button"
                      onClick={() => handleRemoveCandidate(idx)}
                      className="p-2 text-on-ink/40 hover:text-red-400 transition"
                      title="Remove candidate"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>

          <CustomSelect
            label="Election Timezone"
            options={timezoneOptions}
            value={timezoneStr}
            onChange={(val) => setTimezoneStr(String(val))}
            searchable
            variant="dark"
          />

          <div className="pt-4 border-t border-ink-3 flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={onCancel}
              className="px-4 py-2.5 bg-ink border border-ink-3 rounded text-xs text-on-ink/70 hover:text-white font-mono"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isLoading}
              className="px-5 py-2.5 bg-on-ink text-ink font-semibold rounded text-xs font-mono uppercase tracking-wider hover:bg-white transition disabled:opacity-50"
            >
              {isLoading ? 'Saving...' : editElection ? 'Save Election' : 'Create Election & Proceed'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

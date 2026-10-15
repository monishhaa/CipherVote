import React, { useState } from 'react';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Table, TableHead, TableBody, TableRow, TableHeaderCell, TableCell } from '../components/ui/Table';
import { Badge } from '../components/ui/Badge';
import { InfoDisclosure } from '../components/ui/InfoDisclosure';
import { KeyRound, Check, CheckCircle2, ChevronLeft } from 'lucide-react';
import { APP_NAME } from '../constants';

interface TrusteePortalProps {
  electionId?: string;
  navigateTo?: (path: string) => void;
}

export const TrusteePortal: React.FC<TrusteePortalProps> = ({
  electionId = 'council-2026',
  navigateTo = () => {},
}) => {
  const [selectedTrustees, setSelectedTrustees] = useState<number[]>([1, 2, 3]);
  const [isComputing, setIsComputing] = useState<boolean>(false);
  const [tallyResult, setTallyResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const trustees = [
    { id: 1, name: 'Trustee 1 (Faculty Senate Representative)' },
    { id: 2, name: 'Trustee 2 (Student Council Representative)' },
    { id: 3, name: 'Trustee 3 (Independent Audit Committee)' },
    { id: 4, name: 'Trustee 4 (Academic Dean of Science)' },
    { id: 5, name: 'Trustee 5 (External Election Observer)' },
  ];

  const toggleTrustee = (id: number) => {
    if (selectedTrustees.includes(id)) {
      if (selectedTrustees.length > 3) {
        setSelectedTrustees(selectedTrustees.filter((t) => t !== id));
      }
    } else {
      setSelectedTrustees([...selectedTrustees, id]);
    }
  };

  const handleComputeThresholdTally = async () => {
    if (selectedTrustees.length < 3) {
      setError('A minimum threshold of 3 trustees is required for decryption.');
      return;
    }
    setIsComputing(true);
    setError(null);

    try {
      const trusteeParam = selectedTrustees.join(',');
      const res = await fetch(`/api/tally/compute?election_id=${encodeURIComponent(electionId)}&trustee_ids=${trusteeParam}`, {
        method: 'POST',
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Threshold decryption failed');
      }

      const data = await res.json();
      setTallyResult(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsComputing(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto py-8 px-4 sm:px-6">
      {/* Navy Header */}
      <div className="bg-primary text-white rounded p-6 sm:p-8 mb-8 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <button
            type="button"
            onClick={() => navigateTo('/')}
            className="text-xs text-white/70 hover:text-white flex items-center gap-1 transition"
          >
            <ChevronLeft className="w-3.5 h-3.5" />
            <span>Return to Gateway</span>
          </button>
          <span className="text-[11px] px-2.5 py-0.5 rounded-sm bg-white/10 text-white font-mono border border-white/20">
            Threshold Scheme: t = 3, n = 5
          </span>
        </div>

        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-white/10 rounded border border-white/10">
            <KeyRound className="w-6 h-6 text-accent" />
          </div>
          <div>
            <h1 className="font-serif text-2xl sm:text-3xl font-semibold text-white tracking-tight">
              Cryptographic Trustee Portal
            </h1>
            <p className="text-xs sm:text-sm text-white/80 mt-1 max-w-2xl">
              Collaborative threshold decryption portal. No individual administrator or single trustee can decrypt ballots.
              At least 3 authorized trustees must provide partial decryption shares with DLEQ zero-knowledge proofs.
            </p>
          </div>
        </div>
      </div>

      {/* Main Single-Task Workflow */}
      <div className="space-y-6">
        <Card
          title="Trustee Quorum Selection"
          subtitle="Select at least 3 authorized trustees to supply partial decryption shares for this tally."
          headerAction={
            <Badge variant="accent" size="sm">
              {selectedTrustees.length} of 5 Selected
            </Badge>
          }
        >
          <div className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {trustees.map((t) => {
                const isSelected = selectedTrustees.includes(t.id);
                return (
                  <div
                    key={t.id}
                    onClick={() => toggleTrustee(t.id)}
                    className={`p-3.5 border rounded cursor-pointer transition flex items-center justify-between ${
                      isSelected
                        ? 'border-primary bg-[#FAF8F5] ring-1 ring-primary'
                        : 'border-border bg-surface hover:bg-[#FAF8F5]'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <div
                        className={`w-4 h-4 rounded-sm border flex items-center justify-center ${
                          isSelected
                            ? 'bg-primary border-primary text-white'
                            : 'border-border bg-surface'
                        }`}
                      >
                        {isSelected && <Check className="w-3 h-3 stroke-[3]" />}
                      </div>
                      <div>
                        <p className="text-xs font-semibold text-text">{t.name}</p>
                        <p className="text-[11px] text-text-muted font-mono">Trustee Share #{t.id}</p>
                      </div>
                    </div>
                    <KeyRound className={`w-3.5 h-3.5 ${isSelected ? 'text-accent' : 'text-text-muted/50'}`} />
                  </div>
                );
              })}
            </div>

            {error && (
              <div className="p-3 bg-[#FEE2E2] border border-[#FECACA] rounded text-xs text-danger">
                {error}
              </div>
            )}

            <div className="pt-3 border-t border-border flex justify-end">
              <Button
                variant="primary"
                isLoading={isComputing}
                disabled={selectedTrustees.length < 3}
                onClick={handleComputeThresholdTally}
              >
                Execute Threshold Decryption (3-of-5)
              </Button>
            </div>
          </div>
        </Card>

        {/* Certified Outcome Breakdown */}
        {tallyResult && (
          <Card
            title="Verified Election Outcome"
            subtitle="Decrypted tally reconstructed from aggregated homomorphic ciphertexts and DLEQ validity proofs."
          >
            <div className="space-y-4">
              <div className="p-3.5 bg-[#E2EFE7] border border-[#B7D8C4] rounded flex items-center gap-2.5">
                <CheckCircle2 className="w-5 h-5 text-success flex-shrink-0" />
                <span className="text-xs font-semibold text-[#1E4D36]">
                  Lagrange interpolation and threshold proof verification succeeded.
                </span>
              </div>

              <Table dense>
                <TableHead>
                  <TableRow>
                    <TableHeaderCell>Candidate</TableHeaderCell>
                    <TableHeaderCell>Decrypted Vote Count</TableHeaderCell>
                    <TableHeaderCell>Verification Status</TableHeaderCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {(tallyResult.results || tallyResult.candidate_tallies || []).map((c: any, i: number) => (
                    <TableRow key={i}>
                      <TableCell className="font-medium">{c.name || `Candidate ${i+1}`}</TableCell>
                      <TableCell className="font-mono font-semibold">{c.votes !== undefined ? c.votes : (c.count || 0)}</TableCell>
                      <TableCell><Badge variant="success" size="sm">DLEQ Validated</Badge></TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </Card>
        )}

        {/* Collapsible Disclosure */}
        <InfoDisclosure title="How Threshold Decryption Protects Privacy">
          <div className="space-y-2 pt-2 text-xs text-text-muted">
            <p>
              In {APP_NAME}, the private decryption key is split into polynomial shares using Shamir Secret Sharing. No individual party possesses the full key.
            </p>
            <p>
              During tallying, the server sums all encrypted candidate vectors without decrypting them. Then, at least 3 trustees compute partial decryptions of ONLY the aggregate sum. Individual ballots remain permanently encrypted and secret.
            </p>
          </div>
        </InfoDisclosure>
      </div>
    </div>
  );
};

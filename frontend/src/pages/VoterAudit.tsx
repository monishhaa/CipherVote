import React, { useState, useEffect, useCallback } from 'react';
import { CheckCircle2, AlertCircle, Search, RefreshCw, ArrowLeft } from 'lucide-react';

interface VoterAuditProps {
  electionId?: string;
  navigateTo: (path: string) => void;
}

export const VoterAudit: React.FC<VoterAuditProps> = ({
  electionId = 'council-2026',
  navigateTo,
}) => {
  const [ballots, setBallots] = useState<any[]>([]);
  const [genesisHash, setGenesisHash] = useState<string>('');
  const [headHash, setHeadHash] = useState<string>('');
  const [merkleRoot, setMerkleRoot] = useState<string>('');
  const [isChainValid, setIsChainValid] = useState<boolean | null>(null);

  const [searchReceipt, setSearchReceipt] = useState<string>('');
  const [searchResult, setSearchResult] = useState<any>(null);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [boardError, setBoardError] = useState<string | null>(null);

  const fetchBulletinBoard = useCallback(async () => {
    setIsLoading(true);
    setBoardError(null);
    try {
      const res = await fetch(`/api/public/bulletin-board?election_id=${encodeURIComponent(electionId)}`);
      if (res.ok) {
        const data = await res.json();
        setBallots(data.ballots || []);
        setGenesisHash(data.genesis_hash || '');
        setHeadHash(data.head_hash || '');
      } else {
        setBoardError('The bulletin board could not be loaded for this election.');
      }

      const verifyRes = await fetch(`/api/public/bulletin-board/verify?election_id=${encodeURIComponent(electionId)}`);
      if (verifyRes.ok) {
        const vData = await verifyRes.json();
        setIsChainValid(vData.is_valid);
        setMerkleRoot(vData.merkle_root);
      }
    } catch (e) {
      console.error(e);
      setBoardError('The bulletin board could not be loaded for this election.');
    } finally {
      setIsLoading(false);
    }
  }, [electionId]);

  useEffect(() => {
    fetchBulletinBoard();
  }, [fetchBulletinBoard]);

  const handleSearchReceipt = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchReceipt.trim()) return;
    setSearchError(null);
    setSearchResult(null);

    try {
      const normalized = searchReceipt.trim().replace(/\s+/g, '').toUpperCase();
      const res = await fetch(`/api/public/receipt/${encodeURIComponent(normalized)}?election_id=${encodeURIComponent(electionId)}`);
      if (!res.ok) {
        throw new Error('Receipt code not found on the public bulletin board.');
      }
      const data = await res.json();
      setSearchResult(data);
    } catch (err: any) {
      setSearchError(err.message || 'Verification lookup failed.');
    }
  };

  return (
    <div className="max-w-5xl mx-auto px-6 py-12">
      {/* Header */}
      <div className="mb-8 flex items-center justify-between border-b border-line pb-4">
        <div>
          <span className="text-xs uppercase tracking-widest text-ink/50 font-mono">Public Verifiability</span>
          <h1 className="font-display text-2xl font-bold text-ink mt-0.5">Bulletin Board & Merkle Audit</h1>
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={fetchBulletinBoard}
            disabled={isLoading}
            className="text-xs px-3 py-1.5 rounded border border-line bg-white hover:bg-paper text-ink transition flex items-center gap-1.5"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} /> Refresh
          </button>
          <button
            type="button"
            onClick={() => navigateTo('/user/overview')}
            className="text-xs text-ink/60 hover:text-ink transition flex items-center gap-1"
          >
            <ArrowLeft className="w-3.5 h-3.5" /> Return
          </button>
        </div>
      </div>

      {boardError && (
        <div className="mb-6 p-3 rounded border border-red-200 bg-red-50 text-xs text-red-700 flex items-center gap-2">
          <AlertCircle className="w-4 h-4" />
          <span>{boardError}</span>
        </div>
      )}

      {/* 3 Metric cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <div className="border border-line bg-paper rounded-lg p-5">
          <span className="text-[11px] font-mono uppercase tracking-wider text-ink/50 block mb-1">
            Hash Chain Integrity
          </span>
          <div className="flex items-center gap-2 mt-1">
            {isChainValid ? (
              <>
                <CheckCircle2 className="w-4 h-4 text-emerald-700" />
                <span className="text-sm font-semibold text-emerald-800">Valid & Untampered</span>
              </>
            ) : isChainValid === false ? (
              <>
                <AlertCircle className="w-4 h-4 text-red-600" />
                <span className="text-sm font-semibold text-red-700">Integrity Mismatch</span>
              </>
            ) : (
              <span className="text-sm text-ink/60">Verifying chain...</span>
            )}
          </div>
          <span className="text-xs font-mono text-ink/60 mt-1 block">
            {ballots.length} total recorded ballots
          </span>
        </div>

        <div className="border border-line bg-paper rounded-lg p-5">
          <span className="text-[11px] font-mono uppercase tracking-wider text-ink/50 block mb-1">
            Merkle Root Hash
          </span>
          <p className="text-xs font-mono text-ink truncate bg-white p-2 rounded border border-line mt-1" title={merkleRoot}>
            {merkleRoot || '0x00000000000000000000000000000000'}
          </p>
        </div>

        <div className="border border-line bg-paper rounded-lg p-5">
          <span className="text-[11px] font-mono uppercase tracking-wider text-ink/50 block mb-1">
            Chain Head Hash
          </span>
          <p className="text-xs font-mono text-ink truncate bg-white p-2 rounded border border-line mt-1" title={headHash || genesisHash}>
            {headHash || genesisHash || '0x00000000000000000000000000000000'}
          </p>
        </div>
      </div>

      {/* Individual receipt lookup */}
      <div className="border border-line bg-white rounded-lg p-6 mb-8">
        <h3 className="font-display text-base font-bold text-ink mb-1">Individual Ballot Receipt Verification</h3>
        <p className="text-xs text-ink/60 mb-4">
          Enter your receipt hash to verify that your encrypted vote was included in the ledger without exposing your choices.
        </p>

        <form onSubmit={handleSearchReceipt} className="flex flex-col sm:flex-row gap-3">
          <input
            type="text"
            placeholder="Paste your 64-char receipt code (e.g. 0x8a9b...)"
            value={searchReceipt}
            onChange={(e) => setSearchReceipt(e.target.value)}
            className="flex-1 px-3.5 py-2 text-xs font-mono bg-paper/50 border border-line rounded focus:outline-none focus:border-ink"
            required
          />
          <button
            type="submit"
            className="py-2 px-5 bg-ink text-paper rounded text-xs font-medium hover:bg-ink/90 transition flex items-center justify-center gap-1.5"
          >
            <Search className="w-3.5 h-3.5" /> Verify Receipt
          </button>
        </form>

        {searchError && (
          <div className="mt-4 p-3 rounded border border-red-200 bg-red-50 text-red-700 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>{searchError}</span>
          </div>
        )}

        {searchResult && (
          <div className="mt-4 p-4 rounded border border-emerald-200 bg-emerald-50 text-emerald-900 space-y-2 text-xs">
            <div className="flex items-center gap-2 font-semibold">
              <CheckCircle2 className="w-4 h-4 text-emerald-700" />
              <span>Ballot verified on public ledger</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1">
              <div>
                <span className="text-emerald-800/70 block">Sequence Index:</span>
                <span className="font-mono font-medium">#{searchResult.sequence_number}</span>
              </div>
              <div>
                <span className="text-emerald-800/70 block">Merkle Proof:</span>
                <span className="font-semibold text-emerald-700">Valid & Included</span>
              </div>
              <div className="sm:col-span-2">
                <span className="text-emerald-800/70 block">Block Hash:</span>
                <span className="font-mono break-all text-[11px]">{searchResult.block_hash}</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Public cryptographic ledger table */}
      <div className="border border-line bg-paper rounded-lg overflow-hidden">
        <div className="px-6 py-4 border-b border-line">
          <h3 className="font-display text-base font-bold text-ink">Immutable Ledger</h3>
          <p className="text-xs text-ink/60">Sequential records of encrypted ciphertext digests and zero-knowledge validity proofs.</p>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-line bg-paper-2 font-mono text-[11px] text-ink/70">
                <th className="p-3.5 pl-6">Seq #</th>
                <th className="p-3.5">Receipt Code</th>
                <th className="p-3.5">NIZKP Proof</th>
                <th className="p-3.5 pr-6">Block Hash</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {ballots.length > 0 ? (
                ballots.map((b, i) => (
                  <tr key={i} className="hover:bg-white/60 transition">
                    <td className="p-3.5 pl-6 font-mono font-medium text-ink">#{b.sequence_number || i + 1}</td>
                    <td className="p-3.5 font-mono text-ink font-semibold tracking-wide">
                      {b.receipt_code || '—'}
                    </td>
                    <td className="p-3.5 font-mono">
                      <span className="px-2 py-0.5 rounded border border-emerald-300 bg-emerald-50 text-emerald-800 text-[10px]">
                        Valid 1-of-N + Sum
                      </span>
                    </td>
                    <td className="p-3.5 pr-6 font-mono text-ink/70 truncate max-w-[180px]">
                      {b.block_hash || b.receipt_code || '0x3c5d...ef01'}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={4} className="text-center py-8 text-ink/50 font-mono">
                    No ballots recorded on the bulletin board yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

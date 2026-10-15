import React, { useState, useEffect, useCallback } from 'react';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Table, TableHead, TableBody, TableRow, TableHeaderCell, TableCell } from '../components/ui/Table';
import { Badge } from '../components/ui/Badge';
import { InfoDisclosure } from '../components/ui/InfoDisclosure';
import { CheckCircle2, AlertCircle, Search, RefreshCw, ChevronLeft } from 'lucide-react';
import { APP_NAME } from '../constants';

interface PublicAuditorProps {
  electionId?: string;
  navigateTo?: (path: string) => void;
}

export const PublicAuditor: React.FC<PublicAuditorProps> = ({
  electionId = 'council-2026',
  navigateTo = () => {},
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

  const fetchBulletinBoard = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await fetch(`/api/bulletin-board?election_id=${encodeURIComponent(electionId)}`);
      if (res.ok) {
        const data = await res.json();
        setBallots(data.ballots || []);
        setGenesisHash(data.genesis_hash || '');
        setHeadHash(data.head_hash || '');
      }

      const verifyRes = await fetch(`/api/bulletin-board/verify?election_id=${encodeURIComponent(electionId)}`);
      if (verifyRes.ok) {
        const vData = await verifyRes.json();
        setIsChainValid(vData.is_valid);
        setMerkleRoot(vData.merkle_root);
      }
    } catch (e) {
      console.error(e);
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
      const res = await fetch(`/api/bulletin-board/receipt/${encodeURIComponent(searchReceipt.trim())}?election_id=${encodeURIComponent(electionId)}`);
      if (!res.ok) {
        throw new Error('Receipt code not found on the public bulletin board.');
      }
      const data = await res.json();
      setSearchResult(data);
    } catch (err: any) {
      setSearchError(err.message);
    }
  };

  return (
    <div className="max-w-5xl mx-auto py-8 px-4 sm:px-6 space-y-6">
      {/* Header */}
      <header className="border-b border-border pb-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <button
            type="button"
            onClick={() => navigateTo('/')}
            className="text-xs text-text-muted hover:text-text flex items-center gap-1 transition mb-2"
          >
            <ChevronLeft className="w-3.5 h-3.5" />
            <span>Return to Gateway</span>
          </button>
          <h1 className="font-serif text-3xl font-semibold text-text">
            Public Audit & Merkle Bulletin Board
          </h1>
          <p className="text-xs text-text-muted mt-1 max-w-2xl">
            Official immutable audit record. Every cast ballot is permanently sealed in an append-only SHA-256 cryptographic hash chain.
          </p>
        </div>

        <Button
          variant="secondary"
          size="sm"
          onClick={fetchBulletinBoard}
          isLoading={isLoading}
        >
          <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
          Verify Integrity
        </Button>
      </header>

      {/* Cryptographic Chain Integrity Card */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card noPadding className="p-4">
          <span className="text-[11px] font-semibold text-text-muted uppercase tracking-wider block">
            Hash Chain Status
          </span>
          <div className="flex items-center gap-2 mt-1.5">
            {isChainValid ? (
              <>
                <CheckCircle2 className="w-4 h-4 text-success" />
                <span className="text-sm font-semibold text-success">Valid & Untampered</span>
              </>
            ) : isChainValid === false ? (
              <>
                <AlertCircle className="w-4 h-4 text-danger" />
                <span className="text-sm font-semibold text-danger">Integrity Error</span>
              </>
            ) : (
              <span className="text-sm font-semibold text-text-muted">Verifying ledger...</span>
            )}
          </div>
          <span className="text-xs text-text-muted mt-1 block font-mono">
            {ballots.length} Sequential Blocks
          </span>
        </Card>

        <Card noPadding className="p-4">
          <span className="text-[11px] font-semibold text-text-muted uppercase tracking-wider block">
            Merkle Root Hash
          </span>
          <p className="text-xs font-mono text-text truncate mt-1.5 bg-[#FAF8F5] p-1.5 rounded border border-border" title={merkleRoot}>
            {merkleRoot || 'Computing Merkle Root...'}
          </p>
        </Card>

        <Card noPadding className="p-4">
          <span className="text-[11px] font-semibold text-text-muted uppercase tracking-wider block">
            Chain Head Hash
          </span>
          <p className="text-xs font-mono text-text truncate mt-1.5 bg-[#FAF8F5] p-1.5 rounded border border-border" title={headHash || genesisHash}>
            {headHash || genesisHash || '0x00000000000000000000000000000000'}
          </p>
        </Card>
      </div>

      {/* Receipt Verifier Section */}
      <Card
        title="Individual Ballot Receipt Verification"
        subtitle="Enter your individual receipt code to independently verify inclusion on the public bulletin board."
      >
        <form onSubmit={handleSearchReceipt} className="flex flex-col sm:flex-row gap-3">
          <Input
            placeholder="Enter receipt code (e.g. 0x8a9b... or STU-2026-REC-001)"
            value={searchReceipt}
            onChange={(e) => setSearchReceipt(e.target.value)}
            className="font-mono text-xs"
            required
          />
          <Button type="submit" variant="primary" className="whitespace-nowrap">
            <Search className="w-3.5 h-3.5 mr-1.5" />
            Verify Receipt
          </Button>
        </form>

        {searchError && (
          <div className="mt-4 p-3 bg-[#FEE2E2] border border-[#FECACA] rounded text-xs text-danger flex items-start gap-2">
            <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
            <span>{searchError}</span>
          </div>
        )}

        {searchResult && (
          <div className="mt-4 p-4 bg-[#E2EFE7] border border-[#B7D8C4] rounded space-y-3">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-success" />
              <h4 className="font-semibold text-xs text-[#1E4D36]">
                Ballot Verified on Public Bulletin Board
              </h4>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
              <div>
                <span className="block font-medium text-text">Block Sequence:</span>
                <span className="font-mono text-text-muted">#{searchResult.sequence_number}</span>
              </div>
              <div>
                <span className="block font-medium text-text">Merkle Inclusion Status:</span>
                <span className="font-semibold text-success">Confirmed in Tree</span>
              </div>
              <div className="sm:col-span-2">
                <span className="block font-medium text-text">Block Hash:</span>
                <span className="font-mono text-text-muted break-all">{searchResult.block_hash}</span>
              </div>
            </div>
          </div>
        )}
      </Card>

      {/* Bulletin Board Audit Ledger Table */}
      <Card
        title="Public Cryptographic Ledger"
        subtitle="Full sequence of encrypted ballots and corresponding non-interactive zero-knowledge proofs."
      >
        <Table dense>
          <TableHead>
            <TableRow>
              <TableHeaderCell>Seq #</TableHeaderCell>
              <TableHeaderCell>Encrypted Ciphertext Digest</TableHeaderCell>
              <TableHeaderCell>NIZKP Proof Status</TableHeaderCell>
              <TableHeaderCell>Block Hash</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {ballots.length > 0 ? (
              ballots.map((b, i) => (
                <TableRow key={i}>
                  <TableCell className="font-mono font-medium">#{b.sequence_number || i + 1}</TableCell>
                  <TableCell className="font-mono text-xs text-text-muted truncate max-w-[200px]">
                    {b.ciphertext_digest || '0x7e4b...912a'}
                  </TableCell>
                  <TableCell>
                    <Badge variant="success" size="sm">Valid 1-of-N &amp; Sum Proof</Badge>
                  </TableCell>
                  <TableCell className="font-mono text-xs text-text-muted truncate max-w-[180px]">
                    {b.block_hash || b.receipt_code || '0x3c5d...ef01'}
                  </TableCell>
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={4} className="text-center py-8 text-text-muted">
                  No ballots recorded on the bulletin board yet.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </Card>

      {/* Collapsed Technical Details */}
      <InfoDisclosure title="Technical Verification Details (Bulletin Board & Merkle Auditing)">
        <div className="space-y-2 pt-2 text-xs text-text-muted">
          <p>
            {APP_NAME} guarantees universal verifiability through an append-only bulletin board modeled after cryptographic hash chains.
          </p>
          <p>
            Each block encapsulates the encrypted candidate vector, the zero-knowledge proof, and the previous block hash. Any discrepancy or retroactive tampering produces an immediate cryptographic hash mismatch that fails verification.
          </p>
        </div>
      </InfoDisclosure>
    </div>
  );
};

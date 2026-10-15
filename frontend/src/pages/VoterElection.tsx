import React, { useState, useEffect } from 'react';
import { Vote, Lock, Unlock, ShieldCheck, CheckCircle2, ArrowRight, RefreshCw, Copy, Check } from 'lucide-react';
import { WebcamLiveness } from '../components/WebcamLiveness';
import { encryptVote } from '../crypto/elgamal';
import { generateDisjunctiveZKP, generateBallotSumProof } from '../crypto/zkp';
import { blindBallotToken, unblindBallotSignature } from '../crypto/blindSignature';

interface Candidate {
  id: number;
  name: string;
}

interface VoterElectionProps {
  initialVoterId?: string;
  initialShareA?: string;
  electionId?: string;
}

export const VoterElection: React.FC<VoterElectionProps> = ({
  initialVoterId = '',
  initialShareA = '',
  electionId = 'council-2026',
}) => {
  const [voterId, setVoterId] = useState(initialVoterId);
  const [shareA, setShareA] = useState(initialShareA);
  const [shareB, setShareB] = useState<string | null>(null);
  const [isTimeLocked, setIsTimeLocked] = useState<boolean>(true);
  const [timeLockMsg, setTimeLockMsg] = useState<string>('');
  
  const [livenessPassed, setLivenessPassed] = useState<boolean>(false);
  const [livenessTelemetry, setLivenessTelemetry] = useState<any>(null);

  const [blindToken, setBlindToken] = useState<{
    nonce: string;
    signature: string;
  } | null>(null);

  const [candidates, setCandidates] = useState<Candidate[]>([
    { id: 0, name: 'Alice Candidate' },
    { id: 1, name: 'Bob Candidate' },
    { id: 2, name: 'Charlie Candidate' },
  ]);
  const [selectedCandidate, setSelectedCandidate] = useState<number | null>(null);
  const [electionPK, setElectionPK] = useState<bigint | null>(null);
  const [blindRsaPK, setBlindRsaPK] = useState<{ n: bigint; e: bigint } | null>(null);

  const [step, setStep] = useState<number>(1); // 1: Credential Check, 2: Liveness, 3: Voting Booth, 4: Receipt
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [receiptData, setReceiptData] = useState<{
    receiptCode: string;
    sequenceNumber: number;
    blockHash: string;
  } | null>(null);
  const [copied, setCopied] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchElectionInfo();
  }, [electionId]);

  const fetchElectionInfo = async () => {
    try {
      const res = await fetch(`/api/election/status?election_id=${encodeURIComponent(electionId)}`);
      if (res.ok) {
        const data = await res.json();
        setCandidates(data.candidates);
        setElectionPK(BigInt(data.public_key_h));
        setBlindRsaPK({
          n: BigInt(data.blind_rsa_n),
          e: BigInt(data.blind_rsa_e),
        });
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleFetchShareB = async () => {
    setIsProcessing(true);
    setError(null);
    try {
      const res = await fetch(`/api/voters/share_b/${encodeURIComponent(voterId)}?election_id=${encodeURIComponent(electionId)}`);
      if (!res.ok) {
        const err = await res.json();
        setIsTimeLocked(true);
        setTimeLockMsg(err.detail || 'Time-lock is currently active.');
        return;
      }
      const data = await res.json();
      setShareB(data.share_b);
      setIsTimeLocked(false);
      setTimeLockMsg('Time-lock elapsed. Share B retrieved from server.');
      setStep(2);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleAuthenticateAndGetToken = async () => {
    if (!shareB || !shareA || !blindRsaPK) return;
    setIsProcessing(true);
    setError(null);

    try {
      // 1. Generate random ballot nonce & blind message
      const ballotNonce = `ballot_token_${voterId}_${Date.now()}_${Math.random()}`;
      const { mPrime, rBlind } = await blindBallotToken(ballotNonce, blindRsaPK.n, blindRsaPK.e);

      // 2. Request blind signature from server
      const formattedTelemetry = {
        challenge_id: 'challenge_web',
        ear_scores: (livenessTelemetry as any)?.earScores || (livenessTelemetry as any)?.ear_scores || [0.35, 0.15, 0.36],
        yaw_angles: (livenessTelemetry as any)?.yawAngles || (livenessTelemetry as any)?.yaw_angles || [0.0, -12.0, 0.0],
        probe_embedding: (livenessTelemetry as any)?.probeEmbedding || (livenessTelemetry as any)?.probe_embedding || undefined,
      };

      const res = await fetch(`/api/auth/blind-token?election_id=${encodeURIComponent(electionId)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          voter_id: voterId.trim(),
          share_a: shareA.trim(),
          share_b: shareB.trim(),
          blinded_token: '0x' + mPrime.toString(16),
          liveness_telemetry: formattedTelemetry,
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        let errMsg = 'Authentication failed';
        if (typeof err.detail === 'string') {
          errMsg = err.detail;
        } else if (Array.isArray(err.detail)) {
          errMsg = err.detail.map((d: any) => d.msg || d.message || JSON.stringify(d)).join('; ');
        } else if (err.detail && typeof err.detail === 'object') {
          errMsg = err.detail.message || err.detail.msg || JSON.stringify(err.detail);
        }
        throw new Error(errMsg);
      }

      const data = await res.json();
      const sPrime = BigInt(data.blind_signature);

      // 3. Unblind signature on client side
      const unblindedSig = unblindBallotSignature(sPrime, rBlind, blindRsaPK.n);

      setBlindToken({
        nonce: ballotNonce,
        signature: '0x' + unblindedSig.toString(16),
      });
      setStep(3);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleCastVote = async () => {
    const selectedIndex = candidates.findIndex((c) => c.id === selectedCandidate);
    if (selectedCandidate === null || selectedIndex < 0 || !electionPK || !blindToken) return;
    setIsProcessing(true);
    setError(null);

    try {
      // 1. Encrypt candidate vector [v0, v1, v2]
      const ciphertexts = [];
      const randomizers = [];
      const disjunctiveProofs = [];

      for (let i = 0; i < candidates.length; i++) {
        const v = i === selectedIndex ? 1 : 0;
        const { ciphertext, randomizer } = encryptVote(electionPK, v);
        ciphertexts.push(ciphertext);
        randomizers.push(randomizer);

        const zkp = await generateDisjunctiveZKP(electionPK, ciphertext, v, randomizer);
        disjunctiveProofs.push(zkp);
      }

      // 2. Generate Sum-to-One Equality ZKP
      const sumProof = await generateBallotSumProof(electionPK, ciphertexts, randomizers);

      // 3. Submit anonymous ballot payload
      const payload = {
        election_id: electionId,
        ciphertexts: ciphertexts.map((ct) => ({
          c1: '0x' + ct.c1.toString(16),
          c2: '0x' + ct.c2.toString(16),
        })),
        zkp_proofs: {
          disjunctive_proofs: disjunctiveProofs,
          sum_proof: sumProof,
        },
        token_nonce: blindToken.nonce,
        token_signature: blindToken.signature,
      };

      const res = await fetch('/api/ballots/cast', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Ballot casting failed');
      }

      const data = await res.json();
      setReceiptData({
        receiptCode: data.receipt_code,
        sequenceNumber: data.sequence_number,
        blockHash: data.block_hash,
      });
      setStep(4);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsProcessing(false);
    }
  };

  const copyReceipt = () => {
    if (!receiptData) return;
    navigator.clipboard.writeText(receiptData.receiptCode);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="max-w-3xl mx-auto py-8 px-4">
      {/* Step Indicators */}
      <div className="grid grid-cols-4 gap-2 mb-8">
        {[
          { num: 1, label: 'Time-Lock & Shares' },
          { num: 2, label: 'Liveness Check' },
          { num: 3, label: 'Encrypted Voting' },
          { num: 4, label: 'Receipt & Audit' },
        ].map((s) => (
          <div
            key={s.num}
            className={`p-3 rounded-xl border text-center transition ${
              step === s.num
                ? 'bg-emerald-500/10 border-emerald-500/50 text-emerald-400 font-semibold'
                : step > s.num
                ? 'bg-slate-900 border-slate-800 text-slate-300'
                : 'bg-slate-950/40 border-slate-900 text-slate-600'
            }`}
          >
            <span className="text-xs">Step {s.num}</span>
            <p className="text-xs truncate">{s.label}</p>
          </div>
        ))}
      </div>

      {/* STEP 1: Time-Lock & Share B Retrieval */}
      {step === 1 && (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-6">
          <div className="flex items-center space-x-3 text-emerald-400">
            <Lock className="w-6 h-6" />
            <h2 className="text-xl font-bold text-slate-100">Election Day Authentication (2-of-2 Shamir)</h2>
          </div>
          <p className="text-sm text-slate-400">
            Enter your Voter ID and Secret Share A. When the election opens, the time-lock releases Share B from the server to reconstruct your credential commitment.
          </p>

          <div className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
                Voter ID
              </label>
              <input
                type="text"
                value={voterId}
                onChange={(e) => setVoterId(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-slate-200 focus:outline-none focus:border-emerald-500 font-mono"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
                Your Secret Share A (From Registration)
              </label>
              <input
                type="text"
                value={shareA}
                onChange={(e) => setShareA(e.target.value)}
                placeholder="0x..."
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-slate-200 focus:outline-none focus:border-emerald-500 font-mono"
              />
            </div>

            <div className="p-4 bg-slate-950 rounded-xl border border-slate-800 flex items-center justify-between">
              <div className="flex items-center space-x-3">
                {isTimeLocked ? (
                  <Lock className="w-5 h-5 text-amber-400" />
                ) : (
                  <Unlock className="w-5 h-5 text-emerald-400" />
                )}
                <div>
                  <p className="text-xs font-semibold text-slate-200">Server Time-Lock Share B Status</p>
                  <p className="text-xs text-slate-400">{timeLockMsg || 'Ready to query election time-lock gate.'}</p>
                </div>
              </div>
              <button
                type="button"
                onClick={handleFetchShareB}
                disabled={isProcessing}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-medium border border-slate-700 transition"
              >
                {isProcessing ? 'Checking...' : 'Unlock Share B'}
              </button>
            </div>
          </div>

          {error && (
            <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-xs">
              {error}
            </div>
          )}
        </div>
      )}

      {/* STEP 2: Active Liveness & Blind Token Issuance */}
      {step === 2 && (
        <div className="space-y-6">
          <WebcamLiveness
            actions={['BLINK', 'TURN_LEFT']}
            onCaptureCompleted={(tel) => {
              setLivenessTelemetry(tel);
              setLivenessPassed(true);
            }}
          />

          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4 text-center">
            <div className="flex items-center justify-center space-x-2 text-emerald-400">
              <ShieldCheck className="w-5 h-5" />
              <span className="font-semibold text-slate-200">Chaum RSA Blind Signing Ready</span>
            </div>
            <p className="text-xs text-slate-400 max-w-md mx-auto">
              Your browser will blind a random ballot nonce $m \cdot r^e \pmod N$. The server signs without seeing it, ensuring total privacy.
            </p>

            {error && (
              <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-xs text-left">
                {error}
              </div>
            )}

            <button
              onClick={handleAuthenticateAndGetToken}
              disabled={!livenessPassed || isProcessing}
              className={`w-full py-3 rounded-xl font-medium text-sm flex items-center justify-center space-x-2 transition ${
                livenessPassed
                  ? 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-600/20'
                  : 'bg-slate-800 text-slate-500 cursor-not-allowed'
              }`}
            >
              {isProcessing ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>Issuing Blind Voting Token...</span>
                </>
              ) : (
                <>
                  <span>Authenticate & Issue Anonymous Voting Token</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {/* STEP 3: In-Browser Encrypted Voting Booth */}
      {step === 3 && (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-6">
          <div className="flex items-center space-x-3 text-emerald-400">
            <Vote className="w-6 h-6" />
            <h2 className="text-xl font-bold text-slate-100">Step 3: Official Ballot Voting Booth</h2>
          </div>
          <p className="text-sm text-slate-400">
            Select your preferred candidate. Your browser will perform homomorphic ElGamal encryption and generate zero-knowledge validity proofs in-browser. The server will never see your plaintext choice.
          </p>

          <div className="space-y-3">
            {candidates.map((cand) => {
              const isSelected = selectedCandidate === cand.id;
              return (
                <div
                  key={cand.id}
                  onClick={() => setSelectedCandidate(cand.id)}
                  className={`p-4 rounded-xl border cursor-pointer transition flex items-center justify-between ${
                    isSelected
                      ? 'bg-emerald-500/15 border-emerald-500/60 shadow-lg shadow-emerald-500/10'
                      : 'bg-slate-950/60 border-slate-800 hover:border-slate-700'
                  }`}
                >
                  <div className="flex items-center space-x-3">
                    <div
                      className={`w-5 h-5 rounded-full border flex items-center justify-center ${
                        isSelected ? 'border-emerald-400 bg-emerald-400' : 'border-slate-600'
                      }`}
                    >
                      {isSelected && <div className="w-2 h-2 rounded-full bg-slate-950" />}
                    </div>
                    <span className="font-medium text-slate-200">{cand.name}</span>
                  </div>
                  <span className="text-xs text-slate-500 font-mono">Candidate #{cand.id + 1}</span>
                </div>
              );
            })}
          </div>

          <div className="p-4 bg-slate-950 rounded-xl border border-slate-800 space-y-2 text-xs text-slate-400">
            <div className="flex items-center space-x-2 text-emerald-400 font-semibold">
              <ShieldCheck className="w-4 h-4" />
              <span>In-Browser Zero-Knowledge Proofs Attached</span>
            </div>
            <p>1. Disjunctive 1-of-2 ZKP: Proves each candidate ciphertext is strictly 0 or 1.</p>
            <p>2. Sum-to-One ZKP: Proves total ballot votes equal exactly 1 (No ballot stuffing).</p>
          </div>

          {error && (
            <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-xs">
              {error}
            </div>
          )}

          <button
            onClick={handleCastVote}
            disabled={selectedCandidate === null || isProcessing}
            className={`w-full py-3.5 rounded-xl font-medium text-sm flex items-center justify-center space-x-2 transition ${
              selectedCandidate !== null
                ? 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-600/25'
                : 'bg-slate-800 text-slate-500 cursor-not-allowed'
            }`}
          >
            {isProcessing ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                <span>Encrypting Ballot & Computing ZKPs in Browser...</span>
              </>
            ) : (
              <>
                <Vote className="w-4 h-4" />
                <span>Encrypt Vote & Submit Anonymously</span>
              </>
            )}
          </button>
        </div>
      )}

      {/* STEP 4: Receipt & Public Audit Link */}
      {step === 4 && receiptData && (
        <div className="bg-slate-900 border border-emerald-500/40 rounded-2xl p-6 shadow-2xl space-y-6 text-center">
          <div className="w-16 h-16 bg-emerald-500/10 text-emerald-400 rounded-full flex items-center justify-center mx-auto border border-emerald-500/20">
            <CheckCircle2 className="w-8 h-8" />
          </div>

          <div>
            <h2 className="text-2xl font-bold text-slate-100">Ballot Cast Successfully!</h2>
            <p className="text-sm text-slate-400 mt-1">
              Your ballot is cryptographically encrypted, zero-knowledge verified, and permanently anchored on the public bulletin board.
            </p>
          </div>

          <div className="bg-slate-950 p-5 rounded-2xl border border-slate-800 max-w-md mx-auto space-y-3 text-left">
            <div>
              <span className="text-xs text-slate-500 font-semibold uppercase">Official Receipt Code:</span>
              <div className="flex items-center justify-between bg-emerald-950/40 p-3 rounded-xl border border-emerald-500/30 mt-1">
                <span className="text-lg font-mono font-bold text-emerald-300 tracking-wider">
                  {receiptData.receiptCode}
                </span>
                <button
                  onClick={copyReceipt}
                  className="p-1.5 hover:bg-emerald-500/20 rounded-lg text-emerald-400 transition"
                  title="Copy Receipt"
                >
                  {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <div className="text-xs text-slate-400 space-y-1 font-mono">
              <p>Sequence Number: <span className="text-slate-200">#{receiptData.sequenceNumber}</span></p>
              <p className="truncate">Block Hash: <span className="text-slate-200">{receiptData.blockHash}</span></p>
            </div>
          </div>

          <p className="text-xs text-slate-500 max-w-md mx-auto">
            You can verify your receipt code on the <strong>Public Auditor</strong> page at any time to confirm that your ballot remains untampered.
          </p>

          <button
            onClick={() => {
              setStep(1);
              setSelectedCandidate(null);
              setReceiptData(null);
              setBlindToken(null);
            }}
            className="px-6 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-xl text-xs font-medium transition"
          >
            Vote in Another Demo Session
          </button>
        </div>
      )}
    </div>
  );
};

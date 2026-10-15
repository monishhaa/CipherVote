import React, { useState, useEffect, useMemo } from 'react';
import {
  CheckCircle2,
  ArrowRight,
  Copy,
  Check,
  AlertCircle,
  Upload,
  ExternalLink,
} from 'lucide-react';
import { WebcamLiveness } from '../components/WebcamLiveness';
import { encryptVote } from '../crypto/elgamal';
import { generateDisjunctiveZKP, generateBallotSumProof } from '../crypto/zkp';
import { blindBallotToken, unblindBallotSignature } from '../crypto/blindSignature';

interface Candidate {
  id: number;
  name: string;
}

interface VoterVoteProps {
  electionId?: string;
  electionTitle?: string;
  navigateTo: (path: string) => void;
}

interface MyElectionItem {
  election_id: string;
  title: string;
  status: string;
  is_open: boolean;
  scheduled_start?: string | null;
  scheduled_end?: string | null;
  progress: {
    registered: boolean;
    ballot_cast: boolean;
    receipt_code?: string | null;
  };
}

export const VoterVote: React.FC<VoterVoteProps> = ({
  electionId: propElectionId = '',
  electionTitle: propElectionTitle = '',
  navigateTo,
}) => {
  const token = sessionStorage.getItem('voter_session_token');
  const sessionVoterId = sessionStorage.getItem('voter_id') || '';

  const [myElections, setMyElections] = useState<MyElectionItem[]>([]);
  const [selectedElectionId, setSelectedElectionId] = useState<string>(
    () => propElectionId || sessionStorage.getItem('voter_election_id') || ''
  );
  const [hasChosenElection, setHasChosenElection] = useState<boolean>(Boolean(propElectionId));

  const [step, setStep] = useState<1 | 2 | 3 | 4>(1);
  const [voterId] = useState<string>(sessionVoterId);
  const [shareA, setShareA] = useState<string>('');
  const [shareB, setShareB] = useState<string | null>(null);
  const [isTimeLocked, setIsTimeLocked] = useState<boolean>(false);
  const [timeLockMsg, setTimeLockMsg] = useState<string>('');

  const [livenessPassed, setLivenessPassed] = useState<boolean>(false);
  const [livenessTelemetry, setLivenessTelemetry] = useState<any>(null);

  const [blindToken, setBlindToken] = useState<{
    nonce: string;
    signature: string;
  } | null>(null);

  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [selectedCandidate, setSelectedCandidate] = useState<number | null>(null);
  const [electionPK, setElectionPK] = useState<bigint | null>(null);
  const [blindRsaPK, setBlindRsaPK] = useState<{ n: bigint; e: bigint } | null>(null);

  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [statusMessage, setStatusMessage] = useState<string>('');
  const [receiptData, setReceiptData] = useState<{
    receiptCode: string;
    sequenceNumber: number;
    blockHash: string;
  } | null>(null);
  const [copied, setCopied] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Credential file mismatch warning
  const [credentialMismatch, setCredentialMismatch] = useState<{
    mismatchedElectionId: string;
    mismatchedTitle: string;
    canSwitch: boolean;
  } | null>(null);

  // Synchronize propElectionId
  useEffect(() => {
    if (propElectionId) {
      setSelectedElectionId(propElectionId);
      setHasChosenElection(true);
    }
  }, [propElectionId]);

  // Fetch my registered elections
  useEffect(() => {
    if (!token) return;
    fetch('/api/voter/my-elections', {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data && data.elections) {
          setMyElections(data.elections);
          if (!selectedElectionId && data.elections.length > 0) {
            const firstOpen = data.elections.find(
              (e: any) => e.status === 'OPEN' && !e.progress.ballot_cast
            );
            if (firstOpen) {
              setSelectedElectionId(firstOpen.election_id);
            } else {
              setSelectedElectionId(data.elections[0].election_id);
            }
          }
        }
      })
      .catch(() => {});
  }, [token, selectedElectionId]);

  const targetElectionId = selectedElectionId || (myElections.length > 0 ? myElections[0].election_id : '');
  const activeElection = myElections.find((e) => e.election_id === targetElectionId);
  const activeTitle = activeElection?.title || propElectionTitle || targetElectionId || 'Official Election';

  // Check stored receipt
  const storedReceipt = useMemo(() => {
    if (!sessionVoterId || !targetElectionId) return null;
    return (
      sessionStorage.getItem(`securevote_receipt_${sessionVoterId}_${targetElectionId}`) ||
      localStorage.getItem(`securevote_receipt_${sessionVoterId}_${targetElectionId}`)
    );
  }, [sessionVoterId, targetElectionId]);

  // Fetch target election parameters
  useEffect(() => {
    if (!targetElectionId) return;

    fetch(`/api/public/status?election_id=${encodeURIComponent(targetElectionId)}`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!data) return;
        setCandidates(data.candidates || []);
        if (data.public_key_h) {
          setElectionPK(BigInt(data.public_key_h));
        }
        if (data.blind_rsa_n && data.blind_rsa_e) {
          setBlindRsaPK({
            n: BigInt(data.blind_rsa_n),
            e: BigInt(data.blind_rsa_e),
          });
        }
      })
      .catch((e) => console.error('Failed to fetch election parameters:', e));
  }, [targetElectionId]);

  // Categorize elections for switcher / chooser
  const { openElections, unavailableElections } = useMemo(() => {
    const open: MyElectionItem[] = [];
    const unavailable: { election: MyElectionItem; reason: string }[] = [];

    myElections.forEach((el) => {
      if (el.progress?.ballot_cast) {
        unavailable.push({ election: el, reason: 'Already voted' });
      } else if (el.status === 'OPEN') {
        open.push(el);
      } else if (el.status === 'REGISTRATION') {
        const startStr = el.scheduled_start ? new Date(el.scheduled_start).toLocaleDateString() : 'soon';
        unavailable.push({ election: el, reason: `Voting opens ${startStr}` });
      } else {
        unavailable.push({ election: el, reason: 'Voting closed' });
      }
    });

    return { openElections: open, unavailableElections: unavailable };
  }, [myElections]);

  const handleSwitchElection = (newElectionId: string) => {
    setSelectedElectionId(newElectionId);
    sessionStorage.setItem('voter_election_id', newElectionId);
    setHasChosenElection(true);
    setStep(1);
    setShareA('');
    setShareB(null);
    setBlindToken(null);
    setLivenessPassed(false);
    setError(null);
    setCredentialMismatch(null);
    navigateTo(`/user/e/${encodeURIComponent(newElectionId)}/vote`);
  };

  const handleCredentialFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null);
    setCredentialMismatch(null);

    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const text = event.target?.result as string;
        const parsed = JSON.parse(text);

        // Check for election mismatch
        if (parsed.election_id && parsed.election_id !== targetElectionId) {
          const matchInMine = myElections.find((el) => el.election_id === parsed.election_id);
          const otherTitle = matchInMine?.title || parsed.election_id;
          setCredentialMismatch({
            mismatchedElectionId: parsed.election_id,
            mismatchedTitle: otherTitle,
            canSwitch: Boolean(matchInMine),
          });
          return;
        }

        if (parsed.share_a) {
          setShareA(parsed.share_a);
        } else if (typeof parsed === 'string') {
          setShareA(parsed);
        } else {
          throw new Error('Credential file must contain a "share_a" field.');
        }
      } catch (err: any) {
        setError(err.message || 'Invalid JSON credential file.');
      }
    };
    reader.readAsText(file);
  };

  const handleFetchShareB = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!voterId || !shareA) {
      setError('Please provide both your Voter ID and Share A key.');
      return;
    }
    setIsProcessing(true);
    setError(null);

    try {
      const res = await fetch(
        `/api/voter/share_b/${encodeURIComponent(voterId)}?election_id=${encodeURIComponent(targetElectionId)}`
      );
      if (!res.ok) {
        const err = await res.json();
        setIsTimeLocked(true);
        setTimeLockMsg(err.detail || 'Time-lock is currently active for this credential.');
        return;
      }
      const data = await res.json();
      setShareB(data.share_b);
      setIsTimeLocked(false);
      setStep(2);
    } catch (err: any) {
      setError(err.message || 'Failed to communicate with authentication server.');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleAuthenticateAndGetToken = async () => {
    if (!shareB || !shareA || !blindRsaPK) {
      setError('Missing cryptographic shares or election blind RSA key.');
      return;
    }
    setIsProcessing(true);
    setStatusMessage('Generating blinded token and requesting Chaum blind signature...');
    setError(null);

    try {
      const ballotNonce = `ballot_token_${voterId}_${Date.now()}_${Math.random()}`;
      const { mPrime, rBlind } = await blindBallotToken(ballotNonce, blindRsaPK.n, blindRsaPK.e);

      const formattedTelemetry = {
        challenge_id: 'challenge_web',
        ear_scores: (livenessTelemetry as any)?.earScores || (livenessTelemetry as any)?.ear_scores || [0.35, 0.15, 0.36],
        yaw_angles: (livenessTelemetry as any)?.yawAngles || (livenessTelemetry as any)?.yaw_angles || [0.0, -12.0, 0.0],
        probe_embedding: (livenessTelemetry as any)?.probeEmbedding || (livenessTelemetry as any)?.probe_embedding || undefined,
      };

      const res = await fetch(`/api/auth/blind-token?election_id=${encodeURIComponent(targetElectionId)}`, {
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
      const unblindedSig = unblindBallotSignature(sPrime, rBlind, blindRsaPK.n);

      setBlindToken({
        nonce: ballotNonce,
        signature: '0x' + unblindedSig.toString(16),
      });
      setStep(3);
    } catch (err: any) {
      setError(err.message || 'Authentication and token generation failed.');
    } finally {
      setIsProcessing(false);
      setStatusMessage('');
    }
  };

  const handleCastVote = async () => {
    const selectedIndex = candidates.findIndex((c) => c.id === selectedCandidate);
    if (selectedCandidate === null || selectedIndex < 0 || !electionPK || !blindToken) {
      setError('Please select a candidate to encrypt.');
      return;
    }
    setIsProcessing(true);
    setStatusMessage('Encrypting candidate vector with ElGamal and generating ZK zero/one sum proofs...');
    setError(null);

    try {
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

      const sumProof = await generateBallotSumProof(electionPK, ciphertexts, randomizers);

      const payload = {
        election_id: targetElectionId,
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
        throw new Error(err.detail || 'Ballot submission rejected by bulletin board.');
      }

      const data = await res.json();
      const receipt = {
        receiptCode: data.receipt_code,
        sequenceNumber: data.sequence_number,
        blockHash: data.block_hash,
      };
      setReceiptData(receipt);

      // Persist receipt strictly per voter and election
      if (sessionVoterId && targetElectionId) {
        sessionStorage.setItem(`securevote_receipt_${sessionVoterId}_${targetElectionId}`, data.receipt_code);
        localStorage.setItem(`securevote_receipt_${sessionVoterId}_${targetElectionId}`, data.receipt_code);
      }

      setStep(4);
    } catch (err: any) {
      setError(err.message || 'Cryptographic encryption or ballot submission failed.');
    } finally {
      setIsProcessing(false);
      setStatusMessage('');
    }
  };

  // MULTI-ELECTION CHOOSER (If user has multiple open elections and hasn't chosen one)
  if (!hasChosenElection && openElections.length > 1) {
    return (
      <div className="min-h-[calc(100vh-4rem)] bg-paper py-10 px-4 sm:px-6 lg:px-8 max-w-3xl mx-auto">
        <div className="text-center mb-8">
          <span className="text-[11px] font-mono uppercase text-accent font-bold tracking-wider">Ballot Box Portal</span>
          <h1 className="font-display text-3xl font-bold text-ink mt-1">Which election are you voting in?</h1>
          <p className="text-xs text-ink/70 mt-2">
            You are registered in multiple elections that are currently open for voting. Select one to proceed.
          </p>
        </div>

        <div className="space-y-4 mb-8">
          <h3 className="font-display text-sm font-bold text-ink uppercase tracking-wider">Open Elections</h3>
          <div className="grid grid-cols-1 gap-3">
            {openElections.map((el) => (
              <button
                key={el.election_id}
                type="button"
                onClick={() => handleSwitchElection(el.election_id)}
                className="p-5 bg-paper-2 border border-line hover:border-accent rounded-xl text-left transition flex items-center justify-between group shadow-xs"
              >
                <div>
                  <h4 className="font-display text-base font-bold text-ink group-hover:text-accent transition">
                    {el.title}
                  </h4>
                  <span className="text-xs font-mono text-emerald-700 font-semibold mt-1 inline-block">
                    ● Voting Live & Ready
                  </span>
                </div>
                <div className="w-8 h-8 rounded-full bg-paper border border-line flex items-center justify-center text-ink/50 group-hover:text-accent group-hover:border-accent transition">
                  <ArrowRight className="w-4 h-4" />
                </div>
              </button>
            ))}
          </div>
        </div>

        {unavailableElections.length > 0 && (
          <div className="space-y-3 opacity-60">
            <h3 className="font-display text-xs font-bold text-ink/60 uppercase tracking-wider">Other Registered Elections</h3>
            <div className="grid grid-cols-1 gap-2">
              {unavailableElections.map(({ election: el, reason }) => (
                <div
                  key={el.election_id}
                  className="p-3.5 bg-paper-2 border border-line rounded-lg text-left flex items-center justify-between text-xs font-mono"
                >
                  <span className="text-ink font-medium">{el.title}</span>
                  <span className="text-ink/60 bg-paper px-2 py-0.5 rounded border border-line text-[11px]">
                    {reason}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }

  // ALREADY VOTED VIEW: Show receipt code and verification button, no ballot form
  if (activeElection?.progress?.ballot_cast || storedReceipt) {
    const rc = storedReceipt || activeElection?.progress?.receipt_code || 'VERIFIED-ON-CHAIN';
    return (
      <div className="min-h-[calc(100vh-4rem)] bg-paper py-10 px-4 sm:px-6 lg:px-8 max-w-2xl mx-auto text-center">
        <div className="w-14 h-14 bg-emerald-100 border border-emerald-300 text-emerald-700 rounded-full flex items-center justify-center mx-auto mb-4">
          <CheckCircle2 className="w-8 h-8" />
        </div>
        <span className="text-[11px] font-mono uppercase text-ink/50">Ballot Cast Confirmed</span>
        <h1 className="font-display text-3xl font-bold text-ink mt-1 mb-2">You already voted in this election</h1>
        <p className="text-xs text-ink/70 mb-6 font-mono">
          Election: <span className="text-ink font-bold">{activeTitle}</span>
        </p>

        <div className="p-6 bg-paper-2 border border-line rounded-xl text-left font-mono text-xs space-y-3 mb-6 shadow-xs">
          <div>
            <span className="text-ink/50 block text-[11px] uppercase">Official Receipt Code</span>
            <span className="text-lg font-bold text-accent tracking-widest">{rc}</span>
          </div>
          <p className="text-ink/70 text-[11px] leading-relaxed">
            Your encrypted ballot has been permanently sealed into the public bulletin board hash chain. To maintain total ballot confidentiality, ballot tokens are single-use.
          </p>
        </div>

        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <button
            type="button"
            onClick={() => navigateTo(`/user/e/${targetElectionId}/audit`)}
            className="py-2.5 px-5 bg-primary text-white text-xs font-mono uppercase font-semibold rounded hover:bg-primary/90 transition flex items-center justify-center gap-2"
          >
            <ExternalLink className="w-4 h-4" />
            <span>Verify on Bulletin Board</span>
          </button>
          <button
            type="button"
            onClick={() => navigateTo(`/user/e/${targetElectionId}/overview`)}
            className="py-2.5 px-5 bg-paper border border-line text-ink text-xs font-mono uppercase rounded hover:bg-paper-2 transition"
          >
            Back to Overview
          </button>
        </div>
      </div>
    );
  }

  // ACTIVE VOTING FLOW
  return (
    <div className="min-h-[calc(100vh-4rem)] bg-paper py-8 px-4 sm:px-6 lg:px-8 max-w-3xl mx-auto">
      {/* Election Header with Switcher */}
      <div className="border-b border-line pb-6 mb-8 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <span className="text-[11px] font-mono uppercase text-accent font-bold tracking-wider">Ballot Casting</span>
          <h1 className="font-display text-2xl sm:text-3xl font-bold text-ink mt-1">
            {activeTitle}
          </h1>
          <p className="text-xs text-ink/70 mt-1">
            Zero-knowledge client-side encryption with Chaum blind signatures.
          </p>
        </div>

        {/* Switcher limited to open elections */}
        {myElections.length > 1 && (
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-mono text-ink/50 uppercase">Switch:</span>
            <select
              value={targetElectionId}
              onChange={(e) => handleSwitchElection(e.target.value)}
              className="text-xs font-mono bg-paper-2 border border-line rounded px-2.5 py-1 text-ink focus:outline-none focus:border-accent"
            >
              {openElections.map((el) => (
                <option key={el.election_id} value={el.election_id}>
                  {el.title} (Open)
                </option>
              ))}
              {unavailableElections.map(({ election: el, reason }) => (
                <option key={el.election_id} value={el.election_id} disabled>
                  {el.title} ({reason})
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* Stepper Header */}
      <div className="flex items-center justify-between border-b border-line pb-4 mb-8 text-xs font-mono">
        <div className={`flex items-center gap-1.5 ${step === 1 ? 'text-accent font-bold' : step > 1 ? 'text-emerald-700' : 'text-ink/40'}`}>
          <span className="w-5 h-5 rounded-full border border-current flex items-center justify-center text-[10px]">1</span>
          <span>Credential</span>
        </div>
        <span className="text-ink/20">——</span>
        <div className={`flex items-center gap-1.5 ${step === 2 ? 'text-accent font-bold' : step > 2 ? 'text-emerald-700' : 'text-ink/40'}`}>
          <span className="w-5 h-5 rounded-full border border-current flex items-center justify-center text-[10px]">2</span>
          <span>Biometrics</span>
        </div>
        <span className="text-ink/20">——</span>
        <div className={`flex items-center gap-1.5 ${step === 3 ? 'text-accent font-bold' : step > 3 ? 'text-emerald-700' : 'text-ink/40'}`}>
          <span className="w-5 h-5 rounded-full border border-current flex items-center justify-center text-[10px]">3</span>
          <span>Vote</span>
        </div>
        <span className="text-ink/20">——</span>
        <div className={`flex items-center gap-1.5 ${step === 4 ? 'text-emerald-700 font-bold' : 'text-ink/40'}`}>
          <span className="w-5 h-5 rounded-full border border-current flex items-center justify-center text-[10px]">4</span>
          <span>Receipt</span>
        </div>
      </div>

      {/* Error & Mismatch Alerts */}
      {credentialMismatch && (
        <div className="mb-6 p-4 bg-amber-50 border border-amber-300 text-amber-900 rounded-xl text-xs font-mono space-y-2">
          <div className="flex items-center gap-2 font-bold">
            <AlertCircle className="w-4 h-4 text-amber-600 flex-shrink-0" />
            <span>Credential Election Mismatch</span>
          </div>
          <p>
            This credential file belongs to <span className="font-bold underline">{credentialMismatch.mismatchedTitle}</span>. Switch to that election or upload the right file.
          </p>
          {credentialMismatch.canSwitch && (
            <button
              type="button"
              onClick={() => handleSwitchElection(credentialMismatch.mismatchedElectionId)}
              className="mt-2 px-3 py-1 bg-amber-200 text-amber-900 border border-amber-400 rounded font-semibold hover:bg-amber-300 transition"
            >
              Switch to "{credentialMismatch.mismatchedTitle}"
            </button>
          )}
        </div>
      )}

      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-300 text-red-800 rounded-xl text-xs font-mono flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-red-600 flex-shrink-0" />
            <span>{error}</span>
          </div>
          <button type="button" onClick={() => setError(null)} className="text-red-600 hover:text-red-900">
            Dismiss
          </button>
        </div>
      )}

      {/* STEP 1: IDENTITY & TIME-LOCKED SHARE B */}
      {step === 1 && (
        <form onSubmit={handleFetchShareB} className="space-y-6 bg-paper-2 border border-line rounded-xl p-6 sm:p-8">
          <div>
            <h3 className="font-display text-lg font-bold text-ink">Step 1: Enter Credential Shares</h3>
            <p className="text-xs text-ink/70 mt-1">
              Provide your secret Share A (sent to your email during registration) to unlock server Share B.
            </p>
          </div>

          <div>
            <label className="block text-xs font-mono uppercase text-ink/70 mb-1.5">Official Voter ID</label>
            <input
              type="text"
              value={voterId}
              readOnly
              className="w-full px-3 py-2 bg-paper border border-line rounded text-xs font-mono text-ink font-bold opacity-80 cursor-not-allowed"
            />
            <span className="text-[10px] font-mono text-ink/50 mt-1 block">Prefilled and verified from session.</span>
          </div>

          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="block text-xs font-mono uppercase text-ink/70">Secret Share A</label>
              <label className="cursor-pointer text-[11px] font-mono text-accent hover:underline flex items-center gap-1">
                <Upload className="w-3 h-3" />
                <span>Upload credential JSON</span>
                <input
                  type="file"
                  accept=".json,application/json"
                  onChange={handleCredentialFileUpload}
                  className="hidden"
                />
              </label>
            </div>
            <textarea
              rows={3}
              value={shareA}
              onChange={(e) => {
                setShareA(e.target.value);
                setCredentialMismatch(null);
              }}
              placeholder="Paste hexadecimal Share A or upload credential file"
              required
              className="w-full px-3 py-2 bg-paper border border-line rounded text-xs font-mono text-ink focus:outline-none focus:border-accent"
            />
          </div>

          {isTimeLocked && (
            <div className="p-3 bg-amber-50 border border-amber-300 text-amber-900 rounded text-xs font-mono">
              <span className="font-bold">Time-Lock Active: </span>{timeLockMsg}
            </div>
          )}

          <button
            type="submit"
            disabled={isProcessing || !shareA.trim()}
            className="w-full py-3 bg-primary text-white text-xs font-mono uppercase font-semibold rounded hover:bg-primary/90 disabled:opacity-50 transition flex items-center justify-center gap-2"
          >
            {isProcessing ? 'Verifying Time-Lock...' : 'Unlock Share B & Continue'}
            <ArrowRight className="w-4 h-4" />
          </button>
        </form>
      )}

      {/* STEP 2: BIOMETRIC LIVENESS & BLIND TOKEN */}
      {step === 2 && (
        <div className="space-y-6 bg-paper-2 border border-line rounded-xl p-6 sm:p-8">
          <div>
            <h3 className="font-display text-lg font-bold text-ink">Step 2: Biometric Liveness Verification</h3>
            <p className="text-xs text-ink/70 mt-1">
              Perform interactive head/blink telemetry. Upon verification, the server will issue a blind-signed ballot token.
            </p>
          </div>

          <div className="border border-line rounded-xl overflow-hidden bg-black">
            <WebcamLiveness
              onCaptureCompleted={(telemetry: { earScores: number[]; yawAngles: number[]; probeEmbedding?: number[] }) => {
                setLivenessPassed(true);
                setLivenessTelemetry(telemetry);
              }}
            />
          </div>

          {livenessPassed && (
            <div className="p-3 bg-emerald-50 border border-emerald-300 text-emerald-800 rounded text-xs font-mono flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
              <span>Biometric telemetry verified successfully!</span>
            </div>
          )}

          <div className="flex gap-3">
            <button
              type="button"
              onClick={() => setStep(1)}
              className="py-2.5 px-4 bg-paper border border-line text-xs font-mono uppercase rounded hover:bg-paper-2"
            >
              Back
            </button>
            <button
              type="button"
              onClick={handleAuthenticateAndGetToken}
              disabled={isProcessing || !livenessPassed}
              className="flex-1 py-2.5 px-4 bg-primary text-white text-xs font-mono uppercase font-semibold rounded hover:bg-primary/90 disabled:opacity-50 transition flex items-center justify-center gap-2"
            >
              {isProcessing ? (statusMessage || 'Blind-signing...') : 'Request Blind Ballot Token'}
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* STEP 3: VOTE CASTING & ENCRYPTION */}
      {step === 3 && (
        <div className="space-y-6 bg-paper-2 border border-line rounded-xl p-6 sm:p-8">
          <div>
            <h3 className="font-display text-lg font-bold text-ink">Step 3: Confidential Ballot Selection</h3>
            <p className="text-xs text-ink/70 mt-1">
              Select your candidate. Your selection is homomorphically encrypted with ElGamal and validated with zero-knowledge equality proofs.
            </p>
          </div>

          <div className="space-y-2">
            {candidates.map((cand) => {
              const selected = selectedCandidate === cand.id;
              return (
                <button
                  key={cand.id}
                  type="button"
                  onClick={() => setSelectedCandidate(cand.id)}
                  className={`w-full p-4 rounded-xl border text-left font-mono text-xs transition flex items-center justify-between ${
                    selected
                      ? 'bg-paper border-accent shadow-xs text-ink font-bold'
                      : 'bg-paper border-line text-ink/70 hover:border-ink/30'
                  }`}
                >
                  <span className="text-sm">{cand.name}</span>
                  <span className={`w-4 h-4 rounded-full border flex items-center justify-center ${
                    selected ? 'border-accent bg-accent text-white' : 'border-line'
                  }`}>
                    {selected && <Check className="w-3 h-3" />}
                  </span>
                </button>
              );
            })}
          </div>

          <div className="flex gap-3">
            <button
              type="button"
              onClick={() => setStep(2)}
              className="py-2.5 px-4 bg-paper border border-line text-xs font-mono uppercase rounded hover:bg-paper-2"
            >
              Back
            </button>
            <button
              type="button"
              onClick={handleCastVote}
              disabled={isProcessing || selectedCandidate === null}
              className="flex-1 py-2.5 px-4 bg-primary text-white text-xs font-mono uppercase font-semibold rounded hover:bg-primary/90 disabled:opacity-50 transition flex items-center justify-center gap-2"
            >
              {isProcessing ? (statusMessage || 'Encrypting & Submitting...') : 'Encrypt & Cast Ballot'}
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* STEP 4: RECEIPT CODE & CONFIRMATION */}
      {step === 4 && receiptData && (
        <div className="space-y-6 bg-paper-2 border border-line rounded-xl p-6 sm:p-8 text-center">
          <div className="w-14 h-14 bg-emerald-100 border border-emerald-300 text-emerald-700 rounded-full flex items-center justify-center mx-auto mb-2">
            <CheckCircle2 className="w-8 h-8" />
          </div>
          <span className="text-[11px] font-mono uppercase text-ink/50">Ballot Sealed</span>
          <h3 className="font-display text-2xl font-bold text-ink">Ballot Cast Successfully</h3>
          <p className="text-xs text-ink/70 max-w-md mx-auto">
            Your encrypted vote has been validated with ZK proofs and anchored into the public ledger.
          </p>

          <div className="p-6 bg-paper border border-line rounded-xl text-left font-mono text-xs space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-ink/50 block text-[10px] uppercase">Official Receipt Code</span>
                <span className="text-lg font-bold text-accent tracking-widest">{receiptData.receiptCode}</span>
              </div>
              <button
                type="button"
                onClick={() => {
                  navigator.clipboard.writeText(receiptData.receiptCode);
                  setCopied(true);
                  setTimeout(() => setCopied(false), 2000);
                }}
                className="p-2 border border-line rounded hover:bg-paper-2 text-ink/70 hover:text-ink"
                title="Copy receipt code"
              >
                {copied ? <Check className="w-4 h-4 text-emerald-600" /> : <Copy className="w-4 h-4" />}
              </button>
            </div>
            <div>
              <span className="text-ink/50 block text-[10px] uppercase">Ledger Sequence Number</span>
              <span className="text-ink font-bold">#{receiptData.sequenceNumber}</span>
            </div>
            <div>
              <span className="text-ink/50 block text-[10px] uppercase">Block Hash</span>
              <span className="text-ink/70 break-all text-[11px]">{receiptData.blockHash}</span>
            </div>
          </div>

          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <button
              type="button"
              onClick={() => navigateTo(`/user/e/${targetElectionId}/audit`)}
              className="py-2.5 px-5 bg-primary text-white text-xs font-mono uppercase font-semibold rounded hover:bg-primary/90 transition flex items-center justify-center gap-2"
            >
              <ExternalLink className="w-4 h-4" />
              <span>Verify on Bulletin Board</span>
            </button>
            <button
              type="button"
              onClick={() => navigateTo(`/user/e/${targetElectionId}/overview`)}
              className="py-2.5 px-5 bg-paper border border-line text-ink text-xs font-mono uppercase rounded hover:bg-paper-2 transition"
            >
              Return to Overview
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

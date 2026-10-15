/**
 * In-Browser Non-Interactive Zero-Knowledge Proofs (NIZK) with Fiat-Shamir.
 */

import { G, P, Q, getRandomScalar, hashToScalar, modInv, modPow } from "./constants";
import { BigIntCiphertext } from "./elgamal";

export interface DisjunctiveZKPJSON {
  a0: string;
  b0: string;
  a1: string;
  b1: string;
  c0: string;
  c1: string;
  z0: string;
  z1: string;
}

export interface EqualityZKPJSON {
  a: string;
  b: string;
  c: string;
  z: string;
}

/**
 * Generate 1-of-2 Disjunctive Chaum-Pedersen ZKP in browser.
 */
export async function generateDisjunctiveZKP(
  publicKeyH: bigint,
  ct: BigIntCiphertext,
  vote: number, // 0 or 1
  r: bigint
): Promise<DisjunctiveZKPJSON> {
  const gInv = modInv(G, P);
  const c2DivG = (ct.c2 * gInv) % P;

  if (vote === 0) {
    // Real branch 0, simulate branch 1
    const w = getRandomScalar(Q);
    const c1Sim = getRandomScalar(Q);
    const z1Sim = getRandomScalar(Q);

    const c1Inv = modInv(ct.c1, P);
    const c2DivGInv = modInv(c2DivG, P);

    const a1 = (modPow(G, z1Sim, P) * modPow(c1Inv, c1Sim, P)) % P;
    const b1 = (modPow(publicKeyH, z1Sim, P) * modPow(c2DivGInv, c1Sim, P)) % P;

    const a0 = modPow(G, w, P);
    const b0 = modPow(publicKeyH, w, P);

    const c = await hashToScalar(G, publicKeyH, ct.c1, ct.c2, a0, b0, a1, b1);
    const c0 = (c - c1Sim % Q + Q) % Q;
    const z0 = (w + (c0 * r) % Q) % Q;

    return {
      a0: "0x" + a0.toString(16),
      b0: "0x" + b0.toString(16),
      a1: "0x" + a1.toString(16),
      b1: "0x" + b1.toString(16),
      c0: "0x" + c0.toString(16),
      c1: "0x" + c1Sim.toString(16),
      z0: "0x" + z0.toString(16),
      z1: "0x" + z1Sim.toString(16),
    };
  } else {
    // Real branch 1, simulate branch 0
    const w = getRandomScalar(Q);
    const c0Sim = getRandomScalar(Q);
    const z0Sim = getRandomScalar(Q);

    const c1Inv = modInv(ct.c1, P);
    const c2Inv = modInv(ct.c2, P);

    const a0 = (modPow(G, z0Sim, P) * modPow(c1Inv, c0Sim, P)) % P;
    const b0 = (modPow(publicKeyH, z0Sim, P) * modPow(c2Inv, c0Sim, P)) % P;

    const a1 = modPow(G, w, P);
    const b1 = modPow(publicKeyH, w, P);

    const c = await hashToScalar(G, publicKeyH, ct.c1, ct.c2, a0, b0, a1, b1);
    const c1 = (c - c0Sim % Q + Q) % Q;
    const z1 = (w + (c1 * r) % Q) % Q;

    return {
      a0: "0x" + a0.toString(16),
      b0: "0x" + b0.toString(16),
      a1: "0x" + a1.toString(16),
      b1: "0x" + b1.toString(16),
      c0: "0x" + c0Sim.toString(16),
      c1: "0x" + c1.toString(16),
      z0: "0x" + z0Sim.toString(16),
      z1: "0x" + z1.toString(16),
    };
  }
}

/**
 * Generate Sum-to-One Equality ZKP in browser.
 */
export async function generateBallotSumProof(
  publicKeyH: bigint,
  ciphertexts: BigIntCiphertext[],
  randomizers: bigint[]
): Promise<EqualityZKPJSON> {
  let c1Agg = 1n;
  let c2Agg = 1n;
  let rSum = 0n;

  for (let i = 0; i < ciphertexts.length; i++) {
    c1Agg = (c1Agg * ciphertexts[i].c1) % P;
    c2Agg = (c2Agg * ciphertexts[i].c2) % P;
    rSum = (rSum + randomizers[i]) % Q;
  }

  const w = getRandomScalar(Q);
  const a = modPow(G, w, P);
  const b = modPow(publicKeyH, w, P);

  const c = await hashToScalar(G, publicKeyH, c1Agg, c2Agg, a, b);
  const z = (w + (c * rSum) % Q) % Q;

  return {
    a: "0x" + a.toString(16),
    b: "0x" + b.toString(16),
    c: "0x" + c.toString(16),
    z: "0x" + z.toString(16),
  };
}

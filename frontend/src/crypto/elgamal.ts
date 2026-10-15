/**
 * In-Browser Exponential ElGamal Encryption using BigInt.
 */

import { G, P, Q, getRandomScalar, modPow } from "./constants";

export interface BigIntCiphertext {
  c1: bigint;
  c2: bigint;
}

export interface HexCiphertext {
  c1: string;
  c2: string;
}

export function encryptVote(
  publicKeyH: bigint,
  voteValue: number, // 0 or 1
  randomizer?: bigint
): { ciphertext: BigIntCiphertext; randomizer: bigint; hex: HexCiphertext } {
  const r = randomizer ?? getRandomScalar(Q);
  const c1 = modPow(G, r, P);
  const hr = modPow(publicKeyH, r, P);
  const gm = modPow(G, BigInt(voteValue), P);
  const c2 = (hr * gm) % P;

  return {
    ciphertext: { c1, c2 },
    randomizer: r,
    hex: {
      c1: "0x" + c1.toString(16),
      c2: "0x" + c2.toString(16),
    },
  };
}

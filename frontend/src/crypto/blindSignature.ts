/**
 * In-Browser Chaum RSA Blind Signature Helper (Blinding & Unblinding).
 */

import { getRandomScalar, modInv, modPow } from "./constants";

export async function hashMessageToInt(message: string, n: bigint): Promise<bigint> {
  const encoder = new TextEncoder();
  let counter = 0;
  while (true) {
    const data = encoder.encode(`${message}:${counter}`);
    const digest = await window.crypto.subtle.digest("SHA-256", data);
    const hex = Array.from(new Uint8Array(digest))
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");
    const val = BigInt("0x" + hex);
    if (val > 1n && val < n) {
      return val;
    }
    counter++;
  }
}

export async function blindBallotToken(
  ballotNonce: string,
  rsaN: bigint,
  rsaE: bigint = 65537n
): Promise<{ mPrime: bigint; rBlind: bigint; mInt: bigint }> {
  const mInt = await hashMessageToInt(ballotNonce, rsaN);
  const rBlind = getRandomScalar(rsaN);
  const rE = modPow(rBlind, rsaE, rsaN);
  const mPrime = (mInt * rE) % rsaN;
  return { mPrime, rBlind, mInt };
}

export function unblindBallotSignature(
  sPrime: bigint,
  rBlind: bigint,
  rsaN: bigint
): bigint {
  const rInv = modInv(rBlind, rsaN);
  return (sPrime * rInv) % rsaN;
}

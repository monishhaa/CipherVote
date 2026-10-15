/**
 * In-Browser RFC 3526 MODP Group 14 Cryptographic Primitives (BigInt & WebCrypto).
 */

export const RFC3526_P_HEX =
  "FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD1" +
  "29024E088A67CC74020BBEA63B139B22514A08798E3404DD" +
  "EF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245" +
  "E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7ED" +
  "EE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3D" +
  "C2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F" +
  "83655D23DCA3AD961C62F356208552BB9ED529077096966D" +
  "670C354E4ABC9804F1746C08CA18217C32905E462E36CE3B" +
  "E39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9" +
  "DE2BCBF6955817183995497CEA956AE515D2261898FA0510" +
  "15728E5A8AACAA68FFFFFFFFFFFFFFFF";

export const P = BigInt("0x" + RFC3526_P_HEX);
export const Q = (P - 1n) / 2n;
export const G = 2n;

/**
 * Modular Exponentiation: (base^exp) mod mod
 */
export function modPow(base: bigint, exp: bigint, mod: bigint): bigint {
  let res = 1n;
  let b = base % mod;
  let e = exp;
  while (e > 0n) {
    if (e % 2n === 1n) {
      res = (res * b) % mod;
    }
    b = (b * b) % mod;
    e = e / 2n;
  }
  return res;
}

/**
 * Extended Euclidean Algorithm for Modular Inverse: a^(-1) mod m
 */
export function modInv(a: bigint, m: bigint): bigint {
  let [old_r, r] = [a, m];
  let [old_s, s] = [1n, 0n];

  while (r !== 0n) {
    const q = old_r / r;
    [old_r, r] = [r, old_r - q * r];
    [old_s, s] = [s, old_s - q * s];
  }

  return (old_s % m + m) % m;
}

/**
 * CSPRNG Random Scalar in [1, order - 1]
 */
export function getRandomScalar(order: bigint = Q): bigint {
  const byteLen = 256;
  const bytes = new Uint8Array(byteLen);
  window.crypto.getRandomValues(bytes);

  let hex = "";
  for (let i = 0; i < bytes.length; i++) {
    hex += bytes[i].toString(16).padStart(2, "0");
  }

  const val = BigInt("0x" + hex) % (order - 1n);
  return val + 1n;
}

/**
 * Fiat-Shamir SHA-256 Hash Function mapped into Fq
 */
export async function hashToScalar(...args: (bigint | string)[]): Promise<bigint> {
  const parts: Uint8Array[] = [];
  const encoder = new TextEncoder();

  for (const arg of args) {
    if (typeof arg === "bigint") {
      let hex = arg.toString(16);
      if (hex.length % 2 !== 0) hex = "0" + hex;
      const bytes = new Uint8Array(hex.length / 2);
      for (let i = 0; i < hex.length; i += 2) {
        bytes[i / 2] = parseInt(hex.substring(i, i + 2), 16);
      }
      parts.push(bytes);
    } else {
      parts.push(encoder.encode(arg));
    }
    parts.push(encoder.encode("|"));
  }

  // Concatenate parts
  const totalLen = parts.reduce((acc, p) => acc + p.length, 0);
  const fullBytes = new Uint8Array(totalLen);
  let offset = 0;
  for (const p of parts) {
    fullBytes.set(p, offset);
    offset += p.length;
  }

  const digestBuffer = await window.crypto.subtle.digest("SHA-256", fullBytes);
  const digestBytes = new Uint8Array(digestBuffer);
  let hex = "";
  for (let i = 0; i < digestBytes.length; i++) {
    hex += digestBytes[i].toString(16).padStart(2, "0");
  }

  return BigInt("0x" + hex) % Q;
}

/**
 * HMAC-SHA256 request signing — spec §12.1.
 * Uses Web Crypto API (isomorphic: browser, Node.js 18+, Cloudflare Workers).
 */

export interface AuthHeaders {
  "X-Polyeval-Signature": string;
  "X-Polyeval-Timestamp": string;
  "X-Polyeval-Nonce": string;
  "X-Polyeval-Tenant": string;
}

export async function signRequest(
  body: Uint8Array,
  tenant: string,
  secret: string,
): Promise<AuthHeaders> {
  const timestamp = new Date().toISOString();
  const nonce = crypto.randomUUID();

  let signature: string;
  if (secret) {
    const key = await crypto.subtle.importKey(
      "raw",
      new TextEncoder().encode(secret),
      { name: "HMAC", hash: "SHA-256" },
      false,
      ["sign"],
    );
    const mac = await crypto.subtle.sign("HMAC", key, body);
    const hex = Array.from(new Uint8Array(mac))
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");
    signature = `hmac-sha256:${hex}`;
  } else {
    signature = "hmac-sha256:dev";
  }

  return {
    "X-Polyeval-Signature": signature,
    "X-Polyeval-Timestamp": timestamp,
    "X-Polyeval-Nonce": nonce,
    "X-Polyeval-Tenant": tenant,
  };
}

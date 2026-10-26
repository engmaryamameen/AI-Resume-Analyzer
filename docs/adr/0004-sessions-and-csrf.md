# ADR 0004: Server-side sessions with CSRF tokens

**Status:** accepted · **Decision:** opaque session tokens in HttpOnly SameSite=Lax cookies, stored
only as keyed hashes; a separate per-session CSRF token sent in a header on every state-changing
request; an `Origin` check; the browser talks to a single origin through a Next.js proxy.
**Consequences:** instant revocation; one lookup per request; no token-in-script exposure.
**Rejected:** JWTs in local storage (not revocable, script-readable).
**Open:** no multi-device session list, no MFA, no email verification or password reset.

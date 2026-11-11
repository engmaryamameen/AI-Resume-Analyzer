# Optional Stripe test checkout

Rolemaker demonstrates a one-time **5-review pack for $5 USD**, with no subscription. Billing is off by default, so existing local workflows stay free. Live Stripe keys/events are rejected. Real-money checkout is not supported.

## Local configuration

Install the locked backend requirements and apply `alembic upgrade head` (migrations through `0005`). Add sandbox credentials manually to the ignored `.env`:

```dotenv
BILLING_ENABLED=true
BILLING_REQUIRE_CREDITS=false
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
PUBLIC_APP_URL=http://localhost:3000
```

Use an `sk_test_` secret key. Obtain a webhook signing secret from Stripe CLI forwarding or a configured sandbox endpoint; the `whsec_` value is different from the API key. Do not put either in frontend code or chat. With the official Stripe CLI authenticated to your sandbox:

```bash
stripe listen --forward-to localhost:3000/api/v1/billing/webhook
```

Use the signing secret printed by that listener for the backend, then restart/recreate the API after updating configuration. Visit **Review credits** in the signed-in workspace and open test checkout. Follow [Stripe's testing guide](https://docs.stripe.com/testing) for test payment details; never use a real card. No publishable frontend key is needed for a hosted Checkout redirect.

Without credentials, the page accurately reports that checkout is unavailable. Before enabling charging, complete a sandbox payment and confirm the signed provider event settles exactly one credit pack.

### Included Docker listener

`docker compose --profile billing up -d stripe-listener` starts the optional digest-pinned official Stripe CLI container. It forwards only Checkout completion/success test events to the local edge and uses the existing test API key. Set the listener's signing secret in the ignored `.env`, then recreate the API so it loads the new value. Listener logs contain the signing secret: treat them as credentials and do not publish them.

The listener uses the same `unless-stopped` restart policy as the local application. Keep it running for local test settlement. Use `docker compose --profile billing stop` to stop the complete local stack including payment forwarding. This creates no publicly accessible webhook endpoint. The listener joins only the egress-enabled public network; it cannot directly access the private database network.

## Boundaries and accounting

- `GET /api/v1/billing` returns account balance and fixed pack terms.
- `POST /billing/checkout` requires authentication, CSRF and an idempotency key. The server fixes currency, amount and pack size; client-supplied prices have no effect. An order is committed before the network call; a stable order ID is the Stripe idempotency key across uncertain retries.
- `POST /billing/webhook` is authenticated by Stripe's timestamped signature over the original request bytes, not a user cookie or CSRF token. Only completed/async-succeeded, paid, test Checkout sessions with the expected amount, currency, mode and order reference grant credits. A browser redirect never grants credits.
- `billing_orders` belong to an account. The order's paid flag and the unique ledger reference prevent repeat fulfillment across redelivery or different Stripe event IDs. User advisory locks serialize fulfillment, spending, cancellation and deletion.
- `credit_entries` records +5 per paid pack, −1 per new account analysis, and +1 per failed/cancelled paid run. SQL constraints validate entry kinds/amounts and unique references. Spending and analysis enqueueing share one transaction. Idempotent analysis retries do not charge twice. Concurrent requests cannot overdraw the balance.
- Guest/demo analysis remains separate and free. Disabling billing stops charging credits, but previous entries remain visible. Deleting a report does not grant a refund for a successfully completed review. Account deletion cascades local billing records; later provider events do not recreate the account.
- Only an opaque order ID and pack information are sent by the server to Stripe. Résumé content and role text never leave through the payment integration. Stripe collects payment data on its own hosted page.

The API needs outbound HTTPS to Stripe when enabled. The worker uses no Stripe credentials or outbound payment calls; it only returns a credit transactionally on failure/cancellation. Shared internal worker isolation is unchanged.

Tests use signed synthetic events through the real webhook route and actual PostgreSQL. Stripe's network call alone is replaced in transport tests. They cover price tampering, forged/stale signatures, unpaid/live/mismatched events, redelivery, contention, run replay, cancellation and failure refunds. Real sandbox delivery, account configuration, taxes, disputes, financial refunds and commercial compliance are not claimed.

## Free local reviews and optional charging

`BILLING_ENABLED=true` enables sandbox checkout. Local reviews remain free while `BILLING_REQUIRE_CREDITS=false`, even when checkout is enabled. Set both flags to true to demonstrate transactional spending and failure/cancellation refunds. Existing credit entries remain visible when charging is disabled. The UI reports this distinction; a successful browser return never grants credits.

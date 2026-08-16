## Verified Failure Modes

### PostgreSQL unavailable
**Observed:** Webhook cannot persist the event.

**Mitigation:** Return an error so the webhook provider can retry.

### Worker crash
**Observed:** Worker terminates while jobs remain pending.

**Mitigation:** Jobs remain persisted in PostgreSQL and are processed after
the worker restarts.

### PseudoGram 500
**Observed:** DM request fails with HTTP 500.

**Mitigation:** Job remains persistent and is retried using exponential
backoff.

### PseudoGram 429
**Observed:** Rate limit response.

**Mitigation:** Respect `Retry-After` and delay the next attempt.

### 202 accepted then failed
**Observed:** PseudoGram accepts the DM but later reports failure.

**Mitigation:** Reconciliation detects the failure and schedules a retry.
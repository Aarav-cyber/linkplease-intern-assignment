# Known Failure Modes

This document records failure modes that have been identified through
implementation and testing. It will be updated as additional failure and
load tests are performed.

## Currently known

- If the application is completely unavailable when the mock API sends a
  webhook and the provider does not successfully redeliver it, the event
  can be missed.

- If PostgreSQL is unavailable, the webhook cannot durably record the event.
  The application should return a failure so the provider can retry rather
  than pretending the event was processed.

- If the worker process is terminated while an in-memory operation is in
  progress, the current implementation depends on the persistent `dm_jobs`
  state to recover. Worker claiming and recovery behavior still needs to be
  tested under process termination.

- The mock DM API can return HTTP 500 responses. The worker must retry these
  failures without losing the persistent DM job.

- The mock DM API can return HTTP 429 responses. The worker must respect the
  `Retry-After` header and avoid exceeding the provider's rate limit.

- A DM request returning HTTP 202 only means the mock API accepted the
  request. The DM may later become `failed`, so delivery reconciliation is
  required before reporting it as successfully delivered.

- A worker crash between the external DM API accepting a request and the
  database recording its `dm_id` can potentially cause the request to be
  attempted again. The PseudoGram `Idempotency-Key` must be used to make
  retries safe.

- The 500-event/10-second load test has not yet been completed. Rate-limit
  behavior, queue recovery, and final statistics still need to be verified
  under that workload.
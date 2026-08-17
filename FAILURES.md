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

  - A worker can crash after PseudoGram accepts a DM but before the database
  transaction commits the returned `dm_id`. The job may be attempted again
  after restart. This is safe only because every send uses a deterministic
  PseudoGram `Idempotency-Key` derived from the DM job ID.

  - Network timeouts and other HTTP transport errors are retried with
  exponential backoff. If the maximum retry count is reached, the job is
  marked failed and the error is persisted in `last_error`.

  # Known Failure Modes

This document intentionally lists cases where the system can still lose a DM,
send an incorrect result, or report an imperfect number.

## 1. Process crash between an external DM send and database commit

If the worker successfully sends a DM to PseudoGram, but the application
process crashes before the database transaction commits the resulting
`dm_id`, the database may still contain the job as `pending`.

The worker can retry the job later.

The PseudoGram client uses an idempotency key based on the DM job ID:

`dm-job:<job_id>`

This prevents the retry from creating another DM when PseudoGram receives
the same request again.

This protects against duplicate delivery, but a crash at this exact point
can still temporarily leave our local database state inconsistent with the
external API.

## 2. Worker crash while a retry is scheduled

Retry information such as `attempts`, `next_attempt_at`, and `last_error`
is stored in PostgreSQL, so scheduled retries survive a worker restart.

However, if the worker crashes during an external request, the exact outcome
of that request may be unknown.

The next attempt relies on PseudoGram's idempotency key to prevent a duplicate
DM if the previous request was actually accepted.

## 3. Delivery reconciliation can temporarily lag

A DM accepted by PseudoGram is initially stored as `queued`.

The system periodically reconciles queued DMs using:

`GET /v1/dm/{dm_id}`

If the reconciliation worker is stopped, overloaded, or unavailable, a
successfully delivered DM may remain reported as `queued` until reconciliation
runs again.

Therefore `/stats` can temporarily lag behind PseudoGram's real delivery
state.

## 4. Concurrent rule creation can create multiple matching rules

The system intentionally allows multiple rules with the same keyword.

If two separate rules contain the same keyword, a matching comment can create
one DM job for each rule because the uniqueness guarantee is:

`(rule_id, recipient_user_id)`

rather than just:

`(recipient_user_id)`

This is correct according to the rule-based model, but it means two different
rules can legitimately result in two DMs to the same user.

## 5. Statistics are database state, not an atomic snapshot of the external API

`/stats` counts the current PostgreSQL state.

A worker may be updating a DM job while `/stats` is being requested.
Consequently, statistics represent a live database snapshot and can change
immediately after the response is returned.

For example, a job can change from:

`queued -> sent`

immediately after `/stats` reports it as queued.

The values are therefore accurate for the database state observed by that
request, but cannot represent a permanently frozen global snapshot.

## 6. Webhook events that arrive after permanent delivery failure

The system processes each `event_id` exactly once.

If an event has already been processed and its associated DM has eventually
failed permanently, a later redelivery of the same event is intentionally
ignored because the event ID has already been recorded.

This prevents duplicate processing, but it also means the original event is
not automatically replayed from the webhook itself.

Recovery is handled through the persisted DM job and retry/reconciliation
logic instead.

## 7. Environment-specific database configuration

The application uses different database connection addresses depending on
where it runs.

When running Python directly on the host machine, PostgreSQL is exposed through:

`localhost:5433`

When running inside Docker, containers must connect through the Docker service
name:

`db:5432`

Using `localhost:5433` inside the API or worker container causes database
connection failures because `localhost` refers to the container itself.

Alembic was also initially configured with the host-machine URL. The migration
configuration was updated to use the `DATABASE_URL` environment variable so
migrations work correctly inside Docker.

## 8. Worker and API are separate processes

The API and worker run as separate containers.

If the API is running but the worker is stopped, webhook requests can still be
accepted and DM jobs can be persisted, but pending jobs will not be sent until
the worker becomes available.

Similarly, if PostgreSQL is unavailable, both the API and worker can become
unable to process persisted state.

## 9. Statistics can temporarily contain zero values

The `/stats` endpoint reports the current PostgreSQL state.

A newly received webhook may have not yet created a completed DM job, or a DM
may still be waiting for the worker or reconciliation process.

Therefore a response such as:

`sent=0, failed=0, queued=0`

does not necessarily mean that no events have been received. It represents
the DM job state at the moment the statistics query executes.

## 10. Local test environment is different from production

The automated test suite uses a local PostgreSQL database and mocked external
PseudoGram responses.

Passing all automated tests demonstrates the application's handling of
idempotency, retries, rate limits, reconciliation, duplicate protection and
statistics, but it does not prove that the production PseudoGram service,
deployment infrastructure, DNS, TLS, or external network connectivity will
always behave correctly.

The final 500-event simulation must therefore be performed against the
deployed public webhook endpoint.

## 11. Manual webhook integration tests require a running API

The repository contains a manual webhook test that sends a real HTTP request
to the local API.

This test is intended to be executed explicitly with:

`python tests/test_webhook.py`

It is not part of the automated pytest suite because requiring a running API
during test collection would make the test suite dependent on external
process state.

The automated tests instead exercise the webhook processing logic directly
where possible.
# LinkPlease Instagram Automation

A reliable event-driven backend that receives Instagram-style comment webhooks and sends rule-based DMs through the PseudoGram mock API.

The system is designed around idempotent event processing, persistent DM jobs, retries, rate limiting, duplicate prevention, and delivery reconciliation.

## Current Status

* [x] FastAPI application
* [x] PostgreSQL
* [x] SQLAlchemy models
* [x] Alembic migrations
* [x] Rules API
* [x] Webhook processing
* [x] HMAC webhook signature verification
* [x] Event deduplication
* [x] Comment deduplication
* [x] Persistent DM worker
* [x] Retry handling
* [x] Timeout handling
* [x] HTTP 429 handling
* [x] HTTP 500 handling
* [x] Persistent rate limiting
* [x] Rule/user duplicate prevention
* [x] Duplicate block recording
* [x] Delivery reconciliation
* [x] Statistics API
* [x] Worker throughput testing
* [x] Automated test suite
* [ ] 500-event production simulation

## Architecture

```text
PseudoGram
     |
     | POST /webhook
     v
FastAPI API
     |
     | persist event + create DM jobs
     v
PostgreSQL
     ^
     |
DM Worker
     |
     | POST /v1/dm/send
     v
PseudoGram API
     |
     | delivery status
     v
Reconciliation
     |
     v
PostgreSQL
```

The webhook endpoint does not directly send DMs.

Instead, it validates and persists the incoming event and creates persistent DM jobs. The worker processes those jobs asynchronously.

This prevents slow external API calls from blocking the webhook request.

## Stack

* Python 3.12
* FastAPI
* PostgreSQL 16
* SQLAlchemy
* Alembic
* Docker
* pytest
* httpx

## Reliability Features

### Webhook authentication

Incoming webhook requests are authenticated using an HMAC-SHA256 signature.

Requests with an invalid signature are rejected.

### Event idempotency

Each webhook event has a unique `event_id`.

An already processed event is ignored so that webhook retries do not create duplicate work.

### Comment idempotency

Comments are also inserted using their unique `comment_id`.

This prevents the same comment from generating additional DM jobs if it is received again under a different event.

### DM duplicate prevention

The database enforces:

```text
(rule_id, recipient_user_id)
```

as a unique constraint.

This prevents a user from receiving multiple DMs for the same rule.

Blocked duplicate attempts are recorded in the `duplicate_blocks` table.

### Persistent worker

DM jobs are stored in PostgreSQL before the external DM request is made.

The worker continuously searches for pending jobs and processes them.

### Retry handling

Transient failures such as:

* HTTP 429
* HTTP 500
* network errors
* timeouts

are retried using exponential backoff.

The worker respects the `Retry-After` header when provided by PseudoGram.

Permanent client errors such as HTTP 400 are not retried.

### Rate limiting

DM sends are limited to 10 requests per rolling 60-second window.

The rate limiter uses PostgreSQL so that the limit is shared across worker processes.

### Idempotent external DM requests

Every DM request contains:

```text
Idempotency-Key: dm-job:<job_id>
```

If a worker crashes after PseudoGram accepts a request but before the local database transaction is committed, a retry can safely reuse the same idempotency key.

### Delivery reconciliation

A DM initially accepted by PseudoGram is stored as `queued`.

The reconciliation process checks the external DM status and transitions the job to:

```text
sent
```

when delivery succeeds.

Failed delivery states can be retried and eventually marked as permanently failed.

## Statistics

The API exposes:

```text
GET /stats
```

Example:

```json
{
  "sent": 10,
  "failed": 1,
  "queued": 2,
  "duplicates_blocked": 3
}
```

The values represent the current state stored in PostgreSQL.

## Running Locally

Start the complete Docker stack:

```bash
docker compose up -d --build
```

Check the containers:

```bash
docker compose ps
```

The API should be available at:

```text
http://localhost:8000
```

Check statistics:

```bash
curl http://localhost:8000/stats
```

PostgreSQL is exposed to the host at:

```text
localhost:5433
```

Inside Docker, services connect to PostgreSQL using:

```text
db:5432
```

## Database Migrations

Alembic migrations are automatically executed when the API container starts.

To manually create a migration:

```bash
alembic revision --autogenerate -m "description"
```

To apply migrations manually:

```bash
alembic upgrade head
```

## Testing

Run the complete automated test suite:

```bash
python -m pytest -v
```

The current suite covers:

* PseudoGram client behavior
* rate limiting
* retry behavior
* timeout handling
* reconciliation
* statistics
* webhook duplicate prevention
* DM duplicate prevention
* worker throughput
* 429 handling
* retry exhaustion

The current automated suite contains 22 tests.

The webhook integration script can be executed manually:

```bash
python tests/test_webhook.py
```

The final validation is a 500-event simulation against the deployed public webhook endpoint.

## Environment Variables

Create a `.env` file locally:

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5433/linkplease

PSEUDOGRAM_BASE_URL=https://pseudogram-api.onrender.com
PSEUDOGRAM_API_KEY=

WORKER_POLL_INTERVAL=1
WORKER_MAX_RETRIES=3
WORKER_BACKOFF_BASE=1
WORKER_MAX_BACKOFF=30
```

Never commit `.env` or a real PseudoGram API key.

Use `.env.example` as the template for required environment variables.

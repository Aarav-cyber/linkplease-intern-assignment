# LinkPlease Instagram Automation

A reliable event-driven backend that receives Instagram-style comment
webhooks and sends rule-based DMs through the PseudoGram mock API.

## Current Status

- [x] FastAPI application
- [x] PostgreSQL
- [x] SQLAlchemy models
- [x] Alembic migrations
- [ ] Rules API
- [ ] Webhook processing
- [ ] Event deduplication
- [ ] Persistent DM worker
- [ ] Retry handling
- [ ] Rate limiting
- [ ] Delivery reconciliation
- [ ] Statistics API
- [ ] 500-event load testing

## Stack

- Python
- FastAPI
- PostgreSQL
- SQLAlchemy
- Alembic
- Docker

## Running Locally

```bash
docker compose up --build
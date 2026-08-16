# Known Failure Modes

This document will be updated throughout development and testing.

## Current known limitations

- If PostgreSQL is unavailable when a webhook arrives, the event cannot be
  durably recorded by the application.

- If the application is completely unavailable for longer than the webhook
  provider's retry window, an event could potentially be missed.

- The DM delivery worker has not yet been implemented, so DM delivery,
  retry handling, rate limiting, and reconciliation are not yet complete.

- The final failure modes will be updated after the 500-event load test and
  failure-injection tests are completed.
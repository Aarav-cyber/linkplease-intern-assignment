from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from ..models import DMSendAttempt


MAX_REQUESTS = 10
WINDOW_SECONDS = 60

RATE_LIMIT_LOCK_ID = 918273


def acquire_send_slot(db: Session) -> bool:
    """
    Atomically reserve one PseudoGram API request slot.

    Returns:
        True  -> a request may be sent.
        False -> the rate limit has been reached.
    """

    # Only one worker can make a rate-limit decision at a time.
    db.execute(
        text(
            "SELECT pg_advisory_xact_lock(:lock_id)"
        ),
        {
            "lock_id": RATE_LIMIT_LOCK_ID
        },
    )

    now = datetime.now(timezone.utc)

    window_start = now - timedelta(
        seconds=WINDOW_SECONDS
    )

    # Remove attempts outside the rolling 60-second window.
    db.execute(
        delete(DMSendAttempt).where(
            DMSendAttempt.attempted_at < window_start
        )
    )

    count = db.scalar(
        select(
            func.count(DMSendAttempt.id)
        ).where(
            DMSendAttempt.attempted_at >= window_start
        )
    )

    if count >= MAX_REQUESTS:
        return False

    db.add(
        DMSendAttempt(
            attempted_at=now
        )
    )

    db.flush()

    return True
from datetime import datetime, timezone, timedelta

from app.database import SessionLocal
from app.models import DMSendAttempt
from app.services.rate_limiter import acquire_send_slot


def clear_attempts():
    db = SessionLocal()

    try:
        db.query(DMSendAttempt).delete()
        db.commit()
    finally:
        db.close()


def test_allows_ten_requests():
    clear_attempts()

    db = SessionLocal()

    try:
        for _ in range(10):
            assert acquire_send_slot(db) is True
            db.commit()

        assert acquire_send_slot(db) is False

    finally:
        db.close()
        clear_attempts()

def test_old_requests_expire():
    clear_attempts()

    db = SessionLocal()

    try:
        old_time = datetime.now(timezone.utc) - timedelta(
            seconds=61
        )

        for _ in range(10):
            db.add(
                DMSendAttempt(
                    attempted_at=old_time
                )
            )

        db.commit()

        assert acquire_send_slot(db) is True

    finally:
        db.close()
        clear_attempts()
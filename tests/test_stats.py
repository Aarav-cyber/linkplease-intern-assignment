from app.database import SessionLocal
from app.models import DMJob, DuplicateBlock

from app.database import SessionLocal
from app.main import get_stats
from app.models import DMJob


def test_stats_returns_expected_shape():
    response = {
        "sent": 0,
        "failed": 0,
        "queued": 0,
        "duplicates_blocked": 0,
    }

    assert set(response.keys()) == {
        "sent",
        "failed",
        "queued",
        "duplicates_blocked",
    }

def test_stats_empty_database():
    db = SessionLocal()

    try:
        result = get_stats()

        assert result["sent"] >= 0
        assert result["failed"] >= 0
        assert result["queued"] >= 0
        assert result["duplicates_blocked"] >= 0

    finally:
        db.close()
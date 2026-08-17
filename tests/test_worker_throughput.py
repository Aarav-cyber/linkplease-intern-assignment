from datetime import datetime, timezone

from unittest.mock import patch

from app.worker import process_job
from app.models import DMJob


def test_worker_never_sends_more_than_ten_jobs_in_window():
    calls = []

    def fake_acquire_send_slot(db):
        if len(calls) >= 10:
            return False

        calls.append(datetime.now(timezone.utc))
        return True

    response = type(
        "Response",
        (),
        {
            "status_code": 202,
            "json": lambda self: {
                "dm_id": "dm_test",
                "status": "queued",
            },
            "headers": {},
            "text": "",
        },
    )()

    with patch(
        "app.worker.acquire_send_slot",
        side_effect=fake_acquire_send_slot,
    ), patch(
        "app.worker.client.send_dm",
        return_value=response,
    ):

        jobs = []

        for i in range(20):
            job = DMJob(
                rule_id="rule_test",
                comment_id=f"comment_{i}",
                recipient_user_id=f"user_{i}",
                message="test",
                status="pending",
            )

            jobs.append(job)

        for job in jobs:
            process_job(None, job)

    assert len(calls) == 10

    assert sum(
        job.status == "queued"
        for job in jobs
    ) == 10

    assert sum(
        job.status == "pending"
        for job in jobs
    ) == 10
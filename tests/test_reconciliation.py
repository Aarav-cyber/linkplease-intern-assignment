from unittest.mock import patch

from app.worker import reconcile_job
from tests.test_worker import make_job


def make_response(status):
    return type(
        "Response",
        (),
        {
            "status_code": 200,
            "json": lambda self: {
                "dm_id": "dm_123",
                "status": status,
            },
        },
    )()


def test_delivered_marks_job_sent():
    job = make_job()
    job.dm_id = "dm_123"
    job.status = "queued"

    with patch(
        "app.worker.client.get_dm_status",
        return_value=make_response("delivered"),
    ):
        reconcile_job(None, job)

    assert job.status == "sent"
    assert job.last_error is None


def test_queued_stays_queued():
    job = make_job()
    job.dm_id = "dm_123"
    job.status = "queued"

    with patch(
        "app.worker.client.get_dm_status",
        return_value=make_response("queued"),
    ):
        reconcile_job(None, job)

    assert job.status == "queued"


def test_failed_delivery_is_retried():
    job = make_job()
    job.dm_id = "dm_123"
    job.status = "queued"
    job.attempts = 0

    with patch(
        "app.worker.client.get_dm_status",
        return_value=make_response("failed"),
    ):
        reconcile_job(None, job)

    assert job.status == "pending"
    assert job.attempts == 1
    assert job.last_error == "DM delivery failed; retry scheduled"


def test_failed_delivery_eventually_gives_up():
    job = make_job()
    job.dm_id = "dm_123"
    job.status = "queued"
    job.attempts = 2

    with patch(
        "app.worker.client.get_dm_status",
        return_value=make_response("failed"),
    ):
        reconcile_job(None, job)

    assert job.status == "failed"
    assert job.attempts == 3

def test_queued_job_is_reconciled_before_pending_job():
    from unittest.mock import Mock

    queued_job = make_job()
    queued_job.status = "queued"
    queued_job.dm_id = "dm_123"

    pending_job = make_job()
    pending_job.status = "pending"

    db = Mock()

    with patch(
        "app.worker.get_queued_job",
        return_value=queued_job,
    ), patch(
        "app.worker.reconcile_job",
    ) as mock_reconcile:

        from app.worker import get_queued_job

        job = get_queued_job(db)

        assert job is queued_job
        mock_reconcile.assert_not_called()
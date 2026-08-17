import httpx

from types import SimpleNamespace
from unittest.mock import patch

from app.worker import process_job


def make_job():
    return SimpleNamespace(
        id="job-123",
        recipient_user_id="usr_123",
        message="Here's the price",
        comment_id="cmt_123",
        status="pending",
        dm_id=None,
        attempts=0,
        next_attempt_at=None,
        last_error=None,
    )


def make_response(
    status_code,
    json_data=None,
    headers=None,
):
    return SimpleNamespace(
        status_code=status_code,
        headers=headers or {},
        text="error",
        json=lambda: json_data or {},
    )

def test_successful_dm():
    job = make_job()

    response = make_response(
        202,
        {"dm_id": "dm_123", "status": "queued"},
    )

    with patch(
        "app.worker.client.send_dm",
        return_value=response,
    ):
        process_job(job)

    assert job.status == "queued"
    assert job.dm_id == "dm_123"
    assert job.last_error is None

def test_bad_request_fails_without_retry():
    job = make_job()

    response = make_response(
        400,
        {
            "error": "invalid_request",
            "detail": "bad payload",
        },
    )

    with patch(
        "app.worker.client.send_dm",
        return_value=response,
    ):
        process_job(job)

    assert job.status == "failed"
    assert job.attempts == 0

def test_server_error_retries():
    job = make_job()

    response = make_response(
        500,
        {"error": "internal_error"},
    )

    with patch(
        "app.worker.client.send_dm",
        return_value=response,
    ):
        process_job(job)

    assert job.status == "pending"
    assert job.attempts == 1
    assert job.next_attempt_at is not None

def test_rate_limit_respects_retry_after():
    job = make_job()

    response = make_response(
        429,
        {"error": "rate_limited"},
        {"Retry-After": "15"},
    )

    with patch(
        "app.worker.client.send_dm",
        return_value=response,
    ):
        process_job(job)

    assert job.status == "pending"
    assert job.attempts == 1
    assert job.next_attempt_at is not None

def test_retry_exhaustion():
    job = make_job()
    job.attempts = 2

    response = make_response(
        500,
        {"error": "internal_error"},
    )

    with patch(
        "app.worker.client.send_dm",
        return_value=response,
    ):
        process_job(job)

    assert job.attempts == 3
    assert job.status == "failed"

def test_timeout_is_recoverable():
    job = make_job()

    with patch(
        "app.worker.client.send_dm",
        side_effect=httpx.TimeoutException("timeout"),
    ):
        process_job(job)

    assert job.status == "pending"
    assert job.attempts == 1
    assert job.next_attempt_at is not None
    assert "timeout" in job.last_error

def test_timeout_retry_exhaustion():
    job = make_job()
    job.attempts = 2

    with patch(
        "app.worker.client.send_dm",
        side_effect=httpx.TimeoutException("timeout"),
    ):
        process_job(job)

    assert job.status == "failed"
    assert job.attempts == 3
    assert "timeout" in job.last_error
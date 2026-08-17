import httpx

import time
from datetime import datetime, timezone, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.services.rate_limiter import acquire_send_slot

from .database import SessionLocal
from .models import DMJob
from .services.pseudogram_client import PseudoGramClient


POLL_INTERVAL = 1
MAX_RETRIES = 3
BACKOFF_BASE = 1
MAX_BACKOFF = 30


client = PseudoGramClient()


def get_pending_job(db: Session):
    now = datetime.now(timezone.utc)

    statement = (   
        select(DMJob)
        .where(
            DMJob.status == "pending",
            DMJob.next_attempt_at <= now,
        )
        .order_by(DMJob.created_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )

    return db.scalars(statement).first()

def get_queued_job(db: Session):
    statement = (
        select(DMJob)
        .where(
            DMJob.status == "queued",
            DMJob.dm_id.is_not(None),
        )
        .order_by(DMJob.updated_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )

    return db.scalars(statement).first()

def calculate_backoff(attempts: int) -> int:
    delay = BACKOFF_BASE * (2 ** (attempts - 1))

    return min(
        delay,
        MAX_BACKOFF,
    )


def process_job(
    db: Session,
    job: DMJob,
):

    if not acquire_send_slot(db):
        return
    
    try:
        response = client.send_dm(
            recipient_user_id=job.recipient_user_id,
            message=job.message,
            comment_id=job.comment_id,
            job_id=str(job.id),
        )

    except httpx.TimeoutException as exc:
        job.attempts += 1

        if job.attempts >= MAX_RETRIES:
            job.status = "failed"
        else:
            delay = calculate_backoff(job.attempts)

            job.next_attempt_at = (
                datetime.now(timezone.utc)
                + timedelta(seconds=delay)
            )

        job.last_error = f"timeout: {exc}"

        return

    except httpx.HTTPError as exc:
        job.attempts += 1

        if job.attempts >= MAX_RETRIES:
            job.status = "failed"
        else:
            delay = calculate_backoff(job.attempts)

            job.next_attempt_at = (
                datetime.now(timezone.utc)
                + timedelta(seconds=delay)
            )

        job.last_error = f"network error: {exc}"

        return

    if response.status_code == 202:
        data = response.json()

        job.dm_id = data["dm_id"]
        job.status = "queued"
        job.last_error = None

        return

    if response.status_code == 400:
        try:
            detail = response.json()
        except Exception:
            detail = response.text

        job.status = "failed"
        job.last_error = str(detail)

        return

    if response.status_code in (429, 500):
        job.attempts += 1

        if job.attempts >= MAX_RETRIES:
            job.status = "failed"

            try:
                error = response.json()
            except Exception:
                error = response.text

            job.last_error = str(error)

            return

        retry_after = response.headers.get("Retry-After")

        if retry_after:
            delay = int(retry_after)
        else:
            delay = calculate_backoff(job.attempts)

        job.next_attempt_at = (
            datetime.now(timezone.utc)
            + timedelta(seconds=delay)
        )

        try:
            error = response.json()
        except Exception:
            error = response.text

        job.last_error = str(error)

        return

    job.attempts += 1

    if job.attempts >= MAX_RETRIES:
        job.status = "failed"
    else:
        job.next_attempt_at = (
            datetime.now(timezone.utc)
            + timedelta(
                seconds=calculate_backoff(job.attempts)
            )
        )

    job.last_error = (
        f"Unexpected HTTP status: {response.status_code}"
    )

def reconcile_job(
    db: Session,
    job: DMJob,
):
    if not job.dm_id:
        return

    try:
        response = client.get_dm_status(job.dm_id)

    except httpx.HTTPError as exc:
        job.last_error = f"reconciliation network error: {exc}"
        return

    if response.status_code != 200:
        job.last_error = (
            f"reconciliation HTTP status: "
            f"{response.status_code}"
        )
        return

    try:
        data = response.json()
    except Exception as exc:
        job.last_error = (
            f"invalid reconciliation response: {exc}"
        )
        return

    status = data.get("status")

    if status == "delivered":
        job.status = "sent"
        job.last_error = None
        return

    if status == "queued":
        # Still waiting for delivery.
        return

    if status == "failed":
        job.attempts += 1

        if job.attempts >= MAX_RETRIES:
            job.status = "failed"
            job.last_error = "DM delivery failed after retries"
            return

        job.status = "pending"

        delay = calculate_backoff(job.attempts)

        job.next_attempt_at = (
            datetime.now(timezone.utc)
            + timedelta(seconds=delay)
        )

        job.last_error = "DM delivery failed; retry scheduled"
        return

    job.last_error = (
        f"Unknown DM delivery status: {status}"
    )

def run_worker():
    while True:
        db = SessionLocal()

        try:
            # First check whether a queued DM has a delivery update.
            queued_job = get_queued_job(db)

            if queued_job:
                reconcile_job(db, queued_job)
                db.commit()
                continue

            # If there is nothing to reconcile,
            # look for a new/retryable DM.
            pending_job = get_pending_job(db)

            if not pending_job:
                db.close()
                time.sleep(POLL_INTERVAL)
                continue

            process_job(db, pending_job)

            db.commit()

        except Exception as exc:
            db.rollback()
            print(f"Worker error: {exc}")

        finally:
            db.close()

if __name__ == "__main__":
    run_worker()
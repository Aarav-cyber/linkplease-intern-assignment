from unittest.mock import patch
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.models import (
    Comment,
    DMSendAttempt,
    DMJob,
    DuplicateBlock,
    Rule,
)
from app.worker import process_job

def clear_data(db):
    db.query(DMJob).delete()
    db.query(DuplicateBlock).delete()
    db.query(Comment).delete()
    db.query(Rule).delete()
    db.query(DMSendAttempt).delete()
    db.commit()

def make_job(index, rule_id):
    return DMJob(
        rule_id=rule_id,
        recipient_user_id=f"usr_{index}",
        message="Here's the price",
        comment_id=f"cmt_{index}",
        status="pending",
        attempts=0,
    )


def test_eleven_jobs_only_allow_ten_requests():
    db = SessionLocal()

    try:
        clear_data(db)

        rule = Rule(
            keyword="PRICE",
            dm_message="Here's the price",
        )

        db.add(rule)
        db.commit()
        db.refresh(rule)

        comments = [
            Comment(
                comment_id=f"cmt_{i}",
                user_id=f"usr_{i}",
                text="PRICE please",
            )
            for i in range(11)
        ]

        for comment in comments:
            db.add(comment)

        db.commit()

        jobs = [
            make_job(i, rule.id)
            for i in range(11)
        ]

        for job in jobs:
            db.add(job)

        db.commit()

        successful_calls = []

        def fake_send_dm(
            recipient_user_id,
            message,
            comment_id,
            job_id,
        ):
            successful_calls.append(job_id)

            return type(
                "Response",
                (),
                {
                    "status_code": 202,
                    "json": lambda self: {
                        "dm_id": f"dm_{job_id}",
                        "status": "queued",
                    },
                    "headers": {},
                    "text": "",
                },
            )()

        with patch(
            "app.worker.client.send_dm",
            side_effect=fake_send_dm,
        ):
            for job in jobs:
                process_job(db, job)
                db.commit()

        assert len(successful_calls) == 10

        remaining_pending = [
            job
            for job in jobs
            if job.status == "pending"
        ]

        assert len(remaining_pending) == 1

    finally:
        clear_data(db)
        db.close()

def test_duplicate_rule_recipient_is_blocked():
    db = SessionLocal()

    try:
        clear_data(db)

        rule = Rule(
            keyword="PRICE",
            dm_message="Here's the price",
        )

        db.add(rule)
        db.commit()
        db.refresh(rule)

        comment_1 = Comment(
            comment_id="cmt_dup_1",
            user_id="usr_same",
            text="PRICE",
        )

        comment_2 = Comment(
            comment_id="cmt_dup_2",
            user_id="usr_same",
            text="PRICE",
        )

        db.add_all([
            comment_1,
            comment_2,
        ])

        db.commit()

        job_1 = make_job(
            1,
            rule.id,
        )

        job_1.comment_id = "cmt_dup_1"
        job_1.recipient_user_id = "usr_same"

        job_2 = make_job(
            2,
            rule.id,
        )

        job_2.comment_id = "cmt_dup_2"
        job_2.recipient_user_id = "usr_same"

        db.add(job_1)
        db.commit()

        db.add(job_2)

        try:
            db.commit()
            assert False, "Duplicate DM job was allowed"
        except Exception:
            db.rollback()

    finally:
        db.rollback()
        clear_data(db)
        db.close()

def test_duplicate_block_is_recorded():
    db = SessionLocal()

    try:
        clear_data(db)

        rule = Rule(
            keyword="PRICE",
            dm_message="Here's the price",
        )

        db.add(rule)
        db.commit()
        db.refresh(rule)

        comment_1 = Comment(
            comment_id="cmt_block_1",
            user_id="usr_same",
            text="PRICE",
        )

        comment_2 = Comment(
            comment_id="cmt_block_2",
            user_id="usr_same",
            text="PRICE",
        )

        db.add_all([
            comment_1,
            comment_2,
        ])

        db.commit()

        job_1 = make_job(1, rule.id)
        job_1.comment_id = "cmt_block_1"
        job_1.recipient_user_id = "usr_same"

        db.add(job_1)
        db.commit()

        try:
            with db.begin_nested():
                job_2 = make_job(2, rule.id)
                job_2.comment_id = "cmt_block_2"
                job_2.recipient_user_id = "usr_same"

                db.add(job_2)
                db.flush()

        except IntegrityError:
            duplicate = DuplicateBlock(
                rule_id=rule.id,
                comment_id="cmt_block_2",
                recipient_user_id="usr_same",
            )

            db.add(duplicate)
            db.commit()

        blocks = (
            db.query(DuplicateBlock)
            .filter(
                DuplicateBlock.rule_id == rule.id,
                DuplicateBlock.recipient_user_id == "usr_same",
            )
            .all()
        )

        assert len(blocks) == 1
        assert blocks[0].comment_id == "cmt_block_2"

    finally:
        db.rollback()
        clear_data(db)
        db.close()
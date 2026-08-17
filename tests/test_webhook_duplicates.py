import json

from app.database import SessionLocal
from app.models import Comment, DMJob, DuplicateBlock, Event, Rule
from app.services.webhook_service import process_event


def clear_data(db):
    db.query(DMJob).delete()
    db.query(DuplicateBlock).delete()
    db.query(Comment).delete()
    db.query(Event).delete()
    db.query(Rule).delete()
    db.commit()


def make_payload(event_id, comment_id):
    return json.dumps(
        {
            "event_id": event_id,
            "event_type": "comment.created",
            "sent_at": "2026-08-17T00:00:00Z",
            "data": {
                "comment_id": comment_id,
                "post_id": "post_001",
                "text": "PRICE please",
                "created_at": "2026-08-17T00:00:00Z",
                "from": {
                    "user_id": "usr_same",
                    "username": "aarav",
                },
            },
        }
    ).encode()


def test_same_user_same_rule_only_creates_one_dm_job():
    db = SessionLocal()

    try:
        clear_data(db)

        rule = Rule(
            keyword="PRICE",
            dm_message="Here's the price list",
        )

        db.add(rule)
        db.commit()

        payload_1 = make_payload(
            "evt_dup_001",
            "cmt_dup_001",
        )

        payload_2 = make_payload(
            "evt_dup_002",
            "cmt_dup_002",
        )

        assert process_event(db, payload_1) is True
        assert process_event(db, payload_2) is True

        jobs = (
            db.query(DMJob)
            .filter(DMJob.rule_id == rule.id)
            .all()
        )

        blocks = (
            db.query(DuplicateBlock)
            .filter(
                DuplicateBlock.rule_id == rule.id,
                DuplicateBlock.recipient_user_id == "usr_same",
            )
            .all()
        )

        assert len(jobs) == 1
        assert jobs[0].recipient_user_id == "usr_same"
        assert jobs[0].comment_id == "cmt_dup_001"

        assert len(blocks) == 1
        assert blocks[0].comment_id == "cmt_dup_002"

    finally:
        db.rollback()
        clear_data(db)
        db.close()
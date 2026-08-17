import json

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import (
    Comment,
    DMJob,
    DuplicateBlock,
    Event,
    Rule,
)


def record_duplicate_block(
    db: Session,
    rule_id,
    comment_id,
    recipient_user_id,
):
    duplicate = DuplicateBlock(
        rule_id=rule_id,
        comment_id=comment_id,
        recipient_user_id=recipient_user_id,
    )

    db.add(duplicate)
    db.flush()


def process_event(
    db: Session,
    payload: bytes,
) -> bool:
    data = json.loads(payload)

    event_id = data["event_id"]
    event_type = data["event_type"]

    try:
        # Insert the event exactly once.
        event_statement = (
            insert(Event)
            .values(
                event_id=event_id,
                event_type=event_type,
                payload=payload.decode("utf-8"),
            )
            .on_conflict_do_nothing(
                index_elements=[Event.event_id]
            )
        )

        result = db.execute(event_statement)

        # Event already existed.
        if result.rowcount == 0:
            db.rollback()
            return False

        if event_type == "comment.created":
            comment_data = data["data"]

            comment_id = comment_data["comment_id"]
            user_id = comment_data["from"]["user_id"]
            username = comment_data["from"]["username"]
            comment_text = comment_data.get("text") or ""

            # Insert the comment exactly once.
            comment_statement = (
                insert(Comment)
                .values(
                    comment_id=comment_id,
                    post_id=comment_data.get("post_id"),
                    user_id=user_id,
                    username=username,
                    text=comment_text,
                )
                .on_conflict_do_nothing(
                    index_elements=[Comment.comment_id]
                )
            )

            comment_result = db.execute(comment_statement)

            # Comment was already processed.
            # Do not create another DM job.
            if comment_result.rowcount == 0:
                db.commit()
                return True

            rules = db.scalars(
                select(Rule)
            ).all()

            comment_text_lower = comment_text.lower()

            for rule in rules:
                if rule.keyword.lower() not in comment_text_lower:
                    continue

                try:
                    # Use a SAVEPOINT so a duplicate DMJob
                    # does not roll back the whole event.
                    with db.begin_nested():
                        job = DMJob(
                            rule_id=rule.id,
                            comment_id=comment_id,
                            recipient_user_id=user_id,
                            message=rule.dm_message,
                            status="pending",
                        )

                        db.add(job)
                        db.flush()

                except IntegrityError as exc:
                    if "uq_dm_jobs_rule_recipient" not in str(exc):
                        raise

                    record_duplicate_block(
                        db,
                        rule_id=rule.id,
                        comment_id=comment_id,
                        recipient_user_id=user_id,
                    )

        db.commit()

        return True

    except Exception:
        db.rollback()
        raise


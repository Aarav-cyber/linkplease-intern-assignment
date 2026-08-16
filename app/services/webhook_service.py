import json

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ..models import Comment, DMJob, Event, Rule


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

            comment = Comment(
                comment_id=comment_data["comment_id"],
                post_id=comment_data.get("post_id"),
                user_id=comment_data["from"]["user_id"],
                username=comment_data["from"]["username"],
                text=comment_data.get("text") or "",
            )

            db.add(comment)
            db.flush()

            rules = db.scalars(
                select(Rule)
            ).all()

            comment_text = comment.text.lower()

            for rule in rules:
                if rule.keyword.lower() not in comment_text:
                    continue

                dm_statement = (
                    insert(DMJob)
                    .values(
                        rule_id=rule.id,
                        comment_id=comment.comment_id,
                        recipient_user_id=comment.user_id,
                        message=rule.dm_message,
                        status="pending",
                    )
                    .on_conflict_do_nothing(
                        constraint="uq_rule_recipient"
                    )
                )

                db.execute(dm_statement)

        db.commit()

        return True

    except Exception:
        db.rollback()
        raise
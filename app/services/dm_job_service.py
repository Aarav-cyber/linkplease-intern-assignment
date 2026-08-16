from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ..models import DMJob


def create_dm_job(
    db: Session,
    rule_id: str,
    comment_id: str,
    recipient_user_id: str,
    message: str,
) -> bool:
    statement = insert(DMJob).values(
        rule_id=rule_id,
        comment_id=comment_id,
        recipient_user_id=recipient_user_id,
        message=message,
        status="pending",
    )

    statement = statement.on_conflict_do_nothing(
        constraint="uq_rule_recipient"
    )

    result = db.execute(statement)

    return result.rowcount == 1
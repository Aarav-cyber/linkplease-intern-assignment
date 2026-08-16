from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Rule


def find_matching_rules(
    db: Session,
    comment_text: str,
) -> list[Rule]:
    comment_text = comment_text.lower()

    rules = db.scalars(
        select(Rule)
    ).all()

    return [
        rule
        for rule in rules
        if rule.keyword.lower() in comment_text
    ]
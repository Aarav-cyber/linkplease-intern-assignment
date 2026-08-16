from datetime import datetime

from sqlalchemy.orm import Session

from ..models import Comment


def save_comment(
    db: Session,
    data: dict,
) -> Comment:
    comment = Comment(
        comment_id=data["comment_id"],
        post_id=data.get("post_id"),
        user_id=(
            data["from"]["user_id"]
            if data.get("from")
            else None
        ),
        username=(
            data["from"]["username"]
            if data.get("from")
            else None
        ),
        text=data.get("text") or "",
        created_at=(
            datetime.fromisoformat(
                data["created_at"].replace("Z", "+00:00")
            )
            if data.get("created_at")
            else None
        ),
    )

    db.add(comment)

    return comment
from datetime import datetime

from pydantic import BaseModel, Field


class WebhookUser(BaseModel):
    user_id: str
    username: str


class WebhookData(BaseModel):
    comment_id: str
    post_id: str | None = None
    text: str | None = None
    created_at: datetime | None = None
    from_: WebhookUser | None = Field(
        default=None,
        alias="from",
    )


class WebhookEvent(BaseModel):
    event_id: str
    event_type: str
    sent_at: datetime
    data: WebhookData
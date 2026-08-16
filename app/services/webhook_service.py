import json

from sqlalchemy.orm import Session

from ..models import Event


def process_event(
    db: Session,
    payload: bytes,
) -> bool:
    data = json.loads(payload)

    event_id = data["event_id"]
    event_type = data["event_type"]

    existing_event = db.get(Event, event_id)

    if existing_event:
        return False

    event = Event(
        event_id=event_id,
        event_type=event_type,
        payload=payload.decode("utf-8"),
    )

    db.add(event)
    db.commit()

    return True
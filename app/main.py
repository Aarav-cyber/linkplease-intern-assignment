from fastapi import FastAPI, Depends, Request, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session


from .models import Rule
from .schemas import RuleCreate, RuleResponse
from .database import SessionLocal, settings
from .security import verify_webhook_signature
from .services.webhook_service import process_event

app = FastAPI(title="LinkPlease Assignment")


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "linkplease",
    }


@app.get("/health")
def health():
    try:
        db = SessionLocal()

        try:
            db.execute(text("SELECT 1"))

            return {
                "status": "healthy",
                "database": "connected",
            }
        finally:
            db.close()

    except Exception:
        return {
            "status": "unhealthy",
            "database": "disconnected",
        }


@app.post(
    "/rules",
    response_model=RuleResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_rule(
    rule_data: RuleCreate,
    db: Session = Depends(get_db),
):
    rule = Rule(
        keyword=rule_data.keyword,
        dm_message=rule_data.dm_message,
    )

    db.add(rule)
    db.commit()
    db.refresh(rule)

    return RuleResponse(
        rule_id=rule.id,
        keyword=rule.keyword,
        dm_message=rule.dm_message,
    )

@app.post("/webhook")
async def webhook(request: Request):
    raw_body = await request.body()

    signature = request.headers.get(
        "X-PseudoGram-Signature",
        "",
    )

    if not verify_webhook_signature(
        raw_body,
        signature,
        settings.PSEUDOGRAM_API_KEY,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )

    db = SessionLocal()

    try:
        is_new = process_event(
            db,
            raw_body,
        )

        return {
            "status": "accepted",
            "duplicate": not is_new,
        }

    finally:
        db.close()
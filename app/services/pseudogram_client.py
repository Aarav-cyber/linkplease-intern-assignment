import httpx

from ..database import settings


class PseudoGramClient:

    def __init__(self):
        self.base_url = settings.PSEUDOGRAM_BASE_URL
        self.api_key = settings.PSEUDOGRAM_API_KEY

    def send_dm(
    self,
    recipient_user_id: str,
    message: str,
    comment_id: str,
    job_id: str,
    ):
        response = httpx.post(
            f"{self.base_url}/v1/dm/send",
            headers={
                "X-API-Key": self.api_key,
                "Idempotency-Key": f"dm-job:{job_id}",
            },
            json={
                "recipient_user_id": recipient_user_id,
                "message": message,
                "comment_id": comment_id,
            },
            timeout=10.0,
        )

        return response
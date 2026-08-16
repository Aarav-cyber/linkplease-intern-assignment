import hashlib
import hmac
import json

import requests


secret = b"test-secret"

payload = {
    "event_id": "evt_test_004",
    "event_type": "comment.created",
    "sent_at": "2026-08-17T00:00:00Z",
    "data": {
        "comment_id": "cmt_test_004",
        "post_id": "post_001",
        "text": "PRICE please",
        "created_at": "2026-08-17T00:00:00Z",
        "from": {
            "user_id": "usr_001",
            "username": "aarav",
        },
    },
}

body = json.dumps(payload).encode()

signature = hmac.new(
    secret,
    body,
    hashlib.sha256,
).hexdigest()

response = requests.post(
    "http://localhost:8000/webhook",
    data=body,
    headers={
        "Content-Type": "application/json",
        "X-PseudoGram-Signature": f"sha256={signature}",
    },
)

print(response.status_code)
print(response.json())
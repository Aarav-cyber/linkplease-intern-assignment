import hashlib
import hmac


def verify_webhook_signature(
    payload: bytes,
    signature: str,
    secret: str,
) -> bool:
    if not signature.startswith("sha256="):
        return False

    received_signature = signature[7:]

    expected_signature = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(
        received_signature,
        expected_signature,
    )
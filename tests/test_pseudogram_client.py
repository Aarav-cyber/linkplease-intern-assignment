from unittest.mock import patch

from app.services.pseudogram_client import PseudoGramClient


def test_get_dm_status():
    client = PseudoGramClient()

    fake_response = type(
        "Response",
        (),
        {
            "status_code": 200,
            "json": lambda self: {
                "dm_id": "dm_123",
                "status": "delivered",
            },
        },
    )()

    with patch(
        "app.services.pseudogram_client.httpx.get",
        return_value=fake_response,
    ) as mock_get:

        response = client.get_dm_status("dm_123")

        assert response.status_code == 200
        assert response.json()["status"] == "delivered"

        mock_get.assert_called_once()
class FakeWhatsAppClient:
    def __init__(self, payload):
        self._payload = payload

    async def get_qr(self, user_id: str):
        return self._payload


def test_whatsapp_qr_returns_image(client, auth_headers):
    payload = {"qr": "1@fakeqrcode", "status": "waiting_scan", "image": "data:image/png;base64,AAA"}
    client.app.state.whatsapp = FakeWhatsAppClient(payload)
    response = client.get("/api/whatsapp/qr", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["qr"] == "1@fakeqrcode"
    assert body["status"] == "waiting_scan"
    assert body["image"].startswith("data:image/png;base64,")


def test_whatsapp_qr_returns_null_when_no_qr(client, auth_headers):
    client.app.state.whatsapp = FakeWhatsAppClient({"qr": None, "status": "connected", "image": None})
    response = client.get("/api/whatsapp/qr", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["qr"] is None
    assert body["image"] is None
    assert body["status"] == "connected"

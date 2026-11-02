import base64
import hashlib
import hmac
import unittest

import requests

from server.feishu import build_payload, make_signature, send_message


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"code": 0}


class FeishuTests(unittest.TestCase):
    def test_signature_matches_feishu_algorithm(self) -> None:
        timestamp = 1609459200
        secret = "test-secret"
        expected = base64.b64encode(
            hmac.new(
                f"{timestamp}\n{secret}".encode(), digestmod=hashlib.sha256
            ).digest()
        ).decode()
        self.assertEqual(make_signature(timestamp, secret), expected)

    def test_signed_card_has_no_webhook_or_secret(self) -> None:
        payload = build_payload("日报", ["成功 2", "失败 0"], secret="private", timestamp=123)
        serialized = str(payload)
        self.assertNotIn("private", serialized)
        self.assertEqual(payload["timestamp"], "123")
        self.assertEqual(payload["msg_type"], "interactive")

    def test_sender_uses_timeout(self) -> None:
        captured = {}

        def post(url, **kwargs):
            captured.update(url=url, **kwargs)
            return FakeResponse()

        send_message("https://example.invalid/hook", "测试", ["正常"], post=post)
        self.assertEqual(captured["timeout"], 10)

    def test_network_error_does_not_leak_webhook(self) -> None:
        webhook = "https://open.feishu.cn/open-apis/bot/v2/hook/secret-token"

        def post(_url, **_kwargs):
            raise requests.ConnectionError(f"failed to call {webhook}")

        with self.assertRaises(RuntimeError) as captured:
            send_message(webhook, "测试", ["失败"], post=post)
        self.assertNotIn("secret-token", str(captured.exception))


if __name__ == "__main__":
    unittest.main()

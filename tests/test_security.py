import base64
import unittest

from cryptography.exceptions import InvalidTag

from server.security import (
    CredentialCipher,
    PasswordService,
    generate_master_key,
    hash_token,
)


class CredentialCipherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cipher = CredentialCipher(generate_master_key())

    def test_round_trip_uses_random_nonces(self) -> None:
        first = self.cipher.encrypt("secret-value")
        second = self.cipher.encrypt("secret-value")
        self.assertNotEqual(first, second)
        self.assertEqual(self.cipher.decrypt(first), "secret-value")
        self.assertEqual(self.cipher.decrypt(second), "secret-value")

    def test_tampering_is_rejected(self) -> None:
        encoded = self.cipher.encrypt("secret-value")
        raw = bytearray(base64.urlsafe_b64decode(encoded.encode("ascii")))
        raw[-1] ^= 1
        tampered = base64.urlsafe_b64encode(raw).decode("ascii")
        with self.assertRaises(InvalidTag):
            self.cipher.decrypt(tampered)

    def test_invalid_key_size_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            CredentialCipher(base64.urlsafe_b64encode(b"too-short").decode())


class PasswordAndTokenTests(unittest.TestCase):
    def test_argon2_password_verification(self) -> None:
        service = PasswordService()
        password_hash = service.hash("correct horse battery staple")
        self.assertTrue(service.verify(password_hash, "correct horse battery staple"))
        self.assertFalse(service.verify(password_hash, "wrong"))

    def test_token_hash_is_deterministic_without_storing_plaintext(self) -> None:
        token = "opaque-session-token"
        digest = hash_token(token)
        self.assertEqual(digest, hash_token(token))
        self.assertNotIn(token, digest)
        self.assertEqual(len(digest), 64)


if __name__ == "__main__":
    unittest.main()

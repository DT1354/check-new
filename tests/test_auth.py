import base64
import unittest

from freshman_checkin.des import strEnc
from freshman_checkin.idm_auth import _GOTO_B64


class AuthenticationCompatibilityTests(unittest.TestCase):
    def test_des_implementation_matches_known_vector(self):
        self.assertEqual(strEnc("abc", "1234", "", ""), "1AD9EB7EE7984F1A")

    def test_idm_goto_is_embedded_public_configuration(self):
        decoded = base64.b64decode(_GOTO_B64).decode("utf-8")

        self.assertIn("idm.swu.edu.cn/am/oauth2/authorize", decoded)
        self.assertNotIn("SWU_USERNAME", decoded)
        self.assertNotIn("SWU_PASSWORD", decoded)


if __name__ == "__main__":
    unittest.main()

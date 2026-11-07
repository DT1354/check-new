import unittest
from unittest.mock import Mock, patch

from freshman_checkin.client import FreshmanCheckinClient, build_checkin_payload
from freshman_checkin.main import status_summary


class BuildPayloadTests(unittest.TestCase):
    def test_builds_payload_from_first_configured_location(self):
        status = {
            "DD_LIST": [
                {
                    "DDDM": "location-id",
                    "QDDD": "校园地点",
                    "JDZB": "106.123",
                    "WDZB": "29.456",
                }
            ]
        }

        self.assertEqual(
            build_checkin_payload(status),
            {
                "DDDM": "location-id",
                "QDDZ": "校园地点",
                "JDZB": 106.123,
                "WDZB": 29.456,
            },
        )

    def test_rejects_missing_location(self):
        with self.assertRaisesRegex(RuntimeError, "未返回可用打卡地点"):
            build_checkin_payload({"DD_LIST": []})


class StatusSummaryTests(unittest.TestCase):
    def test_summary_does_not_expose_personal_fields(self):
        data = {
            "CONFIG_INFO": {"IN_TIME": "1", "DKKSSJ": "21:00", "DKJSSJ": "23:30"},
            "QD_INFO": {"HAS_QD": "0", "XSBH": "sensitive"},
            "DD_LIST": [{"DDDM": "sensitive"}],
        }

        self.assertEqual(
            status_summary(data),
            {
                "already_checked_in": False,
                "in_time": True,
                "window": "21:00-23:30",
                "locations": 1,
            },
        )


class CheckinFlowTests(unittest.TestCase):
    def test_already_checked_in_never_submits(self):
        client = object.__new__(FreshmanCheckinClient)
        client.get_status = Mock(return_value={"QD_INFO": {"HAS_QD": "1"}})
        client.submit = Mock()

        result = client.checkin()

        self.assertTrue(result.already_checked_in)
        self.assertFalse(result.submitted)
        client.submit.assert_not_called()

    def test_out_of_time_never_submits_without_force(self):
        before = {
            "QD_INFO": {"HAS_QD": "0"},
            "CONFIG_INFO": {
                "IN_TIME": "0",
                "DKKSSJ": "21:00",
                "DKJSSJ": "23:30",
            },
        }
        client = object.__new__(FreshmanCheckinClient)
        client.get_status = Mock(return_value=before)
        client.submit = Mock()

        with self.assertRaisesRegex(RuntimeError, "当前不在打卡时间内"):
            client.checkin()

        client.submit.assert_not_called()

    def test_submit_is_verified_by_second_query(self):
        before = {
            "QD_INFO": {"HAS_QD": "0"},
            "CONFIG_INFO": {"IN_TIME": "1"},
            "DD_LIST": [
                {
                    "DDDM": "location-id",
                    "QDDD": "校园地点",
                    "JDZB": "106.123",
                    "WDZB": "29.456",
                }
            ],
        }
        after = {"QD_INFO": {"HAS_QD": "1"}}
        client = object.__new__(FreshmanCheckinClient)
        client.get_status = Mock(side_effect=[before, after])
        client.submit = Mock(return_value={"code": 0, "msg": "成功"})

        result = client.checkin()

        self.assertTrue(result.submitted)
        client.submit.assert_called_once_with(
            {
                "DDDM": "location-id",
                "QDDZ": "校园地点",
                "JDZB": 106.123,
                "WDZB": 29.456,
            }
        )


class BrowserCleanupTests(unittest.TestCase):
    def _client_with_profile(self, profile: Mock) -> FreshmanCheckinClient:
        client = FreshmanCheckinClient(Mock(), entry_url="https://example.invalid")
        client._external_profile = profile
        return client

    @patch("freshman_checkin.client.time.sleep")
    def test_profile_cleanup_retries_without_changing_result(self, sleep: Mock):
        profile = Mock()
        profile.cleanup.side_effect = [OSError(39, "Directory not empty"), None]
        client = self._client_with_profile(profile)

        client.close()

        self.assertEqual(profile.cleanup.call_count, 2)
        sleep.assert_called_once_with(0.2)
        self.assertIsNone(client._external_profile)

    @patch("freshman_checkin.client.log.warning")
    @patch("freshman_checkin.client.time.sleep")
    def test_persistent_cleanup_failure_is_logged_not_raised(
        self,
        sleep: Mock,
        warning: Mock,
    ):
        profile = Mock()
        profile.cleanup.side_effect = OSError(39, "Directory not empty")
        client = self._client_with_profile(profile)

        client.close()

        self.assertEqual(profile.cleanup.call_count, 5)
        self.assertEqual(sleep.call_count, 4)
        warning.assert_called_once()
        self.assertIsNone(client._external_profile)


if __name__ == "__main__":
    unittest.main()

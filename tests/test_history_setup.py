"""Validate hosted bucket retention without mutating its security settings."""

import unittest
from copy import deepcopy

from maimai_report.history.bundle import ArchiveError
from maimai_report.history.setup import verify_private_bucket

DEFAULT_MULTIPART_RULE = {
    "id": "Default Multipart Abort Rule",
    "enabled": True,
    "conditions": {},
    "abortMultipartUploadsTransition": {"condition": {"type": "Age", "maxAge": 604800}},
}


class BucketAPI:
    def __init__(self, rules):
        self.values = {
            "/r2/buckets/synthetic-history/domains/managed": {"enabled": False},
            "/r2/buckets/synthetic-history/domains/custom": {"domains": []},
            "/r2/buckets/synthetic-history/lifecycle": {"rules": rules},
        }
        self.calls = []

    def request(self, path):
        self.calls.append(path)
        return self.values[path]


class HistorySetupTests(unittest.TestCase):
    def test_provider_default_cleanup_preserves_completed_objects(self):
        api = BucketAPI([deepcopy(DEFAULT_MULTIPART_RULE)])
        before = deepcopy(api.values)
        verify_private_bucket(api, "synthetic-history")
        self.assertEqual(api.values, before)
        self.assertEqual(len(api.calls), 3)

    def test_empty_lifecycle_is_allowed(self):
        verify_private_bucket(BucketAPI([]), "synthetic-history")

    def test_completed_object_actions_rejected_even_with_default_rule_name(self):
        for action in ("deleteObjectsTransition", "storageClassTransitions", "unknownAction"):
            with self.subTest(action=action):
                rule = deepcopy(DEFAULT_MULTIPART_RULE)
                rule[action] = {"condition": {"type": "Age", "maxAge": 86400}}
                with self.assertRaises(ArchiveError):
                    verify_private_bucket(BucketAPI([rule]), "synthetic-history")

    def test_an_additional_expiration_rule_is_rejected(self):
        expiration = {
            "id": "Expire captures",
            "enabled": True,
            "conditions": {},
            "deleteObjectsTransition": {"condition": {"type": "Age", "maxAge": 86400}},
        }
        with self.assertRaises(ArchiveError):
            verify_private_bucket(
                BucketAPI([deepcopy(DEFAULT_MULTIPART_RULE), expiration]), "synthetic-history"
            )

    def test_disabled_rule_remains_unchanged(self):
        rule = {"enabled": False, "deleteObjectsTransition": {}}
        api = BucketAPI([rule])
        verify_private_bucket(api, "synthetic-history")
        self.assertEqual(api.values["/r2/buckets/synthetic-history/lifecycle"]["rules"], [rule])

    def test_malformed_lifecycle_fails_closed(self):
        for rules in (None, {}, [None], [{}], [{"enabled": "false"}]):
            with self.subTest(rules=rules), self.assertRaises(ArchiveError):
                verify_private_bucket(BucketAPI(rules), "synthetic-history")
        for age in (None, True, -1, 0, "604800"):
            rule = deepcopy(DEFAULT_MULTIPART_RULE)
            rule["abortMultipartUploadsTransition"]["condition"]["maxAge"] = age
            with self.subTest(age=age), self.assertRaises(ArchiveError):
                verify_private_bucket(BucketAPI([rule]), "synthetic-history")

    def test_public_access_is_still_rejected(self):
        for suffix, value in (
            ("managed", {"enabled": True}),
            ("managed", {}),
            ("custom", {"domains": [{"domain": "synthetic.example"}]}),
            ("custom", {}),
        ):
            api = BucketAPI([deepcopy(DEFAULT_MULTIPART_RULE)])
            api.values[f"/r2/buckets/synthetic-history/domains/{suffix}"] = value
            with self.subTest(suffix=suffix, value=value), self.assertRaises(ArchiveError):
                verify_private_bucket(api, "synthetic-history")

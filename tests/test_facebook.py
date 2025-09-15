import unittest
from connectors.facebook_connector import FacebookConnector


class TestFacebookConnector(unittest.TestCase):
    def test_dry_run(self):
        c = FacebookConnector(dry_run=True)
        res = c.post("Test message")
        self.assertEqual(res.get("status"), "dry_run")
        self.assertEqual(res.get("message"), "Test message")


if __name__ == "__main__":
    unittest.main()

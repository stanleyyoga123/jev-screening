import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.application import create_app


class ApplicationTests(unittest.TestCase):
    def test_documentation_routes_follow_dev_environment(self) -> None:
        for dev, expected_status in [("true", 200), ("false", 404)]:
            with self.subTest(dev=dev), patch.dict("os.environ", {"DEV": dev}):
                with TestClient(create_app()) as client:
                    for path in ("/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"):
                        self.assertEqual(client.get(path).status_code, expected_status, path)
                    self.assertEqual(client.get("/api/health").json(), {"status": "ok"})

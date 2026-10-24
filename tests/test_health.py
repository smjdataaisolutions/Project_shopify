import unittest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from sqlalchemy.exc import OperationalError

from app.main import health_check, readiness_check


class HealthEndpointTests(unittest.TestCase):
    def test_liveness_does_not_require_database(self):
        self.assertEqual(health_check(), {"status": "ok"})

    @patch("app.main.engine")
    def test_readiness_executes_database_probe(self, engine):
        connection = MagicMock()
        engine.connect.return_value.__enter__.return_value = connection

        self.assertEqual(readiness_check(), {"status": "ready"})
        connection.execute.assert_called_once()

    @patch("app.main.engine")
    def test_readiness_hides_database_error_details(self, engine):
        engine.connect.side_effect = OperationalError(
            "SELECT 1", {}, Exception("credential details")
        )

        with self.assertRaises(HTTPException) as context:
            readiness_check()

        self.assertEqual(context.exception.status_code, 503)
        self.assertEqual(context.exception.detail, "Database is unavailable.")


if __name__ == "__main__":
    unittest.main()

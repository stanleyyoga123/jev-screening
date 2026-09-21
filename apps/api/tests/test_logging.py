import io
import logging
import unittest
from contextlib import redirect_stdout

from fastapi.testclient import TestClient

from api.application import create_app
from core.logging import configure_logging, log_operation, request_id


class LoggingTests(unittest.TestCase):
    def test_request_logging_and_correlation(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            app = create_app()
            with TestClient(app) as client:
                response = client.get('/api/health?private=SECRET_QUERY', headers={
                    'Authorization': 'Bearer SECRET_KEY', 'X-Request-ID': 'UNTRUSTED_ID',
                })
                missing = client.get('/SECRET_PATH')
        logs = output.getvalue()
        self.assertEqual(response.status_code, 200)
        self.assertIn('request_id=' + response.headers['X-Request-ID'], logs)
        self.assertNotEqual(response.headers['X-Request-ID'], missing.headers['X-Request-ID'])
        self.assertIn('route=/api/health status=200 duration_ms=', logs)
        self.assertIn(' | INFO | RequestLoggingMiddleware | request_completed', logs)
        self.assertIn(' | INFO | Application | application_started', logs)
        self.assertIn('route=<unmatched> status=404', logs)
        self.assertIn('application_started', logs)
        self.assertIn('application_stopped', logs)
        for secret in ('SECRET_QUERY', 'SECRET_KEY', 'SECRET_PATH', 'UNTRUSTED_ID'):
            self.assertNotIn(secret, logs)
        self.assertEqual(request_id.get(), '-')

    def test_unhandled_exception_has_safe_stack(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            app = create_app()

            @app.get('/failure')
            def failure():
                raise RuntimeError('SECRET_EXCEPTION_CONTENT')

            with TestClient(app, raise_server_exceptions=False) as client:
                response = client.get('/failure')
        logs = output.getvalue()
        self.assertEqual(response.status_code, 500)
        self.assertIn('request_failed', logs)
        self.assertIn('RuntimeError', logs)
        self.assertIn('in failure', logs)
        self.assertNotIn('SECRET_EXCEPTION_CONTENT', logs)
        self.assertEqual(request_id.get(), '-')

    def test_operations_preserve_errors_without_logging_content(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            configure_logging('INFO')
            logger = logging.getLogger('test.operation')
            with log_operation(logger, 'test.success'):
                pass
            error = ValueError('SECRET_PROVIDER_RESPONSE')
            with self.assertRaises(ValueError) as raised:
                with log_operation(logger, 'test.failure'):
                    raise error
        self.assertIs(raised.exception, error)
        self.assertIn('operation_completed operation=test.success', output.getvalue())
        self.assertIn('operation_failed operation=test.failure error_type=ValueError', output.getvalue())
        self.assertNotIn('SECRET_PROVIDER_RESPONSE', output.getvalue())

    def test_setup_is_idempotent_and_honors_level(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            configure_logging('WARNING')
            configure_logging('WARNING')
            logger = logging.getLogger('test.setup')
            logger.info('hidden_info')
            logger.warning('visible_warning')
            logging.getLogger('uvicorn.access').info('SECRET_RAW_URL')
        self.assertEqual(output.getvalue().count('visible_warning'), 1)
        self.assertNotIn('hidden_info', output.getvalue())
        self.assertNotIn('SECRET_RAW_URL', output.getvalue())
        self.assertEqual(len(logging.getLogger().handlers), 1)

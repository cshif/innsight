"""Tests for application lifecycle events."""

from fastapi.testclient import TestClient

from innsight.app import create_app


class TestLifecycleEvents:
    """Test application startup and shutdown events."""

    def test_startup_event_logs_application_started(self, capsys):
        """Verify startup event logs 'Application started successfully'."""
        app = create_app()

        with TestClient(app):
            pass

        captured = capsys.readouterr()
        assert "Application started successfully" in captured.out

    def test_shutdown_event_logs_application_shutting_down(self, capsys):
        """Verify shutdown event logs 'Application shutting down'."""
        app = create_app()

        with TestClient(app):
            pass

        captured = capsys.readouterr()
        assert "Application shutting down" in captured.out
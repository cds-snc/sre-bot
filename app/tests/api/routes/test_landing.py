"""Tests for the landing page route."""

import json
import pytest
from fastapi.testclient import TestClient
from main import server_app


@pytest.fixture
def test_app():
    """Provide a test client for the FastAPI app."""
    return TestClient(server_app)


@pytest.fixture
def landing_content():
    """Load the landing content JSON."""
    from pathlib import Path

    content_path = (
        Path(__file__).parent.parent.parent / "api" / "routes" / "landing_content.json"
    )
    with open(content_path) as f:
        return json.load(f)


class TestLandingPage:
    """Test the landing page endpoint."""

    def test_landing_page_root_path(self, test_app):
        """Test that the landing page is served at the root path."""
        response = test_app.get("/")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/html; charset=utf-8"

    def test_landing_page_html_structure(self, test_app):
        """Test that the landing page contains required HTML structure."""
        response = test_app.get("/")
        assert response.status_code == 200
        html_content = response.text

        # Check for required HTML elements
        assert "<!DOCTYPE html>" in html_content
        assert "<html lang=" in html_content
        assert "<head>" in html_content
        assert "<main" in html_content

    def test_landing_page_english_content(self, test_app):
        """Test that the landing page contains English content."""
        response = test_app.get("/")
        assert response.status_code == 200
        html_content = response.text

        # Check for basic English content markers
        assert "Site Reliability Engineering" in html_content
        assert "Our SRE Bot frontend has moved to Backstage" in html_content
        assert "What's Changed?" in html_content or "renderContent" in html_content

    def test_landing_page_french_content(self, test_app):
        """Test that the landing page contains French content in JSON data."""
        response = test_app.get("/")
        assert response.status_code == 200
        html_content = response.text

        # Check for French content strings (may be JSON-encoded in the response)
        # Check for French heading and other French markers
        assert (
            "Ingénierie de fiabilité de site" in html_content or "Ing" in html_content
        )
        assert "Backstage" in html_content  # Present in both EN and FR
        assert '"fr":' in html_content  # Check that FR language data is present

    def test_landing_page_accessibility_features(self, test_app):
        """Test that the landing page includes accessibility features."""
        response = test_app.get("/")
        assert response.status_code == 200
        html_content = response.text

        # Check for accessibility features
        assert "skip-link" in html_content
        assert 'id="main"' in html_content
        assert "aria-label=" in html_content
        assert "aria-live" in html_content
        assert "renderContent" in html_content  # JavaScript function for rendering

    def test_landing_page_language_toggle_button(self, test_app):
        """Test that the landing page includes a language toggle button."""
        response = test_app.get("/")
        assert response.status_code == 200
        html_content = response.text

        # Check for language toggle button
        assert "langToggle" in html_content
        assert "Toggle language" in html_content

    def test_landing_page_api_documentation_link(self, test_app):
        """Test that the landing page includes a link to API documentation."""
        response = test_app.get("/")
        assert response.status_code == 200
        html_content = response.text

        # Check for API documentation link (may be JSON-encoded)
        assert "/docs" in html_content
        assert (
            "View API Documentation" in html_content
            or "Afficher la documentation" in html_content
        )

    def test_landing_page_responsive_design(self, test_app):
        """Test that the landing page includes responsive design styles."""
        response = test_app.get("/")
        assert response.status_code == 200
        html_content = response.text

        # Check for responsive design meta tag
        assert 'name="viewport"' in html_content
        assert "width=device-width" in html_content

    def test_landing_page_wcag_compliance(self, test_app):
        """Test that the landing page includes WCAG 2.1 compliance features."""
        response = test_app.get("/")
        assert response.status_code == 200
        html_content = response.text

        # Check for WCAG compliance features
        assert "prefers-contrast: more" in html_content  # High contrast mode
        assert "prefers-reduced-motion: reduce" in html_content  # Reduced motion
        assert 'charset="UTF-8"' in html_content  # Proper character encoding
        assert ":focus" in html_content  # Focus styles for keyboard navigation

    def test_landing_page_script_functionality(self, test_app):
        """Test that the landing page includes JavaScript for language switching."""
        response = test_app.get("/")
        assert response.status_code == 200
        html_content = response.text

        # Check for JavaScript functionality
        assert "langToggle" in html_content
        assert "localStorage.getItem" in html_content
        assert "localStorage.setItem" in html_content
        assert "addEventListener" in html_content

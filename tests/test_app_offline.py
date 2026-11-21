"""
Offline integration and endpoint tests for the Flask application (app.py).
All tests execute using Flask's test_client with synthetic in-memory streams.
No external network calls, real API keys, or live servers are used.
"""

import io
import os
import unittest
from unittest.mock import patch
import zipfile

from app import TEMP_UPLOAD_DIR, TOOLS, app, parse_chat


class TestAppOffline(unittest.TestCase):
    """Test suite for Flask routes, parsers, and API stats offline."""

    def setUp(self):
        """Configure test client in testing mode and track pre-existing temp files."""
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        self.client = app.test_client()
        self.initial_temp_files = set(os.listdir(TEMP_UPLOAD_DIR)) if os.path.exists(TEMP_UPLOAD_DIR) else set()

    def tearDown(self):
        """Clean up any temporary uploaded files created during the test run."""
        if os.path.exists(TEMP_UPLOAD_DIR):
            current_files = set(os.listdir(TEMP_UPLOAD_DIR))
            new_files = current_files - self.initial_temp_files
            for filename in new_files:
                file_path = os.path.join(TEMP_UPLOAD_DIR, filename)
                try:
                    os.remove(file_path)
                except OSError:
                    pass

    def test_tool_registry_integrity(self):
        """Verifies that the TOOL registry contains required tools and valid schemas."""
        required_tools = ["summarize", "action-items", "statistics", "sentiment", "search", "export"]
        for tool_name in required_tools:
            self.assertIn(tool_name, TOOLS, f"Tool '{tool_name}' missing from TOOLS registry")
            tool_meta = TOOLS[tool_name]
            self.assertIn("title", tool_meta)
            self.assertIn("prompt", tool_meta)
            self.assertIn("accepts", tool_meta)

    def test_get_tool_pages(self):
        """Verifies that GET requests to valid tool pages return 200 OK."""
        for tool_name in ["summarize", "statistics"]:
            response = self.client.get(f"/tool/{tool_name}")
            self.assertEqual(response.status_code, 200, f"Failed loading /tool/{tool_name}")

    def test_unknown_tool_returns_400(self):
        """Verifies that requesting an unregistered tool returns 400."""
        response = self.client.post("/api/tool/nonexistent_tool_xyz/stats")
        self.assertEqual(response.status_code, 400)
        json_data = response.get_json()
        self.assertIn("error", json_data)

    def test_parse_chat_function_with_valid_text(self):
        """Verifies the core parse_chat function directly with synthetic chat text."""
        raw_chat = (
            "14/08/23, 10:20 - Alice: Hey everyone, welcome!\n"
            "14/08/23, 10:22 - Bob: Hey Alice! Check out https://example.com :)\n"
            "14/08/23, 10:25 - Alice: Great link Bob!\n"
        )
        formatted_chat, stats, time_series, hourly, media, emojis, links, advanced = parse_chat(raw_chat)

        self.assertTrue(len(formatted_chat) > 0)
        self.assertEqual(advanced["kpis"]["total_messages"], 3)
        self.assertEqual(stats.get("Alice"), 2)
        self.assertEqual(stats.get("Bob"), 1)
        self.assertIn("https://example.com", links)

    def test_api_stats_missing_file_or_text(self):
        """Verifies /api/tool/<tool>/stats rejects requests with no body."""
        response = self.client.post("/api/tool/statistics/stats", data={})
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.get_json())

    def test_api_stats_garbage_file(self):
        """Verifies that uploading a non-chat file returns an error cleanly."""
        data = {"file": (io.BytesIO(b"garbage content without any date headers"), "garbage.txt")}
        response = self.client.post(
            "/api/tool/statistics/stats",
            data=data,
            content_type="multipart/form-data"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.get_json())

    def test_api_stats_valid_chat_file(self):
        """Verifies that uploading a valid synthetic chat returns stats with status 200."""
        chat_content = (
            "14/08/23, 10:20 - User1: Good morning!\n"
            "14/08/23, 10:25 - User2: Good morning User1.\n"
        )
        data = {"file": (io.BytesIO(chat_content.encode("utf-8")), "chat.txt")}
        response = self.client.post(
            "/api/tool/statistics/stats",
            data=data,
            content_type="multipart/form-data"
        )
        self.assertEqual(response.status_code, 200)
        json_data = response.get_json()
        self.assertIn("stats", json_data)
        self.assertEqual(sum(json_data["stats"].values()), 2)
        self.assertEqual(json_data["advanced_stats"]["kpis"]["total_messages"], 2)

    def test_api_stats_valid_zip_file(self):
        """Verifies zip file extraction and stats parsing in memory."""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            chat_data = (
                "15/09/23, 14:00 - DevA: Deploying release v1.0\n"
                "15/09/23, 14:05 - DevB: Release confirmed.\n"
            )
            zf.writestr("_chat.txt", chat_data)
        zip_buffer.seek(0)

        data = {"file": (zip_buffer, "chat_export.zip")}
        response = self.client.post(
            "/api/tool/summarize/stats",
            data=data,
            content_type="multipart/form-data"
        )
        self.assertEqual(response.status_code, 200)
        json_data = response.get_json()
        self.assertIn("stats", json_data)
        self.assertEqual(sum(json_data["stats"].values()), 2)
        self.assertEqual(json_data["advanced_stats"]["kpis"]["total_messages"], 2)

    @patch("app.call_gemini_with_retry")
    def test_api_tool_mocked_summary(self, mock_gemini_call):
        """
        Verifies that /api/tool/summarize processes raw_text input and handles
        the model response cleanly when AI generation is mocked offline.
        """
        mock_gemini_call.return_value = (
            "## Summary\n- Topic: Project deployment\n- Action Item: Complete documentation",
            None,
            "mocked_gemini"
        )

        synthetic_chat = (
            "16/10/23, 09:00 - Alice: We need to finalize the CI pipeline.\n"
            "16/10/23, 09:05 - Bob: I will add the GitHub Actions workflow.\n"
        )
        response = self.client.post(
            "/api/tool/summarize",
            data={"raw_text": synthetic_chat}
        )

        self.assertEqual(response.status_code, 200)
        json_data = response.get_json()
        self.assertIn("response", json_data)
        self.assertIn("Project deployment", json_data["response"])


if __name__ == "__main__":
    unittest.main()

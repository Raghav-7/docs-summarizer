"""
Unit tests for WhatsApp chat parsing logic in summarize.py.
All tests run 100% offline with synthetic in-memory/temp data.
"""

import os
import tempfile
import unittest

from summarize import parse_whatsapp_chat


class TestWhatsAppParser(unittest.TestCase):
    """Deterministic offline test cases for parse_whatsapp_chat."""

    def test_parse_android_format(self):
        """Verifies parsing of standard Android exported chat lines."""
        content = (
            "14/08/23, 10:20 - Alice: Hey team, welcome to the project!\n"
            "14/08/23, 10:21 - Bob: Thanks Alice! Happy to help.\n"
        )
        with tempfile.NamedTemporaryFile("w+", encoding="utf-8", delete=False) as tf:
            tf.write(content)
            temp_path = tf.name

        try:
            messages = parse_whatsapp_chat(temp_path)
            self.assertIsNotNone(messages)
            self.assertEqual(len(messages), 2)

            self.assertEqual(messages[0]["sender"], "Alice")
            self.assertEqual(messages[0]["message"], "Hey team, welcome to the project!")
            self.assertEqual(messages[0]["date"], "14/08/23")
            self.assertEqual(messages[0]["time"], "10:20")

            self.assertEqual(messages[1]["sender"], "Bob")
            self.assertEqual(messages[1]["message"], "Thanks Alice! Happy to help.")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_parse_ios_format(self):
        """Verifies parsing of standard iOS exported chat lines with square brackets."""
        content = (
            "[14/08/23, 10:26:15] Charlie: I will join in 5 minutes.\n"
            "[14/08/23, 10:30:00] Alice: Sounds great, see you soon.\n"
        )
        with tempfile.NamedTemporaryFile("w+", encoding="utf-8", delete=False) as tf:
            tf.write(content)
            temp_path = tf.name

        try:
            messages = parse_whatsapp_chat(temp_path)
            self.assertIsNotNone(messages)
            self.assertEqual(len(messages), 2)
            self.assertEqual(messages[0]["sender"], "Charlie")
            self.assertEqual(messages[0]["message"], "I will join in 5 minutes.")
            self.assertEqual(messages[1]["sender"], "Alice")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_empty_file_handling(self):
        """Verifies that an empty file returns an empty list without error."""
        with tempfile.NamedTemporaryFile("w+", encoding="utf-8", delete=False) as tf:
            tf.write("")
            temp_path = tf.name

        try:
            messages = parse_whatsapp_chat(temp_path)
            self.assertIsNotNone(messages)
            self.assertEqual(len(messages), 0)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_missing_file_handling(self):
        """Verifies that a non-existent file returns None gracefully."""
        non_existent = os.path.join(tempfile.gettempdir(), "non_existent_chat_file_xyz.txt")
        if os.path.exists(non_existent):
            os.remove(non_existent)
        result = parse_whatsapp_chat(non_existent)
        self.assertIsNone(result)

    def test_corrupt_or_non_chat_lines_ignored(self):
        """Verifies that random non-chat lines and notifications are filtered out."""
        content = (
            "Random preamble line that is not a chat\n"
            "14/08/23, 10:20 - Alice: Real message\n"
            "End of exported file message\n"
        )
        with tempfile.NamedTemporaryFile("w+", encoding="utf-8", delete=False) as tf:
            tf.write(content)
            temp_path = tf.name

        try:
            messages = parse_whatsapp_chat(temp_path)
            self.assertEqual(len(messages), 1)
            self.assertEqual(messages[0]["sender"], "Alice")
            self.assertEqual(messages[0]["message"], "Real message")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


if __name__ == "__main__":
    unittest.main()


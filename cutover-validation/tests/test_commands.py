"""Tests for device supported-command validation."""

import unittest

from utils.commands import _format_batched_item, validate_command


class ValidateCommandTests(unittest.TestCase):
    def test_matches_an_exact_literal_command(self):
        self.assertTrue(validate_command("show system", ["show system"]))

    def test_trims_command_and_supported_command_boundaries(self):
        self.assertTrue(validate_command("  show system  ", ["  show system  "]))

    def test_rejects_a_partial_literal_command(self):
        self.assertFalse(validate_command("show cellular", ["show cellular status"]))

    def test_is_case_sensitive(self):
        self.assertFalse(validate_command("show system", ["Show System"]))

    def test_preserves_internal_spacing(self):
        self.assertFalse(validate_command("show  system", ["show system"]))

    def test_matches_a_single_word_template_placeholder(self):
        self.assertTrue(
            validate_command("show ap AP-01", ["show ap {{ap_name}}"])
        )

    def test_rejects_multiple_words_for_a_template_placeholder(self):
        self.assertFalse(
            validate_command(
                "show cellular status detail", ["show cellular {{option}}"]
            )
        )

    def test_matches_multiple_template_placeholders(self):
        self.assertTrue(
            validate_command(
                "show client 00:11:22:33:44:55 vlan 101",
                ["show client {{mac}} vlan {{vlan}}"],
            )
        )

    def test_treats_regex_metacharacters_in_literals_as_literal(self):
        supported = "show ap [detail].(all)?"

        self.assertTrue(validate_command(supported, [supported]))
        self.assertFalse(validate_command("show ap detailXall", [supported]))


class FormatBatchedItemTests(unittest.TestCase):
    def test_marks_parse_error_output_as_failed(self):
        command_output = {"command": "show cellular error", "output": "% Parse error."}

        result = _format_batched_item(command_output)

        self.assertEqual(result.status, "FAILED")
        self.assertEqual(result.error, "Invalid command: API returned % Parse error.")
        self.assertEqual(result.response, "% Parse error.")
        self.assertIs(result.raw_response, command_output)

    def test_treats_case_and_whitespace_variants_as_parse_error(self):
        command_output = {
            "command": "show cellular error",
            "output": "  % parse error.  ",
        }

        result = _format_batched_item(command_output)

        self.assertEqual(result.status, "FAILED")
        self.assertEqual(result.error, "Invalid command: API returned % Parse error.")

    def test_keeps_other_output_completed(self):
        command_output = {
            "command": "show cellular error",
            "output": "cellular status:\nall good",
        }

        result = _format_batched_item(command_output)

        self.assertEqual(result.status, "COMPLETED")
        self.assertEqual(result.response, "cellular status:\nall good")


if __name__ == "__main__":
    unittest.main()

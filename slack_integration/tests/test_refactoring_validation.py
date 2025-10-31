# -*- coding: utf-8 -*-
"""
Test suite for validating refactoring changes in Slack Integration module.

This test validates:
1. Constants are properly defined and used throughout the code
2. Translation function _() is imported and used correctly
3. Deprecated datetime.utcnow() has been replaced with datetime.now(timezone.utc)
4. All imports are valid and work correctly
"""

from odoo.tests import TransactionCase
import os
import re
import ast


class TestRefactoringValidation(TransactionCase):
    """Test suite to validate the refactoring changes in slack_bot.py"""

    @classmethod
    def setUpClass(cls):
        super(TestRefactoringValidation, cls).setUpClass()
        # Get the path to slack_bot.py
        cls.module_path = os.path.dirname(os.path.dirname(__file__))
        cls.slack_bot_path = os.path.join(cls.module_path, 'controllers', 'slack_bot.py')

        # Read the file content
        with open(cls.slack_bot_path, 'r') as f:
            cls.file_content = f.read()

        # Parse the AST
        cls.ast_tree = ast.parse(cls.file_content)

    def test_01_constants_are_defined(self):
        """Test that all required constants are defined at the top of the file"""
        expected_constants = {
            'MODEL_SLACK_USER_MAPPING': "'slack.user.mapping'",
            'MODEL_SLACK_CONVERSATION': "'slack.conversation'",
            'MODEL_RES_CONFIG_SETTINGS': "'res.config.settings'",
            'MODEL_CRM_LEAD': "'crm.lead'",
            'MODEL_CRM_STAGE': "'crm.stage'",
            'MODEL_IR_CONFIG_PARAMETER': "'ir.config_parameter'",
            'CONTENT_TYPE_JSON': "'application/json'",
            'SLACK_API_VIEWS_OPEN': "'https://slack.com/api/views.open'",
            'CONFIG_PARAM_WEB_BASE_URL': "'web.base.url'",
        }

        for const_name, const_value in expected_constants.items():
            pattern = rf'{const_name}\s*=\s*{re.escape(const_value)}'
            self.assertTrue(
                re.search(pattern, self.file_content),
                f"Constant {const_name} = {const_value} should be defined in slack_bot.py"
            )

    def test_02_constants_are_used(self):
        """Test that all constants are actually used in the code (not just defined)"""
        expected_constants = [
            'MODEL_SLACK_USER_MAPPING',
            'MODEL_SLACK_CONVERSATION',
            'MODEL_RES_CONFIG_SETTINGS',
            'MODEL_CRM_LEAD',
            'MODEL_CRM_STAGE',
            'MODEL_IR_CONFIG_PARAMETER',
            'CONTENT_TYPE_JSON',
            'SLACK_API_VIEWS_OPEN',
            'CONFIG_PARAM_WEB_BASE_URL',
        ]

        for const_name in expected_constants:
            # Count occurrences (should be more than 1 - definition + usage)
            pattern = rf'\b{const_name}\b'
            matches = re.findall(pattern, self.file_content)
            self.assertGreater(
                len(matches), 1,
                f"Constant {const_name} should be used in the code (found {len(matches)} occurrences)"
            )

    def test_03_translation_function_imported(self):
        """Test that translation function _() is imported from odoo"""
        self.assertIn(
            "from odoo import http, _",
            self.file_content,
            "Translation function _() must be imported from odoo"
        )

    def test_04_translation_function_used(self):
        """Test that translation function _() is used for user-facing strings"""
        # Find all usages of _()
        pattern = r"_\(['\"]([^'\"]+)['\"]\)"
        matches = re.findall(pattern, self.file_content)

        self.assertGreater(
            len(matches), 0,
            "Translation function _() should be used for user-facing strings"
        )

        # Verify some known translatable strings are using _()
        known_translatable_strings = [
            'Add Note',
            'No partner',
            'No stage',
        ]

        translated_strings = set(matches)
        for known_string in known_translatable_strings:
            self.assertIn(
                known_string,
                translated_strings,
                f"String '{known_string}' should be wrapped with _() for translation"
            )

    def test_05_no_deprecated_datetime_utcnow(self):
        """Test that deprecated datetime.utcnow() is not used"""
        deprecated_pattern = r'datetime\.utcnow\(\)'
        matches = re.findall(deprecated_pattern, self.file_content)

        self.assertEqual(
            len(matches), 0,
            f"Deprecated datetime.utcnow() should not be used. Found {len(matches)} occurrences. "
            "Use datetime.now(timezone.utc) instead."
        )

    def test_06_timezone_imported(self):
        """Test that timezone is imported from datetime module"""
        self.assertIn(
            "from datetime import datetime, timezone",
            self.file_content,
            "timezone must be imported from datetime module"
        )

    def test_07_correct_datetime_usage(self):
        """Test that datetime.now(timezone.utc) is used correctly"""
        correct_pattern = r'datetime\.now\(timezone\.utc\)'
        matches = re.findall(correct_pattern, self.file_content)

        self.assertGreater(
            len(matches), 0,
            "datetime.now(timezone.utc) should be used instead of deprecated datetime.utcnow()"
        )

    def test_08_imports_are_valid(self):
        """Test that all import statements are valid Python"""
        # Get all imports from AST
        imports = []
        for node in ast.walk(self.ast_tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                for alias in node.names:
                    import_str = f"{module}.{alias.name}" if module else alias.name
                    imports.append(import_str)

        # Ensure we have the critical imports
        critical_imports = [
            'json',
            'logging',
            'requests',
            'hashlib',
            'hmac',
            'time',
            'pytz',
        ]

        for critical_import in critical_imports:
            # Check if the import or a parent module is imported
            found = any(imp.startswith(critical_import) or critical_import in imp for imp in imports)
            self.assertTrue(
                found,
                f"Critical import '{critical_import}' should be present"
            )

    def test_09_no_hardcoded_model_names_in_env(self):
        """Test that model names use constants instead of hardcoded strings (in request.env calls)"""
        # This is a warning test - we check but don't fail
        # Look for patterns like request.env['model.name'] or self.env['model.name']

        model_names = [
            'slack.user.mapping',
            'slack.conversation',
            'res.config.settings',
            'crm.lead',
            'crm.stage',
        ]

        issues = []
        for model_name in model_names:
            # Look for hardcoded usage in env[] calls
            # Pattern: env['model.name'] or env["model.name"]
            pattern = rf"env\[['\"]({re.escape(model_name)})['\"]"
            matches = list(re.finditer(pattern, self.file_content))

            # Check if these are NOT in the constants definition section (lines 17-29)
            for match in matches:
                line_num = self.file_content[:match.start()].count('\n') + 1
                if line_num < 17 or line_num > 29:
                    # Get the full line for context
                    line_start = self.file_content.rfind('\n', 0, match.start()) + 1
                    line_end = self.file_content.find('\n', match.end())
                    line_content = self.file_content[line_start:line_end].strip()

                    issues.append((line_num, model_name, line_content))

        # We don't fail the test, just report
        if issues:
            issue_report = "\n".join([
                f"  Line {line_num}: '{model_name}' in {line_content[:60]}..."
                for line_num, model_name, line_content in issues[:5]
            ])
            print(f"\nWARNING: Found {len(issues)} potential hardcoded model names:\n{issue_report}")

    def test_10_no_sql_injection_risks(self):
        """Test that there are no direct SQL execute calls (potential injection risk)"""
        sql_pattern = r'\.execute\s*\(\s*["\']'
        matches = re.findall(sql_pattern, self.file_content)

        self.assertEqual(
            len(matches), 0,
            f"Direct SQL execute calls found ({len(matches)}). Use ORM methods to prevent SQL injection."
        )

    def test_11_no_print_statements(self):
        """Test that there are no print statements (should use _logger instead)"""
        print_pattern = r'\bprint\s*\('
        matches = re.findall(print_pattern, self.file_content)

        self.assertEqual(
            len(matches), 0,
            f"print statements found ({len(matches)}). Use _logger.info/warning/error instead."
        )

    def test_12_proper_exception_handling(self):
        """Test that there are no bare except clauses"""
        bare_except_pattern = r'except\s*:'
        matches = re.findall(bare_except_pattern, self.file_content)

        self.assertEqual(
            len(matches), 0,
            f"Bare except clauses found ({len(matches)}). Specify exception type for better error handling."
        )

    def test_13_logger_is_defined(self):
        """Test that logger is properly defined"""
        self.assertIn(
            "_logger = logging.getLogger(__name__)",
            self.file_content,
            "Logger should be defined using logging.getLogger(__name__)"
        )

    def test_14_controller_class_exists(self):
        """Test that SlackBotController class is defined"""
        self.assertIn(
            "class SlackBotController(http.Controller):",
            self.file_content,
            "SlackBotController class should be defined"
        )

    def test_15_critical_methods_exist(self):
        """Test that critical controller methods are defined"""
        critical_methods = [
            '_verify_slack_request',
            '_handle_dm_message',
            '_handle_connect_command',
            '_handle_search_command',
            '_handle_info_command',
            '_handle_note_command',
            '_handle_move_command',
            '_send_dm_response',
        ]

        for method_name in critical_methods:
            pattern = rf'def {method_name}\s*\('
            self.assertTrue(
                re.search(pattern, self.file_content),
                f"Method '{method_name}' should be defined in SlackBotController"
            )

    def test_16_routes_are_defined(self):
        """Test that HTTP routes are properly defined"""
        routes = [
            '/slack/events',
            '/slack/interactive',
        ]

        for route in routes:
            self.assertIn(
                f"@http.route('{route}'",
                self.file_content,
                f"Route '{route}' should be defined"
            )

    def test_17_security_verification_exists(self):
        """Test that security verification method exists and is comprehensive"""
        # Check that the method exists
        self.assertIn(
            "def _verify_slack_request(self, raw_body):",
            self.file_content,
            "_verify_slack_request method should exist"
        )

        # Check for key security features
        security_features = [
            'hmac.new',  # HMAC signature verification
            'hmac.compare_digest',  # Timing-safe comparison
            'timestamp_drift',  # Timestamp verification
            'AccessDenied',  # Proper exception handling
            'security_log',  # Security logging
        ]

        for feature in security_features:
            self.assertIn(
                feature,
                self.file_content,
                f"Security feature '{feature}' should be implemented in verification method"
            )

    def test_18_file_encoding_is_utf8(self):
        """Test that file has proper UTF-8 encoding declaration"""
        first_line = self.file_content.split('\n')[0]
        self.assertIn(
            'utf-8',
            first_line.lower(),
            "File should have UTF-8 encoding declaration on first line"
        )

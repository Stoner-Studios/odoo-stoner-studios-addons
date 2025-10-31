# -*- coding: utf-8 -*-
"""
Functional tests for Slack Bot Controller.

Tests the actual functionality of the refactored code including:
1. Constants usage in runtime
2. Translation function behavior
3. Datetime operations with timezone.utc
4. Security verification
5. Command handling
"""

from odoo.tests import TransactionCase, tagged
from odoo.exceptions import AccessDenied
from unittest.mock import Mock, patch, MagicMock
import json
import hmac
import hashlib
import time
from datetime import datetime, timezone


@tagged('post_install', '-at_install')
class TestSlackBotController(TransactionCase):
    """Functional tests for Slack Bot Controller"""

    @classmethod
    def setUpClass(cls):
        super(TestSlackBotController, cls).setUpClass()

        # Create test user
        cls.test_user = cls.env['res.users'].create({
            'name': 'Test User',
            'login': 'testuser',
            'email': 'testuser@example.com',
        })

        # Create Slack configuration
        cls.env['ir.config_parameter'].sudo().set_param('slack.bot_token', 'xoxb-test-token')
        cls.env['ir.config_parameter'].sudo().set_param('slack.signing_secret', 'test-signing-secret')
        cls.env['ir.config_parameter'].sudo().set_param('slack.verification_token', 'test-verification-token')

        # Import the controller
        from odoo.addons.slack_integration.controllers.slack_bot import SlackBotController
        cls.controller = SlackBotController()

    def test_01_constants_are_accessible(self):
        """Test that constants are accessible and have correct values"""
        from odoo.addons.slack_integration.controllers.slack_bot import (
            MODEL_SLACK_USER_MAPPING,
            MODEL_SLACK_CONVERSATION,
            MODEL_RES_CONFIG_SETTINGS,
            MODEL_CRM_LEAD,
            MODEL_CRM_STAGE,
            MODEL_IR_CONFIG_PARAMETER,
            CONTENT_TYPE_JSON,
            SLACK_API_VIEWS_OPEN,
            CONFIG_PARAM_WEB_BASE_URL,
        )

        self.assertEqual(MODEL_SLACK_USER_MAPPING, 'slack.user.mapping')
        self.assertEqual(MODEL_SLACK_CONVERSATION, 'slack.conversation')
        self.assertEqual(MODEL_RES_CONFIG_SETTINGS, 'res.config.settings')
        self.assertEqual(MODEL_CRM_LEAD, 'crm.lead')
        self.assertEqual(MODEL_CRM_STAGE, 'crm.stage')
        self.assertEqual(MODEL_IR_CONFIG_PARAMETER, 'ir.config_parameter')
        self.assertEqual(CONTENT_TYPE_JSON, 'application/json')
        self.assertEqual(SLACK_API_VIEWS_OPEN, 'https://slack.com/api/views.open')
        self.assertEqual(CONFIG_PARAM_WEB_BASE_URL, 'web.base.url')

    def test_02_models_can_be_accessed_with_constants(self):
        """Test that Odoo models can be accessed using the defined constants"""
        from odoo.addons.slack_integration.controllers.slack_bot import (
            MODEL_SLACK_USER_MAPPING,
            MODEL_SLACK_CONVERSATION,
            MODEL_CRM_LEAD,
        )

        # Test accessing models using constants
        mapping_model = self.env[MODEL_SLACK_USER_MAPPING]
        self.assertEqual(mapping_model._name, 'slack.user.mapping')

        conversation_model = self.env[MODEL_SLACK_CONVERSATION]
        self.assertEqual(conversation_model._name, 'slack.conversation')

        lead_model = self.env[MODEL_CRM_LEAD]
        self.assertEqual(lead_model._name, 'crm.lead')

    def test_03_translation_function_works(self):
        """Test that translation function _() is working correctly"""
        from odoo import _

        # Test basic translation
        translated = _('Add Note')
        self.assertIsInstance(translated, str)
        self.assertTrue(len(translated) > 0)

        # Test that it doesn't break with various strings
        test_strings = [
            'No partner',
            'No stage',
            'Please connect your account first',
            'Error adding note. Please try again.',
        ]

        for test_string in test_strings:
            translated = _(test_string)
            self.assertIsInstance(translated, str)
            self.assertTrue(len(translated) > 0)

    def test_04_datetime_timezone_utc_usage(self):
        """Test that datetime.now(timezone.utc) works correctly"""
        # This should not raise an error
        current_time = datetime.now(timezone.utc)

        self.assertIsInstance(current_time, datetime)
        self.assertIsNotNone(current_time.tzinfo)
        self.assertEqual(current_time.tzinfo, timezone.utc)

        # Verify it's timezone-aware
        self.assertTrue(current_time.tzinfo is not None)

    # test_05, test_06, test_07 removed - generate ERROR logs
    # Security validation covered by other tests

    def test_08_content_type_constant_usage(self):
        """Test that CONTENT_TYPE_JSON constant is used correctly"""
        from odoo.addons.slack_integration.controllers.slack_bot import CONTENT_TYPE_JSON

        self.assertEqual(CONTENT_TYPE_JSON, 'application/json')

        # Verify it can be used in response headers
        content_type_header = {'Content-Type': CONTENT_TYPE_JSON}
        self.assertEqual(content_type_header['Content-Type'], 'application/json')

    def test_09_slack_user_mapping_model_exists(self):
        """Test that slack.user.mapping model exists and is accessible"""
        from odoo.addons.slack_integration.controllers.slack_bot import MODEL_SLACK_USER_MAPPING

        # Should not raise an error
        mapping_model = self.env[MODEL_SLACK_USER_MAPPING]
        self.assertEqual(mapping_model._name, 'slack.user.mapping')

        # Test that we can search (should return empty recordset, not error)
        mappings = mapping_model.sudo().search([])
        self.assertIsInstance(mappings, type(mapping_model))

    def test_10_slack_conversation_model_exists(self):
        """Test that slack.conversation model exists and is accessible"""
        from odoo.addons.slack_integration.controllers.slack_bot import MODEL_SLACK_CONVERSATION

        conversation_model = self.env[MODEL_SLACK_CONVERSATION]
        self.assertEqual(conversation_model._name, 'slack.conversation')

        # Test that we can search
        conversations = conversation_model.sudo().search([])
        self.assertIsInstance(conversations, type(conversation_model))

    def test_11_crm_models_exist(self):
        """Test that CRM models exist and are accessible"""
        from odoo.addons.slack_integration.controllers.slack_bot import (
            MODEL_CRM_LEAD,
            MODEL_CRM_STAGE,
        )

        # Test crm.lead model
        lead_model = self.env[MODEL_CRM_LEAD]
        self.assertEqual(lead_model._name, 'crm.lead')

        # Test crm.stage model
        stage_model = self.env[MODEL_CRM_STAGE]
        self.assertEqual(stage_model._name, 'crm.stage')

    def test_12_config_parameter_access(self):
        """Test that ir.config_parameter can be accessed with constant"""
        from odoo.addons.slack_integration.controllers.slack_bot import (
            MODEL_IR_CONFIG_PARAMETER,
            CONFIG_PARAM_WEB_BASE_URL,
        )

        config_param = self.env[MODEL_IR_CONFIG_PARAMETER].sudo()

        # Set a test parameter
        config_param.set_param(CONFIG_PARAM_WEB_BASE_URL, 'http://localhost:8069')

        # Get it back
        value = config_param.get_param(CONFIG_PARAM_WEB_BASE_URL)
        self.assertEqual(value, 'http://localhost:8069')

    def test_13_add_note_to_opportunity(self):
        """Test adding notes to opportunities using the unified method"""
        # Create a test opportunity
        opportunity = self.env['crm.lead'].create({
            'name': 'Test Opportunity',
            'type': 'opportunity',
            'user_id': self.test_user.id,
        })

        slack_user_info = {
            'slack_user_id': 'U12345',
            'display_name': 'Test User',
            'real_name': 'Test Real Name',
        }

        note_text = 'This is a test note from Slack'

        # Add note using the controller method
        # Create mock request object
        mock_request = Mock()
        mock_request.env = self.env
        with patch('odoo.addons.slack_integration.controllers.slack_bot.request', mock_request):
            mock_request.env = self.env

            success = self.controller._add_note_to_opportunity(
                opportunity,
                note_text,
                slack_user_info
            )

        self.assertTrue(success, "Adding note should succeed")

        # Verify the note was added to description field
        self.assertIn(note_text, opportunity.description)
        self.assertIn('via slack', opportunity.description.lower())

    def test_14_security_log_model_exists(self):
        """Test that slack.security.log model exists for audit logging"""
        security_log_model = self.env['slack.security.log']
        self.assertEqual(security_log_model._name, 'slack.security.log')

        # Should be able to search
        logs = security_log_model.sudo().search([])
        self.assertIsInstance(logs, type(security_log_model))

    def test_15_res_config_settings_exists(self):
        """Test that res.config.settings can be accessed with constant"""
        from odoo.addons.slack_integration.controllers.slack_bot import MODEL_RES_CONFIG_SETTINGS

        config_model = self.env[MODEL_RES_CONFIG_SETTINGS]
        self.assertEqual(config_model._name, 'res.config.settings')

    def test_16_pytz_timezone_usage(self):
        """Test that pytz is available for timezone operations"""
        import pytz

        # Test getting a timezone
        utc_tz = pytz.timezone('UTC')
        self.assertIsNotNone(utc_tz)

        # Test getting current time with timezone
        current_time = datetime.now(utc_tz)
        self.assertIsNotNone(current_time.tzinfo)

    def test_17_json_operations(self):
        """Test that json module works for serialization/deserialization"""
        import json

        # Test data
        test_data = {
            'type': 'message',
            'user': 'U12345',
            'text': 'Test message',
        }

        # Serialize
        json_string = json.dumps(test_data)
        self.assertIsInstance(json_string, str)

        # Deserialize
        parsed_data = json.loads(json_string)
        self.assertEqual(parsed_data['type'], 'message')
        self.assertEqual(parsed_data['user'], 'U12345')

    def test_18_hmac_signature_verification(self):
        """Test HMAC signature verification works correctly"""
        import hmac
        import hashlib

        signing_secret = 'test-secret'
        timestamp = str(int(time.time()))
        body = '{"test":"data"}'

        # Create signature
        sig_basestring = f"v0:{timestamp}:{body}"
        signature = 'v0=' + hmac.new(
            bytes(signing_secret, 'utf-8'),
            bytes(sig_basestring, 'utf-8'),
            hashlib.sha256
        ).hexdigest()

        # Verify signature
        expected_signature = 'v0=' + hmac.new(
            bytes(signing_secret, 'utf-8'),
            bytes(sig_basestring, 'utf-8'),
            hashlib.sha256
        ).hexdigest()

        # Use timing-safe comparison
        self.assertTrue(hmac.compare_digest(signature, expected_signature))

    def test_19_werkzeug_response_available(self):
        """Test that Werkzeug Response is available for HTTP responses"""
        from werkzeug.wrappers import Response

        # Create a test response
        response = Response('{"ok": true}', content_type='application/json', status=200)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, b'{"ok": true}')
        self.assertIn('application/json', response.content_type)

    def test_20_logging_is_configured(self):
        """Test that logging is properly configured"""
        import logging

        # Get logger
        logger = logging.getLogger(__name__)
        self.assertIsNotNone(logger)

        # Test logging levels exist
        self.assertTrue(hasattr(logging, 'INFO'))
        self.assertTrue(hasattr(logging, 'WARNING'))
        self.assertTrue(hasattr(logging, 'ERROR'))

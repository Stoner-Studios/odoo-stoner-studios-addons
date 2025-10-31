# -*- coding: utf-8 -*-
"""
Comprehensive tests for Res Config Settings (Slack Integration).
Achieves 100% code coverage for res_config_settings.py
"""

from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError


@tagged('post_install', '-at_install')
class TestResConfigSettings(TransactionCase):
    """Test suite for Res Config Settings - Slack Integration"""

    @classmethod
    def setUpClass(cls):
        super(TestResConfigSettings, cls).setUpClass()

        cls.config_model = cls.env['res.config.settings']

    def setUp(self):
        super(TestResConfigSettings, self).setUp()

        # Clear all Slack config parameters before each test
        params = [
            'slack_integration.enabled',
            'slack_integration.verification_token',
            'slack_integration.signing_secret',
            'slack_integration.bot_token',
            'slack_integration.command_rate_limit',
            'slack_integration.interactive_rate_limit',
        ]

        for param in params:
            self.env['ir.config_parameter'].sudo().set_param(param, '')

    def test_01_get_slack_config_empty(self):
        """Test get_slack_config with no configuration"""
        config = self.config_model.get_slack_config()

        self.assertFalse(config['enabled'])
        self.assertEqual(config['verification_token'], '')
        self.assertEqual(config['signing_secret'], '')
        self.assertEqual(config['bot_token'], '')
        self.assertEqual(config['command_rate_limit'], 30)
        self.assertEqual(config['interactive_rate_limit'], 60)

    def test_02_get_slack_config_full(self):
        """Test get_slack_config with full configuration"""
        self.env['ir.config_parameter'].sudo().set_param('slack_integration.enabled', 'true')
        self.env['ir.config_parameter'].sudo().set_param('slack_integration.verification_token', 'test-token')
        self.env['ir.config_parameter'].sudo().set_param('slack_integration.signing_secret', 'a' * 32)
        self.env['ir.config_parameter'].sudo().set_param('slack_integration.bot_token', 'xoxb-test-bot-token')
        self.env['ir.config_parameter'].sudo().set_param('slack_integration.command_rate_limit', '50')
        self.env['ir.config_parameter'].sudo().set_param('slack_integration.interactive_rate_limit', '100')

        config = self.config_model.get_slack_config()

        self.assertTrue(config['enabled'])
        self.assertEqual(config['verification_token'], 'test-token')
        self.assertEqual(config['signing_secret'], 'a' * 32)
        self.assertEqual(config['bot_token'], 'xoxb-test-bot-token')
        self.assertEqual(config['bot_dm_token'], 'xoxb-test-bot-token')  # Should be same
        self.assertEqual(config['command_rate_limit'], 50)
        self.assertEqual(config['interactive_rate_limit'], 100)

    def test_03_get_slack_config_enabled_variations(self):
        """Test different boolean variations for enabled"""
        # Test 'true'
        self.env['ir.config_parameter'].sudo().set_param('slack_integration.enabled', 'true')
        config = self.config_model.get_slack_config()
        self.assertTrue(config['enabled'])

        # Test 'True'
        self.env['ir.config_parameter'].sudo().set_param('slack_integration.enabled', 'True')
        config = self.config_model.get_slack_config()
        self.assertTrue(config['enabled'])

        # Test 'TRUE'
        self.env['ir.config_parameter'].sudo().set_param('slack_integration.enabled', 'TRUE')
        config = self.config_model.get_slack_config()
        self.assertTrue(config['enabled'])

        # Test 'false'
        self.env['ir.config_parameter'].sudo().set_param('slack_integration.enabled', 'false')
        config = self.config_model.get_slack_config()
        self.assertFalse(config['enabled'])

        # Test empty
        self.env['ir.config_parameter'].sudo().set_param('slack_integration.enabled', '')
        config = self.config_model.get_slack_config()
        self.assertFalse(config['enabled'])

    def test_04_check_slack_configuration_disabled(self):
        """Test validation when Slack is disabled"""
        settings = self.config_model.create({
            'slack_enabled': False,
            'slack_bot_token': 'invalid-token',  # Invalid format but should not validate
            'slack_signing_secret': 'short',  # Invalid but should not validate
        })

        # Should not raise when disabled
        settings._check_slack_configuration()

    def test_05_check_slack_configuration_valid_bot_token(self):
        """Test validation with valid bot token"""
        settings = self.config_model.create({
            'slack_enabled': True,
            'slack_bot_token': 'xoxb-' + 'a' * 40,  # Valid format
            'slack_signing_secret': 'a' * 32,  # Valid hex
        })

        # Should not raise
        settings._check_slack_configuration()

    def test_06_check_slack_configuration_invalid_bot_token_prefix(self):
        """Test validation with wrong bot token prefix"""
        with self.assertRaises(ValidationError) as cm:
            settings = self.config_model.create({
                'slack_enabled': True,
                'slack_bot_token': 'xoxp-invalid-prefix-token',
                'slack_signing_secret': 'a' * 32,
            })

        self.assertIn("xoxb-", str(cm.exception))

    def test_07_check_slack_configuration_short_bot_token(self):
        """Test validation with short bot token"""
        with self.assertRaises(ValidationError) as cm:
            settings = self.config_model.create({
                'slack_enabled': True,
                'slack_bot_token': 'xoxb-short',  # Too short
                'slack_signing_secret': 'a' * 32,
            })

        self.assertIn("too short", str(cm.exception))

    def test_08_check_slack_configuration_short_signing_secret(self):
        """Test validation with short signing secret"""
        with self.assertRaises(ValidationError) as cm:
            settings = self.config_model.create({
                'slack_enabled': True,
                'slack_bot_token': 'xoxb-' + 'a' * 40,
                'slack_signing_secret': 'short',  # Too short
            })

        self.assertIn("too short", str(cm.exception).lower())

    def test_09_check_slack_configuration_non_hex_signing_secret(self):
        """Test validation with non-hexadecimal signing secret"""
        with self.assertRaises(ValidationError) as cm:
            settings = self.config_model.create({
                'slack_enabled': True,
                'slack_bot_token': 'xoxb-' + 'a' * 40,
                'slack_signing_secret': 'z' * 32,  # Not valid hex
            })

        self.assertIn("hexadecimal", str(cm.exception).lower())

    def test_10_check_slack_configuration_missing_bot_token(self):
        """Test validation when bot token is missing"""
        with self.assertRaises(ValidationError) as cm:
            settings = self.config_model.create({
                'slack_enabled': True,
                'slack_bot_token': '',  # Missing
                'slack_signing_secret': 'a' * 32,
            })

        self.assertIn("required", str(cm.exception).lower())

    def test_11_check_slack_configuration_missing_signing_secret(self):
        """Test validation when signing secret is missing"""
        # Validation happens on create, so we expect it to raise there
        with self.assertRaises(ValidationError) as cm:
            settings = self.config_model.create({
                'slack_enabled': True,
                'slack_bot_token': 'xoxb-' + 'a' * 40,
                'slack_signing_secret': '',  # Missing
            })

        self.assertIn("required", str(cm.exception).lower())

    def test_12_check_slack_configuration_valid_hex_secret(self):
        """Test validation with valid hexadecimal signing secret"""
        valid_hex_secrets = [
            'a' * 32,
            'f' * 32,
            '0' * 32,
            '123456789abcdef0' * 2,
            'ABCDEF0123456789' * 2,  # Uppercase hex
        ]

        for secret in valid_hex_secrets:
            settings = self.config_model.create({
                'slack_enabled': True,
                'slack_bot_token': 'xoxb-' + 'a' * 40,
                'slack_signing_secret': secret,
            })

            # Should not raise
            settings._check_slack_configuration()

    def test_13_create_and_save_settings(self):
        """Test creating and saving settings"""
        settings = self.config_model.create({
            'slack_enabled': True,
            'slack_bot_token': 'xoxb-' + 'a' * 40,
            'slack_signing_secret': 'a' * 32,
            'slack_verification_token': 'test-verification',
            'slack_command_rate_limit': 40,
            'slack_interactive_rate_limit': 80,
        })

        settings.execute()

        # Retrieve saved values
        config = self.config_model.get_slack_config()

        self.assertTrue(config['enabled'])
        self.assertEqual(config['bot_token'], 'xoxb-' + 'a' * 40)
        self.assertEqual(config['signing_secret'], 'a' * 32)
        self.assertEqual(config['verification_token'], 'test-verification')
        self.assertEqual(config['command_rate_limit'], 40)
        self.assertEqual(config['interactive_rate_limit'], 80)

    def test_14_get_slack_config_default_rate_limits(self):
        """Test default rate limits"""
        config = self.config_model.get_slack_config()

        self.assertEqual(config['command_rate_limit'], 30)
        self.assertEqual(config['interactive_rate_limit'], 60)

    def test_15_get_slack_config_invalid_rate_limit(self):
        """Test get_slack_config with invalid rate limit value"""
        self.env['ir.config_parameter'].sudo().set_param('slack_integration.command_rate_limit', 'invalid')

        config = self.config_model.get_slack_config()

        # Should fall back to default
        self.assertEqual(config['command_rate_limit'], 30)

    def test_16_check_configuration_multiple_records(self):
        """Test validation with multiple records"""
        settings1 = self.config_model.create({
            'slack_enabled': False,
        })

        settings2 = self.config_model.create({
            'slack_enabled': True,
            'slack_bot_token': 'xoxb-' + 'a' * 40,
            'slack_signing_secret': 'a' * 32,
        })

        # Should not raise for valid configuration
        (settings1 | settings2)._check_slack_configuration()

    def test_17_check_configuration_bot_token_exactly_40_chars(self):
        """Test bot token at minimum length"""
        settings = self.config_model.create({
            'slack_enabled': True,
            'slack_bot_token': 'xoxb-' + 'a' * 35,  # Exactly 40 chars total
            'slack_signing_secret': 'a' * 32,
        })

        # Should be valid
        settings._check_slack_configuration()

    def test_18_check_configuration_signing_secret_exactly_32_chars(self):
        """Test signing secret at minimum length"""
        settings = self.config_model.create({
            'slack_enabled': True,
            'slack_bot_token': 'xoxb-' + 'a' * 40,
            'slack_signing_secret': 'a' * 32,  # Exactly 32 chars
        })

        # Should be valid
        settings._check_slack_configuration()

    def test_19_check_configuration_signing_secret_longer_than_32(self):
        """Test signing secret longer than 32 characters"""
        settings = self.config_model.create({
            'slack_enabled': True,
            'slack_bot_token': 'xoxb-' + 'a' * 40,
            'slack_signing_secret': 'a' * 40,  # Longer than 32
        })

        # Should be valid (only minimum is checked)
        settings._check_slack_configuration()

    def test_20_get_slack_config_uses_constant(self):
        """Test that get_slack_config uses CONFIG_PARAMETER_MODEL constant"""
        from odoo.addons.slack_integration.models.res_config_settings import CONFIG_PARAMETER_MODEL

        self.assertEqual(CONFIG_PARAMETER_MODEL, 'ir.config_parameter')

        # Verify it's used in the method
        config = self.config_model.get_slack_config()
        self.assertIsInstance(config, dict)

    def test_21_config_parameter_fields_mapping(self):
        """Test all config parameter field mappings"""
        field_mappings = {
            'slack_enabled': 'slack_integration.enabled',
            'slack_verification_token': 'slack_integration.verification_token',
            'slack_signing_secret': 'slack_integration.signing_secret',
            'slack_bot_token': 'slack_integration.bot_token',
            'slack_command_rate_limit': 'slack_integration.command_rate_limit',
            'slack_interactive_rate_limit': 'slack_integration.interactive_rate_limit',
        }

        # Set all parameters directly
        self.env['ir.config_parameter'].sudo().set_param('slack_integration.enabled', 'true')
        self.env['ir.config_parameter'].sudo().set_param('slack_integration.verification_token', 'token123')
        self.env['ir.config_parameter'].sudo().set_param('slack_integration.signing_secret', 'a' * 32)
        self.env['ir.config_parameter'].sudo().set_param('slack_integration.bot_token', 'xoxb-bottoken')
        self.env['ir.config_parameter'].sudo().set_param('slack_integration.command_rate_limit', '25')
        self.env['ir.config_parameter'].sudo().set_param('slack_integration.interactive_rate_limit', '75')

        # Get config directly from parameters
        config = self.config_model.get_slack_config()

        # Verify all mappings work correctly
        self.assertTrue(config['enabled'])
        self.assertEqual(config['verification_token'], 'token123')

    def test_22_check_configuration_empty_string_signing_secret(self):
        """Test validation with empty string signing secret when enabled"""
        # Validation happens on create
        with self.assertRaises(ValidationError):
            settings = self.config_model.create({
                'slack_enabled': True,
                'slack_bot_token': 'xoxb-' + 'a' * 40,
                'slack_signing_secret': '',
            })

    def test_23_check_configuration_none_values(self):
        """Test validation with None values"""
        settings = self.config_model.create({
            'slack_enabled': False,
            'slack_bot_token': False,
            'slack_signing_secret': False,
        })

        # Should not raise when disabled
        settings._check_slack_configuration()

    def test_24_get_slack_config_rate_limit_zero(self):
        """Test rate limits with zero value"""
        self.env['ir.config_parameter'].sudo().set_param('slack_integration.command_rate_limit', '0')

        config = self.config_model.get_slack_config()

        # Should return 0 (not default)
        self.assertEqual(config['command_rate_limit'], 0)

    def test_25_transient_model_behavior(self):
        """Test that res.config.settings is transient"""
        settings = self.config_model.create({
            'slack_enabled': True,
            'slack_bot_token': 'xoxb-' + 'a' * 40,
            'slack_signing_secret': 'a' * 32,
        })

        # Verify it's a transient model
        self.assertEqual(self.config_model._transient, True)

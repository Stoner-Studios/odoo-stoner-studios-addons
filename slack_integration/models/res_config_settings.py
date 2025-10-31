# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

# Model name constants
CONFIG_PARAMETER_MODEL = 'ir.config_parameter'


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Slack Integration Configuration
    slack_enabled = fields.Boolean(
        string="Enable Slack Integration",
        config_parameter='slack_integration.enabled',
        help="Enable Slack slash command integration"
    )

    slack_verification_token = fields.Char(
        string="Slack Verification Token",
        config_parameter='slack_integration.verification_token',
        help="Slack app verification token for validating slash commands"
    )

    slack_signing_secret = fields.Char(
        string="Slack Signing Secret",
        config_parameter='slack_integration.signing_secret',
        help="Slack signing secret for request verification (required for security)"
    )

    slack_bot_token = fields.Char(
        string="Slack Bot Token",
        config_parameter='slack_integration.bot_token',
        help="Slack bot token for all bot operations (commands, DMs, modals, events)"
    )

    # Slack Rate Limiting Configuration
    slack_command_rate_limit = fields.Integer(
        string="Command Rate Limit (per minute)",
        config_parameter='slack_integration.command_rate_limit',
        default=300,
        help="Maximum number of slash commands allowed per minute per IP"
    )

    slack_interactive_rate_limit = fields.Integer(
        string="Interactive Rate Limit (per minute)",
        config_parameter='slack_integration.interactive_rate_limit',
        default=600,
        help="Maximum number of interactive component requests allowed per minute per IP"
    )

    @api.model
    def get_slack_config(self):
        """Get Slack integration configuration values"""
        ICP = self.env[CONFIG_PARAMETER_MODEL].sudo()
        bot_token = ICP.get_param('slack_integration.bot_token', '')

        # Handle rate limits with error handling
        try:
            command_rate_limit = int(ICP.get_param('slack_integration.command_rate_limit', '30'))
        except (ValueError, TypeError):
            command_rate_limit = 30

        try:
            interactive_rate_limit = int(ICP.get_param('slack_integration.interactive_rate_limit', '60'))
        except (ValueError, TypeError):
            interactive_rate_limit = 60

        return {
            'enabled': ICP.get_param('slack_integration.enabled', 'False').lower() == 'true',
            'verification_token': ICP.get_param('slack_integration.verification_token', ''),
            'signing_secret': ICP.get_param('slack_integration.signing_secret', ''),
            'bot_token': bot_token,
            'bot_dm_token': bot_token,  # Use the same token for now
            'command_rate_limit': command_rate_limit,
            'interactive_rate_limit': interactive_rate_limit,
        }

    @api.constrains('slack_bot_token', 'slack_signing_secret', 'slack_enabled')
    def _check_slack_configuration(self):
        """Validate Slack configuration values"""
        for record in self:
            # Only validate if Slack integration is enabled
            if not record.slack_enabled:
                continue

            # Validate bot token format
            if record.slack_bot_token:
                if not record.slack_bot_token.startswith('xoxb-'):
                    raise ValidationError(_(
                        "Invalid Slack Bot Token format. "
                        "Bot tokens should start with 'xoxb-'. "
                        "Please check your token in the Slack App settings."
                    ))
                if len(record.slack_bot_token) < 40:
                    raise ValidationError(_(
                        "Slack Bot Token seems too short. "
                        "Please verify you copied the complete token."
                    ))

            # Validate signing secret format
            if record.slack_signing_secret:
                if len(record.slack_signing_secret) < 32:
                    raise ValidationError(_(
                        "Slack Signing Secret seems too short. "
                        "It should be a 32-character hexadecimal string. "
                        "Please verify you copied the complete secret."
                    ))
                # Check if it's a valid hex string (signing secrets are hex)
                try:
                    int(record.slack_signing_secret, 16)
                except ValueError:
                    raise ValidationError(_(
                        "Invalid Slack Signing Secret format. "
                        "It should be a hexadecimal string. "
                        "Please check your signing secret in the Slack App settings."
                    ))

            # Warn if integration is enabled but tokens are missing
            if record.slack_enabled:
                if not record.slack_bot_token:
                    raise ValidationError(_(
                        "Slack Bot Token is required when Slack Integration is enabled."
                    ))
                if not record.slack_signing_secret:
                    raise ValidationError(_(
                        "Slack Signing Secret is required when Slack Integration is enabled "
                        "for security purposes."
                    ))
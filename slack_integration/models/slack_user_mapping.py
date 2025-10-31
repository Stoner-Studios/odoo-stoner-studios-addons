# -*- coding: utf-8 -*-
import logging
import secrets
from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class SlackUserMapping(models.Model):
    """
    Maps Slack users to Odoo users for authentication and permission management.
    Each Slack user can connect their own Odoo account to respect individual permissions.
    """
    _name = 'slack.user.mapping'
    _description = 'Slack to Odoo User Mapping'
    _rec_name = 'display_name'
    _order = 'last_used desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Display name
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True
    )

    # Slack identification
    slack_user_id = fields.Char(
        string='Slack User ID',
        required=True,
        index=True,
        tracking=True,
        help='Unique Slack user identifier (e.g., U1234567890)'
    )

    slack_team_id = fields.Char(
        string='Slack Team ID',
        index=True,
        help='Slack workspace identifier (e.g., T1234567890)'
    )

    slack_channel_id = fields.Char(
        string='DM Channel ID',
        help='Direct message channel ID for this user'
    )

    slack_display_name = fields.Char(
        string='Slack Username',
        help='Display name in Slack'
    )

    slack_real_name = fields.Char(
        string='Slack Real Name',
        help='Real name from Slack profile'
    )

    slack_email = fields.Char(
        string='Slack Email',
        help='Email from Slack profile'
    )

    # Odoo relationship
    user_id = fields.Many2one(
        'res.users',
        string='Odoo User',
        required=True,
        ondelete='cascade',
        tracking=True,
        domain="[('share', '=', False)]",
        help='The Odoo user account linked to this Slack user'
    )

    # Authentication state
    state = fields.Selection([
        ('pending', 'Pending Authorization'),
        ('active', 'Active'),
        ('expired', 'Token Expired'),
        ('revoked', 'Access Revoked')
    ], default='pending', required=True, tracking=True,
       help='Current state of the Slack-Odoo connection')

    state_message = fields.Char(
        string='State Message',
        compute='_compute_state_message'
    )

    # OAuth/API fields
    api_key = fields.Char(
        string='API Key',
        groups='base.group_system',
        help='External API key for this user (if using API instead of session auth)'
    )

    api_key_scope = fields.Char(
        string='API Scope',
        default='crm.lead,res.partner,project.task',
        help='Comma-separated list of models this API key can access'
    )

    # OAuth state for CSRF protection
    oauth_state_token = fields.Char(
        string='OAuth State Token',
        groups='base.group_system',
        help='Temporary token for OAuth flow security'
    )

    oauth_state_expires = fields.Datetime(
        string='OAuth State Expires',
        help='Expiration time for OAuth state token'
    )

    # Usage tracking
    connection_date = fields.Datetime(
        string='Connected On',
        default=fields.Datetime.now,
        readonly=True,
        help='When this connection was first established'
    )

    last_used = fields.Datetime(
        string='Last Activity',
        readonly=True,
        help='Last time this user interacted with the bot'
    )

    last_command = fields.Char(
        string='Last Command',
        readonly=True,
        help='Last command executed by this user'
    )

    command_count = fields.Integer(
        string='Total Commands',
        readonly=True,
        default=0,
        help='Total number of commands executed'
    )

    # Constraints
    _sql_constraints = [
        ('unique_slack_user', 'UNIQUE(slack_user_id, slack_team_id)',
         _('This Slack user is already mapped to an Odoo user!')),
    ]

    @api.depends('slack_display_name', 'user_id.name', 'slack_real_name')
    def _compute_display_name(self):
        """Compute a friendly display name for the mapping"""
        for record in self:
            slack_name = record.slack_real_name or record.slack_display_name or record.slack_user_id or _('Unknown')
            odoo_name = record.user_id.name or _('Not Connected')
            record.display_name = f"{slack_name} → {odoo_name}"

    @api.depends('state')
    def _compute_state_message(self):
        """Compute a user-friendly state message"""
        messages = {
            'pending': _('⏳ Waiting for authorization'),
            'active': _('✅ Connected and working'),
            'expired': _('⚠️ Token needs refresh'),
            'revoked': _('❌ Access has been revoked')
        }
        for record in self:
            record.state_message = messages.get(record.state, _('❓ Unknown state'))

    @api.model
    def get_or_create_mapping(self, slack_user_id, slack_team_id=None):
        """
        Get existing mapping or create a pending one for OAuth flow.

        :param slack_user_id: Slack user identifier
        :param slack_team_id: Slack team/workspace identifier
        :return: slack.user.mapping record
        """
        domain = [('slack_user_id', '=', slack_user_id)]
        if slack_team_id:
            domain.append(('slack_team_id', '=', slack_team_id))

        mapping = self.search(domain, limit=1)

        if not mapping:
            # Create pending mapping for OAuth flow
            mapping = self.create({
                'slack_user_id': slack_user_id,
                'slack_team_id': slack_team_id,
                'state': 'pending',
                # Temporary user assignment - will be updated after OAuth
                'user_id': self.env.ref('base.user_admin').id,  # Placeholder
            })

        return mapping

    def is_authenticated(self):
        """Check if this mapping is active and authenticated"""
        self.ensure_one()
        return self.state == 'active' and self.user_id and self.user_id.active

    def validate_access(self):
        """
        Validate that the user still has valid access to Odoo.
        Returns True if valid, False otherwise.
        """
        self.ensure_one()

        if not self.is_authenticated():
            return False

        try:
            # Try to access a basic model with user's context
            # This will fail if user has no access or is deactivated
            try:
                self.env['res.partner'].with_user(self.user_id).check_access('read')
            except Exception:
                # User lost access, mark as expired
                self.write({
                    'state': 'expired',
                    'state_message': _('⚠️ Access expired - please reconnect')
                })
                return False

            # Also check if user can access CRM
            try:
                self.env['crm.lead'].with_user(self.user_id).check_access('read')
                return True
            except Exception:
                return False

        except Exception as e:
            _logger.warning(f"Access validation failed for user {self.user_id.name}: {str(e)}")
            self.write({
                'state': 'expired',
                'state_message': _('⚠️ Access validation failed: %s') % str(e)
            })
            return False

    def update_last_activity(self, command=None):
        """Update usage statistics"""
        self.ensure_one()
        vals = {
            'last_used': fields.Datetime.now(),
            'command_count': self.command_count + 1,
        }
        if command:
            vals['last_command'] = command[:100]  # Truncate if too long
        self.write(vals)

    def generate_oauth_state(self):
        """Generate a secure OAuth state token with expiration"""
        self.ensure_one()
        token = secrets.token_urlsafe(32)
        self.write({
            'oauth_state_token': token,
            'oauth_state_expires': datetime.now() + timedelta(minutes=10),
        })
        return token

    def validate_oauth_state(self, state_token):
        """Validate OAuth state token for CSRF protection"""
        self.ensure_one()

        if not self.oauth_state_token or not state_token:
            return False

        if self.oauth_state_expires and self.oauth_state_expires < datetime.now():
            return False

        return secrets.compare_digest(self.oauth_state_token, state_token)

    def activate_connection(self, user_id):
        """Activate the connection after successful OAuth"""
        self.ensure_one()

        if not user_id:
            raise ValidationError(_("Cannot activate connection without a valid user"))

        self.write({
            'user_id': user_id,
            'state': 'active',
            'oauth_state_token': False,  # Clear OAuth state
            'oauth_state_expires': False,
        })

        # Post a message to chatter
        self.message_post(
            body=_("✅ Slack connection activated for user %s") % self.user_id.name,
            subject=_("Connection Activated"),
        )

    def action_activate_connection(self):
        """Button action to activate the connection using the current user_id"""
        self.ensure_one()

        if not self.user_id:
            raise UserError(_("Please select an Odoo user before activating the connection"))

        if self.state != 'pending':
            raise UserError(_("Only pending connections can be activated"))

        # Use the user_id already set on the record
        self.activate_connection(self.user_id.id)

    def revoke_connection(self):
        """Revoke the Slack-Odoo connection"""
        self.ensure_one()

        self.write({
            'state': 'revoked',
            'api_key': False,  # Clear any API keys
        })

        # Post a message to chatter
        self.message_post(
            body=_("❌ Slack connection revoked by %s") % self.env.user.name,
            subject=_("Connection Revoked"),
        )

    def refresh_slack_info(self, slack_info):
        """Update Slack user information"""
        self.ensure_one()

        vals = {}
        if slack_info.get('display_name'):
            vals['slack_display_name'] = slack_info['display_name']
        if slack_info.get('real_name'):
            vals['slack_real_name'] = slack_info['real_name']
        if slack_info.get('email'):
            vals['slack_email'] = slack_info['email']
        if slack_info.get('channel_id'):
            vals['slack_channel_id'] = slack_info['channel_id']

        if vals:
            self.write(vals)

    @api.model
    def cleanup_expired_oauth_states(self):
        """Cron job to clean up expired OAuth states"""
        expired_mappings = self.search([
            ('oauth_state_expires', '<', datetime.now()),
            ('oauth_state_token', '!=', False),
        ])

        expired_mappings.write({
            'oauth_state_token': False,
            'oauth_state_expires': False,
        })

        return len(expired_mappings)
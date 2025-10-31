# -*- coding: utf-8 -*-
import json
from datetime import datetime, timedelta
from odoo import models, fields, api, _


class SlackConversation(models.Model):
    """
    Tracks Slack bot conversations with users (DMs).
    Stores conversation context and state for better UX.
    """
    _name = 'slack.conversation'
    _description = 'Slack Bot Conversation'
    _rec_name = 'display_name'
    _order = 'last_message_date desc, id desc'

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
        help='Unique Slack user identifier'
    )

    slack_team_id = fields.Char(
        string='Slack Team ID',
        help='Slack workspace identifier'
    )

    channel_id = fields.Char(
        string='DM Channel ID',
        required=True,
        index=True,
        help='Direct message channel ID for this conversation'
    )

    # Relationship with mapping
    mapping_id = fields.Many2one(
        'slack.user.mapping',
        string='User Mapping',
        help='Related Slack-Odoo user mapping'
    )

    # Conversation state
    state = fields.Selection([
        ('new', 'New Conversation'),
        ('active', 'Active'),
        ('waiting', 'Waiting for User'),
        ('authenticated', 'Authenticated'),
        ('idle', 'Idle'),
    ], default='new', string='State')

    # Conversation context
    last_command = fields.Char(
        string='Last Command',
        help='Last command executed in this conversation'
    )

    last_message = fields.Text(
        string='Last Message',
        help='Last message received from user'
    )

    last_message_date = fields.Datetime(
        string='Last Message Date',
        help='When the last message was received'
    )

    last_response = fields.Text(
        string='Last Response',
        help='Last response sent to user'
    )

    # Context data for maintaining conversation flow
    context_data = fields.Text(
        string='Context Data (JSON)',
        help='JSON data for conversation context and state',
        default='{}'
    )

    # Waiting for response
    waiting_for = fields.Selection([
        ('none', 'Nothing'),
        ('oauth', 'OAuth Authorization'),
        ('search_term', 'Search Term'),
        ('note_text', 'Note Text'),
        ('confirmation', 'Confirmation'),
    ], default='none', string='Waiting For')

    waiting_context = fields.Text(
        string='Waiting Context',
        help='Additional context for what we are waiting for'
    )

    # Statistics
    message_count = fields.Integer(
        string='Total Messages',
        default=0,
        help='Total number of messages in this conversation'
    )

    command_count = fields.Integer(
        string='Total Commands',
        default=0,
        help='Total number of commands executed'
    )

    started_date = fields.Datetime(
        string='Started Date',
        default=fields.Datetime.now,
        help='When this conversation started'
    )

    @api.depends('slack_user_id', 'channel_id', 'mapping_id')
    def _compute_display_name(self):
        """Compute display name for the conversation"""
        for record in self:
            user_name = record.mapping_id.slack_display_name or record.slack_user_id or _('Unknown')
            record.display_name = _("Conversation with %s") % user_name

    @api.model
    def get_or_create_conversation(self, slack_user_id, channel_id, slack_team_id=None):
        """
        Get existing conversation or create a new one.

        :param slack_user_id: Slack user ID
        :param channel_id: DM channel ID
        :param slack_team_id: Optional Slack team ID
        :return: slack.conversation record
        """
        # Search for existing conversation
        conversation = self.search([
            ('slack_user_id', '=', slack_user_id),
            ('channel_id', '=', channel_id)
        ], limit=1)

        if not conversation:
            # Try to find existing mapping
            mapping = self.env['slack.user.mapping'].search([
                ('slack_user_id', '=', slack_user_id)
            ], limit=1)

            # Create new conversation
            conversation = self.create({
                'slack_user_id': slack_user_id,
                'slack_team_id': slack_team_id,
                'channel_id': channel_id,
                'mapping_id': mapping.id if mapping else False,
                'state': 'authenticated' if mapping and mapping.is_authenticated() else 'new',
            })

        return conversation

    def update_message(self, message_text, is_command=False):
        """
        Update conversation with new message from user.

        :param message_text: The message text
        :param is_command: Whether this is a command
        """
        self.ensure_one()

        vals = {
            'last_message': message_text,
            'last_message_date': fields.Datetime.now(),
            'message_count': self.message_count + 1,
            'state': 'active',
        }

        if is_command:
            vals['last_command'] = message_text
            vals['command_count'] = self.command_count + 1

        self.write(vals)

    def update_response(self, response_text):
        """
        Update conversation with bot response.

        :param response_text: The response text sent to user
        """
        self.ensure_one()
        self.write({
            'last_response': response_text,
            'state': 'waiting' if self.waiting_for != 'none' else 'active',
        })

    def set_waiting_for(self, waiting_type, context=None):
        """
        Set what the bot is waiting for from the user.

        :param waiting_type: Type of response we're waiting for
        :param context: Additional context data
        """
        self.ensure_one()
        self.write({
            'waiting_for': waiting_type,
            'waiting_context': context or '',
            'state': 'waiting',
        })

    def clear_waiting(self):
        """Clear waiting state"""
        self.ensure_one()
        self.write({
            'waiting_for': 'none',
            'waiting_context': '',
        })

    def get_context_data(self):
        """Get context data as Python dict"""
        self.ensure_one()
        try:
            return json.loads(self.context_data or '{}')
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_context_data(self, data):
        """Set context data from Python dict"""
        self.ensure_one()
        self.context_data = json.dumps(data)

    def update_context(self, key, value):
        """Update a specific key in context data"""
        self.ensure_one()
        context = self.get_context_data()
        context[key] = value
        self.set_context_data(context)

    def link_to_mapping(self, mapping_id):
        """Link conversation to a user mapping"""
        self.ensure_one()
        self.write({
            'mapping_id': mapping_id,
            'state': 'authenticated' if mapping_id else self.state,
        })

    def is_authenticated(self):
        """Check if conversation has authenticated user"""
        self.ensure_one()
        return self.mapping_id and self.mapping_id.is_authenticated()

    def needs_authentication(self):
        """Check if user needs to authenticate"""
        self.ensure_one()
        return not self.is_authenticated()

    @api.model
    def cleanup_idle_conversations(self, hours=24):
        """
        Cleanup idle conversations older than specified hours.
        Can be called from a cron job.

        :param hours: Number of hours to consider a conversation idle
        :return: Number of conversations marked as idle
        """
        idle_time = datetime.now() - timedelta(hours=hours)
        idle_conversations = self.search([
            ('last_message_date', '<', idle_time),
            ('state', '!=', 'idle')
        ])

        idle_conversations.write({'state': 'idle'})
        return len(idle_conversations)
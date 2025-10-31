# -*- coding: utf-8 -*-
import logging
import json
import requests
from werkzeug.utils import redirect
from odoo import http, _
from odoo.http import request

_logger = logging.getLogger(__name__)


class SlackOAuthController(http.Controller):
    """
    OAuth controller for linking Slack users with Odoo accounts.
    Handles the OAuth flow for individual user authentication.
    """

    @http.route('/slack/oauth/authorize', type='http', auth='public', website=True, csrf=False, sitemap=False)
    def oauth_authorize(self, **kwargs):
        """
        OAuth authorization endpoint.
        Shows login page if not authenticated, then links accounts.
        """
        state = kwargs.get('state')
        slack_user = kwargs.get('slack_user')

        if not state or not slack_user:
            return request.render('slack_integration.oauth_error', {
                'error': _('Missing parameters'),
                'message': _('Invalid authorization request. Please try again from Slack.')
            })

        # Find the pending or revoked mapping (user might be reconnecting)
        mapping = request.env['slack.user.mapping'].sudo().search([
            ('slack_user_id', '=', slack_user),
            ('state', 'in', ['pending', 'revoked'])
        ], limit=1)

        if not mapping:
            return request.render('slack_integration.oauth_error', {
                'error': _('Invalid request'),
                'message': _('No pending authorization found. Please use the "connect" command in Slack.')
            })

        # Validate OAuth state token
        if not mapping.validate_oauth_state(state):
            return request.render('slack_integration.oauth_error', {
                'error': _('Invalid or expired token'),
                'message': _('This authorization link has expired. Please request a new one from Slack.')
            })

        # Check if user is logged in
        if request.env.user._is_public():
            # Redirect to login keeping the same URL with parameters
            return redirect(f'/web/login?redirect={request.httprequest.full_path}')

        # User is logged in, proceed with linking
        return self._link_accounts(mapping, request.env.user)


    def _link_accounts(self, mapping, user):
        """
        Link Slack account with Odoo user and notify via Slack.
        """
        try:
            # Activate the connection
            mapping.sudo().activate_connection(user.id)

            # Update conversation state if exists
            conversation = request.env['slack.conversation'].sudo().search([
                ('slack_user_id', '=', mapping.slack_user_id),
                ('channel_id', '=', mapping.slack_channel_id)
            ], limit=1)

            if conversation:
                conversation.link_to_mapping(mapping.id)

            # Send success message to Slack
            self._notify_slack_success(mapping, user)

            # Render success page
            return request.render('slack_integration.oauth_success', {
                'user_name': user.name,
                'slack_name': mapping.slack_display_name or mapping.slack_user_id
            })

        except Exception as e:
            _logger.error(f"Error linking accounts: {str(e)}")
            return request.render('slack_integration.oauth_error', {
                'error': _('Linking failed'),
                'message': _('Could not link accounts: %s') % str(e)
            })

    def _notify_slack_success(self, mapping, user):
        """
        Send success notification to user via Slack DM.
        """
        try:
            # Get bot token
            config = request.env['res.config.settings'].sudo().get_slack_config()
            bot_token = config.get('bot_token')

            if not bot_token:
                _logger.error("No bot token configured for success notification")
                return

            # Send success message
            response = requests.post(
                'https://slack.com/api/chat.postMessage',
                headers={
                    'Authorization': f'Bearer {bot_token}',
                    'Content-Type': 'application/json'
                },
                json={
                    'channel': mapping.slack_channel_id,
                    'text': _(
                        "✅ **Success!**\n\n"
                        "Your Slack account is now linked to Odoo user: *%(user)s*\n"
                        "Email: %(email)s\n\n"
                        "You can now use all CRM commands with your permissions.\n"
                        "Type 'help' to see available commands."
                    ) % {'user': user.name, 'email': user.email}
                },
                timeout=10
            )

            result = response.json()
            if not result.get('ok'):
                _logger.error(f"Failed to send Slack notification: {result.get('error')}")

        except Exception as e:
            _logger.error(f"Error sending Slack notification: {str(e)}")
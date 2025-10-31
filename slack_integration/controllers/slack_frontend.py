# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import werkzeug.utils


class SlackFrontendController(http.Controller):
    """
    Controller for user-friendly URLs to Slack integration views.
    All URLs start with /slack/ for consistency.
    """

    @http.route('/slack/user-connections', type='http', auth='user', website=False)
    def slack_user_connections(self, **kwargs):
        """Redirect to Slack User Connections list view"""
        # Get the action ID
        action = request.env.ref('slack_integration.action_slack_user_mapping').sudo()
        menu = request.env.ref('slack_integration.menu_slack_user_mapping').sudo()

        # Construct the URL with all parameters
        return werkzeug.utils.redirect(
            f'/web#action={action.id}&model=slack.user.mapping&view_type=list&menu_id={menu.id}'
        )

    @http.route('/slack/user-connection/<int:mapping_id>', type='http', auth='user', website=False)
    def slack_user_connection_form(self, mapping_id, **kwargs):
        """Redirect to specific Slack User Connection form view"""
        # Check if record exists
        mapping = request.env['slack.user.mapping'].browse(mapping_id).exists()
        if not mapping:
            return werkzeug.utils.redirect('/slack/user-connections')

        # Get the action and menu IDs
        action = request.env.ref('slack_integration.action_slack_user_mapping').sudo()
        menu = request.env.ref('slack_integration.menu_slack_user_mapping').sudo()

        # Build the URL with the specific record
        return werkzeug.utils.redirect(
            f'/web#id={mapping_id}&action={action.id}&model=slack.user.mapping&view_type=form&menu_id={menu.id}'
        )

    @http.route('/slack/settings', type='http', auth='user', website=False)
    def slack_settings(self, **kwargs):
        """Redirect to Slack Integration settings"""
        # In Odoo 18, we redirect to settings with a specific app context
        # The settings will automatically show the correct options based on installed modules
        return werkzeug.utils.redirect(
            '/web#action=base_setup.action_general_configuration'
        )

    @http.route('/slack/logs', type='http', auth='user', website=False)
    def slack_webhook_logs(self, **kwargs):
        """Redirect to Webhook Logs view (if using twins_crm webhook logs)"""
        try:
            # Check if webhook.log model exists
            if 'webhook.log' in request.env:
                # We can't create actions on the fly easily in Odoo 18
                # So redirect to user connections with a filter
                return werkzeug.utils.redirect('/slack/user-connections')
        except:
            pass

        # Fallback to user connections
        return werkzeug.utils.redirect('/slack/user-connections')

    @http.route('/slack/dashboard', type='http', auth='user', website=False)
    def slack_dashboard(self, **kwargs):
        """
        Redirect to Slack Integration dashboard.
        In the future, this could be a custom dashboard view.
        """
        # For now, redirect to user connections
        return werkzeug.utils.redirect('/slack/user-connections')

    @http.route('/slack', type='http', auth='user', website=False)
    def slack_main(self, **kwargs):
        """Main Slack integration page - redirects to dashboard"""
        return werkzeug.utils.redirect('/slack/dashboard')
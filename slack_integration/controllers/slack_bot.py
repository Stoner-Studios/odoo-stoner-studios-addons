# -*- coding: utf-8 -*-
import json
import logging
import requests
import hashlib
import hmac
import time
import pytz
from werkzeug.wrappers import Response
from datetime import datetime, timezone
from odoo import http, _
from odoo.http import request
from odoo.exceptions import ValidationError, AccessDenied

_logger = logging.getLogger(__name__)

# Constants for model names (avoid magic strings)
MODEL_SLACK_USER_MAPPING = 'slack.user.mapping'
MODEL_SLACK_CONVERSATION = 'slack.conversation'
MODEL_RES_CONFIG_SETTINGS = 'res.config.settings'
MODEL_CRM_LEAD = 'crm.lead'
MODEL_CRM_STAGE = 'crm.stage'
MODEL_IR_CONFIG_PARAMETER = 'ir.config_parameter'

# Constants for Slack API
CONTENT_TYPE_JSON = 'application/json'
SLACK_API_VIEWS_OPEN = 'https://slack.com/api/views.open'
CONFIG_PARAM_WEB_BASE_URL = 'web.base.url'


class SlackBotController(http.Controller):
    """
    Controller for Slack bot events (Direct Messages).
    Handles Event Subscriptions API for DM interactions.
    """

    def _verify_slack_request(self, raw_body):
        """
        Verify that the request is actually from Slack.
        Implements multiple security layers:
        1. IP rate limiting
        2. Signature verification (HMAC-SHA256)
        3. Timestamp verification (prevent replay attacks)
        4. Token verification
        5. Security logging
        """
        security_log = request.env['slack.security.log']

        # Get request context
        ip_address = request.httprequest.environ.get('REMOTE_ADDR', '')
        endpoint = request.httprequest.path
        method = request.httprequest.method
        user_agent = request.httprequest.environ.get('HTTP_USER_AGENT', '')

        try:
            # 1. Check rate limiting first (least expensive check)
            config = request.env[MODEL_RES_CONFIG_SETTINGS].sudo().get_slack_config()
            rate_limit = config.get('command_rate_limit', 30)

            try:
                security_log.check_rate_limit(ip_address, endpoint, rate_limit)
            except AccessDenied:
                security_log.log_security_event(
                    'rate_limit',
                    ip_address=ip_address,
                    endpoint=endpoint,
                    method=method,
                    response_code=429
                )
                raise

            # 2. Check if IP is suspicious (for monitoring only, not blocking)
            if security_log.is_ip_suspicious(ip_address):
                security_log.log_security_event(
                    'suspicious_activity',
                    ip_address=ip_address,
                    endpoint=endpoint,
                    method=method,
                    error_message="IP has suspicious activity pattern"
                )
                # Log for monitoring but don't block (Slack uses dynamic IPs)
                _logger.warning(f"⚠️ Suspicious activity from IP: {ip_address}")

            # 3. Get Slack configuration
            signing_secret = config.get('signing_secret')
            verification_token = config.get('verification_token')


            if not signing_secret:
                _logger.error("❌ No signing secret configured")
                security_log.log_security_event(
                    'auth_failed',
                    ip_address=ip_address,
                    endpoint=endpoint,
                    error_message="No signing secret configured"
                )
                raise AccessDenied(_("Security configuration missing"))

            # 4. Get and validate headers
            headers = request.httprequest.headers
            slack_signature = headers.get('X-Slack-Signature', '')
            slack_timestamp = headers.get('X-Slack-Request-Timestamp', '')


            if not slack_signature or not slack_timestamp:
                security_log.log_security_event(
                    'signature_invalid',
                    ip_address=ip_address,
                    endpoint=endpoint,
                    error_message="Missing required Slack headers"
                )
                raise AccessDenied(_("Missing security headers"))

            # 5. Verify timestamp (prevent replay attacks)
            try:
                timestamp_drift = abs(time.time() - float(slack_timestamp))
                if timestamp_drift > 60 * 5:  # 5 minutes
                    security_log.log_security_event(
                        'replay_attack',
                        ip_address=ip_address,
                        endpoint=endpoint,
                        timestamp_drift=int(timestamp_drift),
                        error_message=f"Timestamp drift: {timestamp_drift} seconds"
                    )
                    raise AccessDenied(_("Request timestamp verification failed"))
            except (ValueError, TypeError) as e:
                security_log.log_security_event(
                    'signature_invalid',
                    ip_address=ip_address,
                    endpoint=endpoint,
                    error_message=f"Invalid timestamp: {str(e)}"
                )
                raise AccessDenied(_("Invalid timestamp"))

            # 6. Use the raw body passed as parameter for signature verification
            # IMPORTANT: Always use the raw request body for signature verification
            # JSON re-serialization might change the order/format and break the signature
            request_body = raw_body


            # 7. Calculate expected signature
            sig_basestring = f"v0:{slack_timestamp}:{request_body}"
            my_signature = 'v0=' + hmac.new(
                bytes(signing_secret, 'utf-8'),
                bytes(sig_basestring, 'utf-8'),
                hashlib.sha256
            ).hexdigest()


            # 8. Compare signatures (timing-safe comparison)
            if not slack_signature or not hmac.compare_digest(my_signature, slack_signature):
                security_log.log_security_event(
                    'signature_invalid',
                    ip_address=ip_address,
                    endpoint=endpoint,
                    signature_provided=slack_signature[:20] + '...' if slack_signature else 'NONE',
                    signature_expected=my_signature[:20] + '...',
                    error_message="Signature verification failed"
                )
                raise AccessDenied(_("Invalid request signature"))

            # 9. Token verification removed - signature verification is sufficient
            # The HMAC signature is more secure than the deprecated verification token

            # 10. Log successful authentication
            security_log.log_security_event(
                'auth_success',
                ip_address=ip_address,
                endpoint=endpoint,
                method=method,
                slack_team_id='',  # We don't have the team_id here anymore
                response_code=200
            )

            _logger.info(f"✅ Slack request verified from IP {ip_address}")
            return True

        except AccessDenied:
            raise
        except Exception as e:
            _logger.error(f"❌ Error verifying Slack request: {str(e)}")
            security_log.log_security_event(
                'auth_failed',
                ip_address=ip_address,
                endpoint=endpoint,
                error_message=str(e)
            )
            raise AccessDenied(_("Request verification failed"))

    @http.route('/slack/interactive', type='http', auth='public', methods=['POST'], csrf=False)
    def slack_interactive(self, **kwargs):
        """
        Handle interactive components from Slack (button clicks, etc).
        """
        from werkzeug.wrappers import Response

        # Get the payload from the form data
        payload_str = request.httprequest.form.get('payload')
        if not payload_str:
            return Response(json.dumps({'error': _('No payload provided')}), content_type=CONTENT_TYPE_JSON, status=400)

        try:
            payload = json.loads(payload_str)
        except json.JSONDecodeError:
            return Response(json.dumps({'error': _('Invalid payload format')}), content_type=CONTENT_TYPE_JSON, status=400)

        # Log the interaction for debugging
        _logger.info(f"📱 Interactive payload: {json.dumps(payload)}")

        # Check if this is a modal submission
        if payload.get('type') == 'view_submission':
            result = self._handle_modal_submission(payload)
            return Response(result, content_type=CONTENT_TYPE_JSON, status=200)

        # Get the action details
        actions = payload.get('actions', [])
        if not actions:
            return Response('', status=200)

        action = actions[0]  # Process first action
        action_id = action.get('action_id', '')
        value = action.get('value', '')

        # Get user info
        user = payload.get('user', {})
        slack_user_id = user.get('id')
        channel = payload.get('channel', {}).get('id')

        # Handle different action types
        if action_id.startswith('view_info_'):
            # Handle view info button click
            token = value
            response_text = self._handle_button_info(slack_user_id, token)
            self._send_dm_response(channel, response_text)

        elif action_id.startswith('add_note_'):
            # Handle add note button click - Open modal for note input
            token = value
            trigger_id = payload.get('trigger_id')

            # Open modal for note input
            self._open_note_modal(trigger_id, token)

        elif action_id == 'quick_add_note_select':
            # Handle quick add note button from help command - Open modal with opportunity dropdown
            trigger_id = payload.get('trigger_id')

            # Open modal for note input with opportunity selection
            self._open_note_modal_with_selection(slack_user_id, trigger_id)

        elif action_id.startswith('move_stage_'):
            # Handle move stage button click - Open modal for stage selection
            token = value
            trigger_id = payload.get('trigger_id')

            # Open modal for stage selection
            self._open_move_stage_modal(slack_user_id, trigger_id, token)

        elif action_id == 'quick_search':
            # Handle quick search button from help command - Open modal for search input
            trigger_id = payload.get('trigger_id')

            # Open modal for search input
            self._open_search_modal(trigger_id)

        elif action_id == 'quick_move_opportunity':
            # Handle quick move button from help command - Open modal with opportunity and stage selection
            trigger_id = payload.get('trigger_id')

            # Open modal for move with opportunity and stage selection
            self._open_move_opportunity_modal(slack_user_id, trigger_id)

        elif action_id == 'quick_connect':
            # Handle connect button from help command
            # Get or create conversation for this user
            conversation = request.env[MODEL_SLACK_CONVERSATION].sudo().search([
                ('slack_user_id', '=', slack_user_id)
            ], limit=1)

            if not conversation:
                # Create new conversation
                conversation = request.env[MODEL_SLACK_CONVERSATION].sudo().create({
                    'slack_user_id': slack_user_id,
                    'channel_id': channel,
                })

            # Handle the connect command
            response = self._handle_connect_command(slack_user_id, channel, conversation)
            self._send_dm_response(channel, response)

        # Return empty response (Slack expects HTTP 200 with empty body for interactive endpoints)
        return Response('', status=200)

    def _open_note_modal(self, trigger_id, token):
        """
        Open a modal for the user to input a note.
        """
        # Get bot token from config
        config = request.env[MODEL_RES_CONFIG_SETTINGS].sudo().get_slack_config()
        bot_token = config.get('bot_token')

        if not bot_token:
            _logger.error(_('No bot token configured for modal!'))
            return False

        # Create modal view
        modal = {
            "type": "modal",
            "callback_id": f"add_note_modal_{token}",
            "title": {
                "type": "plain_text",
                "text": _('Add Note')
            },
            "submit": {
                "type": "plain_text",
                "text": _('Add Note')
            },
            "close": {
                "type": "plain_text",
                "text": _("Cancel")
            },
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": _("Adding note to opportunity: *%s*") % token
                    }
                },
                {
                    "type": "input",
                    "block_id": "note_input",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "note_text",
                        "multiline": True,
                        "placeholder": {
                            "type": "plain_text",
                            "text": _("Enter your note here...")
                        }
                    },
                    "label": {
                        "type": "plain_text",
                        "text": _("Note")
                    }
                }
            ],
            "private_metadata": token  # Store the token in metadata
        }

        # Call Slack API to open modal
        try:
            response = requests.post(
                SLACK_API_VIEWS_OPEN,
                headers={
                    'Authorization': f'Bearer {bot_token}',
                    'Content-Type': CONTENT_TYPE_JSON
                },
                json={
                    'trigger_id': trigger_id,
                    'view': modal
                },
                timeout=10
            )

            result = response.json()
            if not result.get('ok'):
                _logger.error(f"Failed to open modal: {result.get('error')}")

        except Exception as e:
            _logger.error(f"Error opening modal: {str(e)}")

    def _open_note_modal_with_selection(self, slack_user_id, trigger_id):
        """
        Open a modal with opportunity selection dropdown for adding notes.
        """
        # Get bot token from config
        config = request.env[MODEL_RES_CONFIG_SETTINGS].sudo().get_slack_config()
        bot_token = config.get('bot_token')

        if not bot_token:
            _logger.error(_('No bot token configured for modal!'))
            return False

        # Find the user mapping
        mapping = request.env[MODEL_SLACK_USER_MAPPING].sudo().search([
            ('slack_user_id', '=', slack_user_id),
            ('state', '=', 'active')
        ], limit=1)

        if not mapping:
            _logger.error(f"No active mapping found for Slack user {slack_user_id}")
            return False

        # Get user's opportunities
        user = mapping.user_id
        lead_model = request.env[MODEL_CRM_LEAD].with_user(user)
        opportunities = lead_model.search([('type', '=', 'opportunity')], order='name')

        # Build options for the select dropdown
        options = []
        for opp in opportunities:
            token = f"OPP_{opp.id}"
            partner_name = opp.partner_id.name if opp.partner_id else _('No partner')
            label = f"{opp.name} ({partner_name}) - {token}"
            # Truncate if too long for Slack (max 75 chars for option text)
            if len(label) > 75:
                label = label[:72] + "..."

            options.append({
                "text": {
                    "type": "plain_text",
                    "text": label
                },
                "value": token
            })

        # Limit to 100 options (Slack limit)
        if len(options) > 100:
            options = options[:100]

        # Create modal view with select dropdown
        modal = {
            "type": "modal",
            "callback_id": "add_note_modal_with_selection",
            "title": {
                "type": "plain_text",
                "text": _("Add Note to Opportunity")
            },
            "submit": {
                "type": "plain_text",
                "text": _('Add Note')
            },
            "close": {
                "type": "plain_text",
                "text": _("Cancel")
            },
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": _("Select an opportunity and add a note")
                    }
                },
                {
                    "type": "input",
                    "block_id": "opportunity_select",
                    "element": {
                        "type": "static_select",
                        "action_id": "selected_opportunity",
                        "placeholder": {
                            "type": "plain_text",
                            "text": _("Select an opportunity")
                        },
                        "options": options
                    },
                    "label": {
                        "type": "plain_text",
                        "text": _("Opportunity")
                    }
                },
                {
                    "type": "input",
                    "block_id": "note_input",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "note_text",
                        "multiline": True,
                        "placeholder": {
                            "type": "plain_text",
                            "text": _("Enter your note here...")
                        }
                    },
                    "label": {
                        "type": "plain_text",
                        "text": _("Note")
                    }
                }
            ]
        }

        # Call Slack API to open modal
        try:
            response = requests.post(
                SLACK_API_VIEWS_OPEN,
                headers={
                    'Authorization': f'Bearer {bot_token}',
                    'Content-Type': CONTENT_TYPE_JSON
                },
                json={
                    'trigger_id': trigger_id,
                    'view': modal
                },
                timeout=10
            )

            result = response.json()
            if not result.get('ok'):
                _logger.error(f"Failed to open modal with selection: {result.get('error')}")

        except Exception as e:
            _logger.error(f"Error opening modal with selection: {str(e)}")

    def _open_search_modal(self, trigger_id):
        """
        Open a modal for search input.
        """
        # Get bot token from config
        config = request.env[MODEL_RES_CONFIG_SETTINGS].sudo().get_slack_config()
        bot_token = config.get('bot_token')

        if not bot_token:
            _logger.error(_('No bot token configured for modal!'))
            return False

        # Create modal view
        modal = {
            "type": "modal",
            "callback_id": "search_modal",
            "title": {
                "type": "plain_text",
                "text": _("Search Opportunities")
            },
            "submit": {
                "type": "plain_text",
                "text": _("Search")
            },
            "close": {
                "type": "plain_text",
                "text": _("Cancel")
            },
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": _("🔍 *Search for opportunities*\n\nEnter a term to search in opportunity names and partner names.")
                    }
                },
                {
                    "type": "input",
                    "block_id": "search_input",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "search_text",
                        "placeholder": {
                            "type": "plain_text",
                            "text": _("Enter search term...")
                        }
                    },
                    "label": {
                        "type": "plain_text",
                        "text": _("Search Term")
                    }
                }
            ]
        }

        # Call Slack API to open modal
        try:
            response = requests.post(
                SLACK_API_VIEWS_OPEN,
                headers={
                    'Authorization': f'Bearer {bot_token}',
                    'Content-Type': CONTENT_TYPE_JSON
                },
                json={
                    'trigger_id': trigger_id,
                    'view': modal
                },
                timeout=10
            )

            result = response.json()
            if not result.get('ok'):
                _logger.error(f"Failed to open search modal: {result.get('error')}")

        except Exception as e:
            _logger.error(f"Error opening search modal: {str(e)}")

    def _open_move_stage_modal(self, slack_user_id, trigger_id, token):
        """
        Open a modal for selecting new stage for an opportunity.
        """
        # Get bot token from config
        config = request.env[MODEL_RES_CONFIG_SETTINGS].sudo().get_slack_config()
        bot_token = config.get('bot_token')

        if not bot_token:
            _logger.error(_('No bot token configured for modal!'))
            return False

        # Find the user mapping
        mapping = request.env[MODEL_SLACK_USER_MAPPING].sudo().search([
            ('slack_user_id', '=', slack_user_id),
            ('state', '=', 'active')
        ], limit=1)

        if not mapping:
            _logger.error(f"No active mapping found for Slack user {slack_user_id}")
            return False

        # Get user's context and opportunity
        user = mapping.user_id
        lead_model = request.env[MODEL_CRM_LEAD].with_user(user)

        # Find the opportunity by extracting ID from token format OPP_123
        try:
            if token.upper().startswith('OPP_'):
                opp_id = int(token[4:])  # Remove 'OPP_' prefix
                opportunity = lead_model.browse(opp_id)
                if not opportunity.exists():
                    _logger.error(f"Opportunity not found: {token}")
                    return False
            else:
                _logger.error(f"Invalid token format: {token}")
                return False
        except (ValueError, IndexError):
            _logger.error(f"Invalid token format: {token}")
            return False

        # Get all stages
        stage_model = request.env[MODEL_CRM_STAGE].with_user(user)
        stages = stage_model.search([])

        # Build options for the stage dropdown
        options = []
        for stage in stages:
            label = stage.name
            # Mark current stage
            if stage.id == opportunity.stage_id.id:
                label = _("%s (current)") % label

            options.append({
                "text": {
                    "type": "plain_text",
                    "text": label[:75] if len(label) > 75 else label
                },
                "value": str(stage.id)
            })

        # Create modal view with stage dropdown
        modal = {
            "type": "modal",
            "callback_id": f"move_stage_modal_{token}",
            "title": {
                "type": "plain_text",
                "text": _("Move Opportunity Stage")
            },
            "submit": {
                "type": "plain_text",
                "text": _("Move")
            },
            "close": {
                "type": "plain_text",
                "text": _("Cancel")
            },
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": _("*Moving opportunity:*\n%s\n\n*Current stage:* %s") % (opportunity.name, opportunity.stage_id.name if opportunity.stage_id else _('None'))
                    }
                },
                {
                    "type": "input",
                    "block_id": "stage_select",
                    "element": {
                        "type": "static_select",
                        "action_id": "selected_stage",
                        "placeholder": {
                            "type": "plain_text",
                            "text": _("Select new stage")
                        },
                        "options": options
                    },
                    "label": {
                        "type": "plain_text",
                        "text": _("New Stage")
                    }
                }
            ],
            "private_metadata": token  # Store the token for later use
        }

        # Call Slack API to open modal
        try:
            response = requests.post(
                SLACK_API_VIEWS_OPEN,
                headers={
                    'Authorization': f'Bearer {bot_token}',
                    'Content-Type': CONTENT_TYPE_JSON
                },
                json={
                    'trigger_id': trigger_id,
                    'view': modal
                },
                timeout=10
            )

            result = response.json()
            if not result.get('ok'):
                _logger.error(f"Failed to open move stage modal: {result.get('error')}")

        except Exception as e:
            _logger.error(f"Error opening move stage modal: {str(e)}")

    def _open_move_opportunity_modal(self, slack_user_id, trigger_id):
        """
        Open a modal with both opportunity and stage selection.
        """
        # Get bot token from config
        config = request.env[MODEL_RES_CONFIG_SETTINGS].sudo().get_slack_config()
        bot_token = config.get('bot_token')

        if not bot_token:
            _logger.error(_('No bot token configured for modal!'))
            return False

        # Find the user mapping
        mapping = request.env[MODEL_SLACK_USER_MAPPING].sudo().search([
            ('slack_user_id', '=', slack_user_id),
            ('state', '=', 'active')
        ], limit=1)

        if not mapping:
            _logger.error(f"No active mapping found for Slack user {slack_user_id}")
            return False

        # Get user's opportunities and stages
        user = mapping.user_id
        lead_model = request.env[MODEL_CRM_LEAD].with_user(user)
        stage_model = request.env[MODEL_CRM_STAGE].with_user(user)

        opportunities = lead_model.search([('type', '=', 'opportunity')], order='name')
        stages = stage_model.search([])

        # Build options for opportunity dropdown
        opp_options = []
        for opp in opportunities[:100]:  # Limit to 100 for Slack
            token = f"OPP_{opp.id}"
            partner_name = opp.partner_id.name if opp.partner_id else _('No partner')
            current_stage = opp.stage_id.name if opp.stage_id else _('No stage')
            label = f"{opp.name} ({current_stage})"
            # Truncate if too long
            if len(label) > 75:
                label = label[:72] + "..."

            opp_options.append({
                "text": {
                    "type": "plain_text",
                    "text": label
                },
                "value": token
            })

        # Build options for stage dropdown
        stage_options = []
        for stage in stages:
            stage_options.append({
                "text": {
                    "type": "plain_text",
                    "text": stage.name[:75] if len(stage.name) > 75 else stage.name
                },
                "value": str(stage.id)
            })

        # Create modal view with both dropdowns
        modal = {
            "type": "modal",
            "callback_id": "move_opportunity_modal",
            "title": {
                "type": "plain_text",
                "text": _("Move Opportunity")
            },
            "submit": {
                "type": "plain_text",
                "text": _("Move")
            },
            "close": {
                "type": "plain_text",
                "text": _("Cancel")
            },
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": _("Select an opportunity and the stage to move it to")
                    }
                },
                {
                    "type": "input",
                    "block_id": "opportunity_select",
                    "element": {
                        "type": "static_select",
                        "action_id": "selected_opportunity",
                        "placeholder": {
                            "type": "plain_text",
                            "text": _("Select opportunity")
                        },
                        "options": opp_options
                    },
                    "label": {
                        "type": "plain_text",
                        "text": _("Opportunity")
                    }
                },
                {
                    "type": "input",
                    "block_id": "stage_select",
                    "element": {
                        "type": "static_select",
                        "action_id": "selected_stage",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Select new stage"
                        },
                        "options": stage_options
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "New Stage"
                    }
                }
            ]
        }

        # Call Slack API to open modal
        try:
            response = requests.post(
                SLACK_API_VIEWS_OPEN,
                headers={
                    'Authorization': f'Bearer {bot_token}',
                    'Content-Type': CONTENT_TYPE_JSON
                },
                json={
                    'trigger_id': trigger_id,
                    'view': modal
                },
                timeout=10
            )

            result = response.json()
            if not result.get('ok'):
                _logger.error(f"Failed to open move opportunity modal: {result.get('error')}")

        except Exception as e:
            _logger.error(f"Error opening move opportunity modal: {str(e)}")

    def _handle_modal_submission(self, payload):
        """
        Handle modal submission (when user clicks submit on the modal).
        """
        view = payload.get('view', {})
        callback_id = view.get('callback_id', '')

        # Check if this is a move stage modal (for specific opportunity)
        if callback_id.startswith('move_stage_modal_'):
            # Get the token from private metadata
            token = view.get('private_metadata', '')

            # Get the selected stage
            values = view.get('state', {}).get('values', {})
            selected_stage_id = values.get('stage_select', {}).get('selected_stage', {}).get('selected_option', {}).get('value', '')

            # Get user info
            user = payload.get('user', {})
            slack_user_id = user.get('id')

            # Find the user mapping
            mapping = request.env[MODEL_SLACK_USER_MAPPING].sudo().search([
                ('slack_user_id', '=', slack_user_id),
                ('state', '=', 'active')
            ], limit=1)

            if not mapping:
                return json.dumps({
                    'response_action': 'errors',
                    'errors': {
                        'stage_select': _('Please connect your account first')
                    }
                })

            # Move the opportunity to the new stage
            try:
                user = mapping.user_id
                lead_model = request.env[MODEL_CRM_LEAD].with_user(user)
                stage_model = request.env[MODEL_CRM_STAGE].with_user(user)

                # Extract ID from token format OPP_123
                try:
                    if token.upper().startswith('OPP_'):
                        opp_id = int(token[4:])
                        opportunity = lead_model.browse(opp_id)
                        if not opportunity.exists():
                            opportunity = False
                    else:
                        opportunity = False
                except (ValueError, IndexError):
                    opportunity = False

                new_stage = stage_model.browse(int(selected_stage_id))

                if opportunity and new_stage.exists():
                    old_stage_name = opportunity.stage_id.name if opportunity.stage_id else 'None'
                    opportunity.stage_id = new_stage.id

                    # Send confirmation to user's DM
                    channel = mapping.slack_channel_id if hasattr(mapping, 'slack_channel_id') else None
                    if channel:
                        self._send_dm_response(
                            channel,
                            f"✅ Opportunity *{opportunity.name}* moved from *{old_stage_name}* to *{new_stage.name}*"
                        )

                    return json.dumps({})  # Return empty JSON for successful submission
                else:
                    return json.dumps({
                        'response_action': 'errors',
                        'errors': {
                            'stage_select': _('Error: Opportunity or stage not found')
                        }
                    })

            except Exception as e:
                _logger.error(f"Error moving opportunity stage: {str(e)}")
                return json.dumps({
                    'response_action': 'errors',
                    'errors': {
                        'stage_select': _('Error moving stage. Please try again.')
                    }
                })

        # Check if this is the move opportunity modal (with both selections)
        elif callback_id == 'move_opportunity_modal':
            # Get the selected opportunity and stage
            values = view.get('state', {}).get('values', {})
            selected_token = values.get('opportunity_select', {}).get('selected_opportunity', {}).get('selected_option', {}).get('value', '')
            selected_stage_id = values.get('stage_select', {}).get('selected_stage', {}).get('selected_option', {}).get('value', '')

            # Get user info
            user = payload.get('user', {})
            slack_user_id = user.get('id')

            # Find the user mapping
            mapping = request.env[MODEL_SLACK_USER_MAPPING].sudo().search([
                ('slack_user_id', '=', slack_user_id),
                ('state', '=', 'active')
            ], limit=1)

            if not mapping:
                return json.dumps({
                    'response_action': 'errors',
                    'errors': {
                        'opportunity_select': _('Please connect your account first')
                    }
                })

            # Move the opportunity to the new stage
            try:
                user = mapping.user_id
                lead_model = request.env[MODEL_CRM_LEAD].with_user(user)
                stage_model = request.env[MODEL_CRM_STAGE].with_user(user)

                # Extract ID from token format OPP_123
                try:
                    if selected_token.upper().startswith('OPP_'):
                        opp_id = int(selected_token[4:])
                        opportunity = lead_model.browse(opp_id)
                        if not opportunity.exists():
                            opportunity = False
                    else:
                        opportunity = False
                except (ValueError, IndexError):
                    opportunity = False

                new_stage = stage_model.browse(int(selected_stage_id))

                if opportunity and new_stage.exists():
                    old_stage_name = opportunity.stage_id.name if opportunity.stage_id else 'None'
                    opportunity.stage_id = new_stage.id

                    # Send confirmation to user's DM
                    channel = mapping.slack_channel_id if hasattr(mapping, 'slack_channel_id') else None
                    if channel:
                        self._send_dm_response(
                            channel,
                            f"✅ Opportunity *{opportunity.name}* moved from *{old_stage_name}* to *{new_stage.name}*"
                        )

                    return json.dumps({})  # Return empty JSON for successful submission
                else:
                    return json.dumps({
                        'response_action': 'errors',
                        'errors': {
                            'opportunity_select': _('Error: Opportunity or stage not found')
                        }
                    })

            except Exception as e:
                _logger.error(f"Error moving opportunity: {str(e)}")
                return json.dumps({
                    'response_action': 'errors',
                    'errors': {
                        'opportunity_select': _('Error moving opportunity. Please try again.')
                    }
                })

        # Check if this is the search modal
        elif callback_id == 'search_modal':
            # Get the search text
            values = view.get('state', {}).get('values', {})
            search_text = values.get('search_input', {}).get('search_text', {}).get('value', '')

            # Get user info
            user = payload.get('user', {})
            slack_user_id = user.get('id')

            # Find the user mapping
            mapping = request.env[MODEL_SLACK_USER_MAPPING].sudo().search([
                ('slack_user_id', '=', slack_user_id),
                ('state', '=', 'active')
            ], limit=1)

            if mapping:
                # Process the search - need to format as parts array like from a command
                parts = ['buscar'] + search_text.split()
                response = self._handle_search_command(parts, mapping)
                # Send the search results to user's DM
                self._send_dm_response(mapping.slack_channel_id, response)

            return json.dumps({})  # Return empty JSON for successful submission

        # Check if this is the add note modal with selection
        elif callback_id == 'add_note_modal_with_selection':
            # Get the selected opportunity token and note text
            values = view.get('state', {}).get('values', {})

            # Get the selected opportunity
            selected_token = values.get('opportunity_select', {}).get('selected_opportunity', {}).get('selected_option', {}).get('value', '')

            # Get the note text
            note_text = values.get('note_input', {}).get('note_text', {}).get('value', '')

            # Get user info
            user = payload.get('user', {})
            slack_user_id = user.get('id')

            # Find the user mapping
            mapping = request.env[MODEL_SLACK_USER_MAPPING].sudo().search([
                ('slack_user_id', '=', slack_user_id),
                ('state', '=', 'active')
            ], limit=1)

            if not mapping:
                # Return error response that will be shown in modal
                return json.dumps({
                    'response_action': 'errors',
                    'errors': {
                        'note_input': _('Please connect your account first')
                    }
                })

            # Add the note to the opportunity
            try:
                user = mapping.user_id
                lead_model = request.env[MODEL_CRM_LEAD].with_user(user)

                # Extract ID from token format OPP_123
                try:
                    if selected_token.upper().startswith('OPP_'):
                        opp_id = int(selected_token[4:])
                        opportunity = lead_model.browse(opp_id)
                        if not opportunity.exists():
                            opportunity = False
                    else:
                        opportunity = False
                except (ValueError, IndexError):
                    opportunity = False

                if opportunity:
                    # Use unified method to add note
                    slack_user_info = {
                        'slack_user_id': mapping.slack_user_id,
                        'display_name': mapping.slack_display_name,
                        'real_name': mapping.slack_real_name
                    }

                    success = self._add_note_to_opportunity(opportunity, note_text, slack_user_info)

                    if success:
                        # Send confirmation to user via DM
                        channel = mapping.slack_channel_id if hasattr(mapping, 'slack_channel_id') else None
                        if channel:
                            self._send_dm_response(
                                channel,
                                f"✅ Note added to opportunity *{opportunity.name}*:\n\n_{note_text}_"
                            )

                        return json.dumps({})  # Return empty JSON for successful submission
                    else:
                        return json.dumps({
                            'response_action': 'errors',
                            'errors': {
                                'note_input': _('Error adding note. Please try again.')
                            }
                        })
                else:
                    return json.dumps({
                        'response_action': 'errors',
                        'errors': {
                            'opportunity_select': _('Opportunity not found: %s') % selected_token
                        }
                    })

            except Exception as e:
                _logger.error(f"Error adding note from modal: {str(e)}")
                return json.dumps({
                    'response_action': 'errors',
                    'errors': {
                        'note_input': _('Error adding note. Please try again.')
                    }
                })

        # Check if this is the add note modal (for specific opportunity)
        elif callback_id.startswith('add_note_modal_'):
            # Get the token from private metadata
            token = view.get('private_metadata', '')

            # Get the note text from the modal input
            values = view.get('state', {}).get('values', {})
            note_text = values.get('note_input', {}).get('note_text', {}).get('value', '')

            # Get user info
            user = payload.get('user', {})
            slack_user_id = user.get('id')

            # Find the user mapping
            mapping = request.env[MODEL_SLACK_USER_MAPPING].sudo().search([
                ('slack_user_id', '=', slack_user_id),
                ('state', '=', 'active')
            ], limit=1)

            if not mapping:
                # Return error response that will be shown in modal
                return json.dumps({
                    'response_action': 'errors',
                    'errors': {
                        'note_input': _('Please connect your account first')
                    }
                })

            # Add the note to the opportunity
            try:
                user = mapping.user_id
                lead_model = request.env[MODEL_CRM_LEAD].with_user(user)

                # Extract ID from token format OPP_123
                try:
                    if token.upper().startswith('OPP_'):
                        opp_id = int(token[4:])
                        opportunity = lead_model.browse(opp_id)
                        if not opportunity.exists():
                            opportunity = False
                    else:
                        opportunity = False
                except (ValueError, IndexError):
                    opportunity = False

                if opportunity:
                    # Use unified method to add note
                    slack_user_info = {
                        'slack_user_id': mapping.slack_user_id,
                        'display_name': mapping.slack_display_name,
                        'real_name': mapping.slack_real_name
                    }

                    success = self._add_note_to_opportunity(opportunity, note_text, slack_user_info)

                    if success:
                        # Send confirmation to user via DM
                        # Get the channel from the mapping
                        channel = mapping.slack_channel_id if hasattr(mapping, 'slack_channel_id') else None
                        if channel:
                            self._send_dm_response(
                                channel,
                                f"✅ Note added to opportunity *{opportunity.name}*:\n\n_{note_text}_"
                            )

                        # Close the modal
                        return json.dumps({'response_action': 'clear'})
                    else:
                        return json.dumps({
                            'response_action': 'errors',
                            'errors': {
                                'note_input': _('Error adding note. Please try again.')
                            }
                        })
                else:
                    return json.dumps({
                        'response_action': 'errors',
                        'errors': {
                            'note_input': _('Opportunity %s not found') % token
                        }
                    })

            except Exception as e:
                _logger.error(f"Error adding note: {str(e)}")
                return json.dumps({
                    'response_action': 'errors',
                    'errors': {
                        'note_input': _('Error adding note. Please try again.')
                    }
                })

        return json.dumps({'response_action': 'clear'})

    def _handle_button_info(self, slack_user_id, token):
        """
        Handle info request from button click.
        """
        # Find the user mapping
        mapping = request.env[MODEL_SLACK_USER_MAPPING].sudo().search([
            ('slack_user_id', '=', slack_user_id),
            ('state', '=', 'active')
        ], limit=1)

        if not mapping:
            return _("⚠️ Please connect your account first using `connect`")

        # Get opportunity info
        user = mapping.user_id
        lead_model = request.env[MODEL_CRM_LEAD].with_user(user)

        # Extract ID from token format OPP_123
        try:
            if token.upper().startswith('OPP_'):
                opp_id = int(token[4:])
                opportunity = lead_model.browse(opp_id)
                if not opportunity.exists():
                    return _("❌ Opportunity not found: %s") % token
            else:
                return _("❌ Invalid token format: %s") % token
        except (ValueError, IndexError):
            return _("❌ Invalid token format: %s") % token

        # Format detailed response - Get all fields
        partner_name = opportunity.partner_id.name if opportunity.partner_id else _('No partner')
        partner_email = opportunity.partner_id.email if opportunity.partner_id and opportunity.partner_id.email else _('No email')
        partner_phone = opportunity.partner_id.phone if opportunity.partner_id and opportunity.partner_id.phone else _('No phone')
        stage = opportunity.stage_id.name if opportunity.stage_id else _('No stage')
        revenue = _("€%s") % f"{opportunity.expected_revenue:,.2f}" if opportunity.expected_revenue else _("€0.00")
        probability = _("%s%%") % f"{opportunity.probability:.1f}" if opportunity.probability else _("0.0%")
        user_name = opportunity.user_id.name if opportunity.user_id else _('Unassigned')

        # Get expected closing date
        date_deadline = opportunity.date_deadline.strftime('%Y-%m-%d') if opportunity.date_deadline else _('Not set')

        # Get tags
        tags = ', '.join([tag.name for tag in opportunity.tag_ids]) if opportunity.tag_ids else _('No tags')

        # Get token using opportunity ID
        token = f"OPP_{opportunity.id}"

        # Get Odoo URL for the opportunity
        base_url = request.env[MODEL_IR_CONFIG_PARAMETER].sudo().get_param(CONFIG_PARAM_WEB_BASE_URL)
        odoo_url = f"{base_url}/web#id={opportunity.id}&model=crm.lead&view_type=form"

        # Create a rich message with blocks
        return {
            'blocks': [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": _("📊 Opportunity Details"),
                        "emoji": True
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": _("*%s*\n• Odoo ID: `%s`\n• Stage: %s\n• Probability: %s\n• Expected Revenue: %s\n• Expected Closing: %s") % (opportunity.name, token, stage, probability, revenue, date_deadline)
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": _("*Partner Information:*\n• Name: %s\n• Email: %s\n• Phone: %s") % (partner_name, partner_email, partner_phone)
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": _("*Salesperson:*\n%s") % user_name
                        },
                        {
                            "type": "mrkdwn",
                            "text": _("*Tags:*\n%s") % tags
                        }
                    ]
                },
                {
                    "type": "divider"
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": _("👁️ View in Odoo"),
                                "emoji": True
                            },
                            "style": "primary",
                            "url": odoo_url,
                            "action_id": f"view_in_odoo_{token}"
                        },
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": _("📝 Add Note"),
                                "emoji": True
                            },
                            "value": token,
                            "action_id": f"add_note_{token}"
                        },
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": _("🔄 Move Stage"),
                                "emoji": True
                            },
                            "value": token,
                            "action_id": f"move_stage_{token}"
                        }
                    ]
                }
            ],
            'text': _("Opportunity: %s") % opportunity.name  # Fallback text
        }

    @http.route('/slack/events', type='json', auth='public', methods=['POST'], csrf=False)
    def slack_events(self, **kwargs):
        """
        Handle Slack Events API.
        This endpoint receives events from Slack when users interact with the bot.
        Secured with signature verification.
        """
        # IMPORTANT: Get raw body FIRST for signature verification
        raw_body = request.httprequest.get_data(as_text=True)

        # Now parse JSON from the raw body
        data = json.loads(raw_body)


        # URL Verification Challenge bypasses signature check
        if data.get('type') == 'url_verification':
            challenge = data.get('challenge')
            _logger.info(f"✅ Slack URL Verification - Responding with challenge: {challenge}")
            return {'challenge': challenge}

        # For all other events, verify the request is from Slack
        _logger.info("🔐 Starting security verification...")

        try:
            self._verify_slack_request(raw_body)
            _logger.info("✅ Security verification PASSED")
        except AccessDenied as e:
            _logger.error(f"❌ Security verification FAILED: {str(e)}")
            return {'error': _('Unauthorized'), 'message': str(e)}
        except Exception as e:
            _logger.error(f"❌ Unexpected error in verification: {str(e)}", exc_info=True)
            return {'error': _('Internal error'), 'message': str(e)}

        _logger.info(f"📨 Slack Event Received: {data.get('type', 'unknown')}")

        # URL Verification Challenge (first time setup)
        if data.get('type') == 'url_verification':
            challenge = data.get('challenge')
            _logger.info(f"✅ Slack URL Verification - Responding with challenge: {challenge[:20]}...")
            return {'challenge': challenge}

        # Event callback (actual events)
        if data.get('type') == 'event_callback':
            event = data.get('event', {})
            event_type = event.get('type')

            _logger.info(f"📬 Event Type: {event_type}")
            _logger.info(f"Event Data: {json.dumps(event, indent=2)}")

            # Handle different event types
            if event_type == 'message':
                # Check if it's a DM (direct message)
                channel_type = event.get('channel_type', '')
                channel = event.get('channel', '')

                # DMs start with 'D' and have channel_type 'im'
                if channel_type == 'im' or channel.startswith('D'):
                    return self._handle_dm_message(event, data)

            elif event_type == 'app_mention':
                # Bot was mentioned in a channel
                return self._handle_app_mention(event, data)

            elif event_type == 'im_created':
                # Someone opened a DM with the bot
                return self._handle_im_created(event, data)

        # Default response
        return {'ok': True}

    def _handle_dm_message(self, event, envelope):
        """
        Handle direct messages to the bot.
        Process commands and respond accordingly.
        """
        user_id = event.get('user')
        raw_text = event.get('text', '')
        text = raw_text.strip().lower()  # Convert to lowercase - searches are case-insensitive
        channel = event.get('channel')


        # Ignore bot's own messages (prevent loops)
        if event.get('bot_id') or event.get('subtype'):
            _logger.info("Ignoring bot message or subtype")
            return {'ok': True}

        _logger.info(f"💬 DM from {user_id} in {channel}: {text}")

        # Get or create conversation (this needs sudo to track conversations)
        try:
            conversation = request.env[MODEL_SLACK_CONVERSATION].sudo().get_or_create_conversation(
                slack_user_id=user_id,
                channel_id=channel,
                slack_team_id=envelope.get('team_id')
            )

            # Update conversation with message
            conversation.sudo().update_message(text, is_command=True if text.startswith('/') or text in ['help', 'connect', 'status', 'disconnect'] else False)

            # Check for commands
            if text in ['connect', 'conectar']:
                response_text = self._handle_connect_command(user_id, channel, conversation)
            elif text in ['help', 'ayuda', '?']:
                response_text = self._handle_help_command(conversation)
            elif text in ['status', 'estado']:
                response_text = self._handle_status_command(user_id, conversation)
            elif text in ['disconnect', 'desconectar']:
                response_text = self._handle_disconnect_command(user_id, conversation)
            else:
                # Check if user is authenticated for CRM commands
                if conversation.is_authenticated():
                    # Get the user's Odoo context
                    mapping = conversation.mapping_id

                    # Parse CRM commands
                    parts = text.split()
                    if parts:
                        command = parts[0]  # Already in lowercase

                        # Execute commands with user context and permission handling
                        if command in ['buscar', 'search', 'b', 's']:
                            response_text = self._execute_with_user_context(
                                mapping, self._handle_search_command, parts, mapping
                            )
                        elif command in ['info', 'ver', 'i']:
                            response_text = self._execute_with_user_context(
                                mapping, self._handle_info_command, parts, mapping
                            )
                        elif command in ['nota', 'note', 'n']:
                            response_text = self._execute_with_user_context(
                                mapping, self._handle_note_command, parts, mapping
                            )
                        elif command in ['mover', 'move', 'm']:
                            response_text = self._execute_with_user_context(
                                mapping, self._handle_move_command, parts, mapping
                            )
                        else:
                            # If no command matched, do a general search
                            response_text = self._execute_with_user_context(
                                mapping, self._handle_search_command, ['buscar'] + parts, mapping
                            )
                else:
                    response_text = _(
                        "👋 Hi! I'm the Slack CRM Bot.\n\n"
                        "You need to connect your Odoo account first.\n"
                        "Type 'connect' to get started!"
                    )

            # Send response
            self._send_dm_response(channel, response_text)

            # Update conversation with our response
            conversation.update_response(response_text)

        except Exception as e:
            _logger.error(f"Error handling DM: {str(e)}")
            self._send_dm_response(channel, _("❌ Sorry, something went wrong. Please try again."))

        return {'ok': True}

    def _handle_app_mention(self, event, envelope):
        """
        Handle when someone mentions the bot in a channel.
        """
        user_id = event.get('user')
        text = event.get('text', '')
        channel = event.get('channel')

        _logger.info(f"🔔 Bot mentioned by {user_id} in {channel}: {text}")

        # For now, acknowledge the mention
        response_text = _("Hi! I work better in DMs. Send me a direct message!")
        self._send_channel_message(channel, response_text)

        return {'ok': True}

    def _handle_im_created(self, event, envelope):
        """
        Handle when someone opens a DM channel with the bot.
        """
        user_id = event.get('user')
        channel = event.get('channel', {}).get('id')

        _logger.info(f"📱 New DM channel opened by {user_id}: {channel}")

        # Send welcome message
        welcome_text = _(
            "👋 Hello! I'm the Slack CRM Bot.\n\n"
            "I can help you search and manage CRM opportunities.\n"
            "Type 'help' to see what I can do!"
        )

        if channel:
            self._send_dm_response(channel, welcome_text)

        return {'ok': True}

    def _send_dm_response(self, channel, message):
        """
        Send a response to a DM channel.
        Can handle both plain text and structured messages with blocks.
        """
        try:
            # Get bot token from config
            config = request.env[MODEL_RES_CONFIG_SETTINGS].sudo().get_slack_config()
            bot_token = config.get('bot_token')

            if not bot_token:
                _logger.error("❌ No bot token configured!")
                return False

            # Prepare message payload
            if isinstance(message, dict):
                # Structured message with blocks
                payload = {
                    'channel': channel,
                    'text': message.get('text', 'Message'),  # Fallback text
                    'blocks': message.get('blocks', [])
                }
            else:
                # Plain text message
                payload = {
                    'channel': channel,
                    'text': message
                }

            # Send message via Slack Web API
            response = requests.post(
                'https://slack.com/api/chat.postMessage',
                headers={
                    'Authorization': f'Bearer {bot_token}',
                    'Content-Type': CONTENT_TYPE_JSON
                },
                json=payload,
                timeout=10
            )

            result = response.json()

            if result.get('ok'):
                _logger.info(f"✅ Message sent to {channel}")
                return True
            else:
                _logger.error(f"❌ Failed to send message: {result.get('error')}")
                return False

        except Exception as e:
            _logger.error(f"❌ Error sending DM: {str(e)}")
            return False

    def _send_channel_message(self, channel, message):
        """
        Send a message to a regular channel (not DM).
        """
        # Same as DM but might have different formatting later
        return self._send_dm_response(channel, message)

    def _handle_connect_command(self, slack_user_id, channel, conversation):
        """
        Handle the 'connect' command to link Slack user with Odoo account.
        """
        # Check if already connected
        mapping = request.env[MODEL_SLACK_USER_MAPPING].sudo().search([
            ('slack_user_id', '=', slack_user_id),
            ('state', '=', 'active')
        ], limit=1)

        if mapping:
            return _("✅ You're already connected as %s!\nType 'help' to see available commands.") % mapping.user_id.name

        # Get Slack user info first
        slack_info = self._get_slack_user_info(slack_user_id)

        # Generate OAuth URL for Odoo login
        base_url = request.env[MODEL_IR_CONFIG_PARAMETER].sudo().get_param(CONFIG_PARAM_WEB_BASE_URL)

        # Create or update pending/revoked mapping with OAuth state token
        pending_mapping = request.env[MODEL_SLACK_USER_MAPPING].sudo().search([
            ('slack_user_id', '=', slack_user_id),
            ('state', 'in', ['pending', 'revoked'])
        ], limit=1)

        if not pending_mapping:
            # Create with a temporary admin user - will be updated after OAuth
            pending_mapping = request.env[MODEL_SLACK_USER_MAPPING].sudo().create({
                'slack_user_id': slack_user_id,
                'slack_team_id': conversation.slack_team_id,
                'slack_channel_id': channel,
                'slack_display_name': slack_info.get('display_name', ''),
                'slack_real_name': slack_info.get('real_name', ''),
                'slack_email': slack_info.get('email', ''),
                'state': 'pending',
                'user_id': request.env.ref('base.user_admin').id,  # Temporary
            })
        else:
            # Update with latest Slack info and set to pending for re-auth
            pending_mapping.write({
                'slack_channel_id': channel,
                'slack_display_name': slack_info.get('display_name', ''),
                'slack_real_name': slack_info.get('real_name', ''),
                'slack_email': slack_info.get('email', ''),
                'state': 'pending',  # Reset to pending for re-authentication
            })

        # Generate OAuth state token
        auth_token = pending_mapping.generate_oauth_state()

        # Create OAuth authorization URL
        oauth_url = f"{base_url}/slack/oauth/authorize?state={auth_token}&slack_user={slack_user_id}"

        # Return a structured message with a button
        return {
            'blocks': [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": _("🔐 *Connect your Odoo account*\n\nClick the button below to authorize your Odoo account and unlock all CRM features!")
                    }
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": _("Connect to Odoo"),
                                "emoji": True
                            },
                            "style": "primary",
                            "url": oauth_url,
                            "action_id": "oauth_connect"
                        }
                    ]
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": _("⏱️ This link will expire in 10 minutes")
                        }
                    ]
                }
            ],
            'text': _('🔐 Connect your Odoo account')  # Fallback text
        }

    def _handle_help_command(self, conversation):
        """
        Return help text with available commands.
        """
        # Check if authenticated
        is_authenticated = conversation.is_authenticated()

        # Build blocks for rich help message
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": _("📚 Slack CRM Bot - Help"),
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": _("*Connection Commands:*\n• `connect` - Link your Odoo account\n• `status` - Check your connection\n• `disconnect` - Unlink your account\n• `help` - Show this help")
                }
            }
        ]

        if is_authenticated:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": _("*CRM Commands (Spanish/English):*\n• `buscar/search/b/s <term>` - Search opportunities\n• `info/ver/i <OPP_ID>` - View details\n• `nota/note/n <OPP_ID> <msg>` - Add note\n• `mover/move/m <OPP_ID> <stage>` - Change stage\n\n*OPP_ID format:* OPP_123 (from search results)")
                }
            })

            blocks.append({
                "type": "divider"
            })

            # Add quick action buttons
            blocks.append({
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": _("🔍 Search Opportunities"),
                            "emoji": True
                        },
                        "value": "search",
                        "action_id": "quick_search"
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": _("📝 Add Note to Opportunity"),
                            "emoji": True
                        },
                        "value": "add_note",
                        "action_id": "quick_add_note_select"
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": _("🔄 Move Opportunity"),
                            "emoji": True
                        },
                        "value": "move_opportunity",
                        "action_id": "quick_move_opportunity"
                    }
                ]
            })

            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": _("💡 *Tip:* Search works with opportunity names, partner names, and emails!")
                    }
                ]
            })
        else:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": _("⚠️ *Connect your account to access CRM commands!*")
                }
            })

            blocks.append({
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": _("🔐 Connect Now"),
                            "emoji": True
                        },
                        "style": "primary",
                        "value": "connect",
                        "action_id": "quick_connect"
                    }
                ]
            })

        return {
            'blocks': blocks,
            'text': _('Slack CRM Bot Help')  # Fallback text
        }

    def _handle_status_command(self, slack_user_id, conversation):
        """
        Check and return user's connection status.
        """
        mapping = request.env[MODEL_SLACK_USER_MAPPING].sudo().search([
            ('slack_user_id', '=', slack_user_id)
        ], limit=1)

        if not mapping:
            return _("❌ Not connected. Type 'connect' to link your Odoo account.")

        if mapping.state == 'active':
            last_used = mapping.last_used
            if last_used:
                from datetime import datetime
                time_ago = datetime.now() - last_used
                days = time_ago.days
                hours = time_ago.seconds // 3600

                if days > 0:
                    last_used_text = _("%s days ago") % days
                elif hours > 0:
                    last_used_text = _("%s hours ago") % hours
                else:
                    last_used_text = _("recently")
            else:
                last_used_text = _("never")

            return _(
                "✅ **Connected**\n\n"
                "• Odoo User: %s\n"
                "• Email: %s\n"
                "• Last Activity: %s\n"
                "• Commands Used: %s\n"
            ) % (mapping.user_id.name, mapping.user_id.email, last_used_text, mapping.command_count)
        elif mapping.state == 'pending':
            return _("⏳ Authorization pending. Please complete the OAuth process.")
        else:
            return _("⚠️ Connection issue. Status: %s. Type 'connect' to reconnect.") % mapping.state

    def _handle_disconnect_command(self, slack_user_id, conversation):
        """
        Disconnect user's Odoo account.
        """
        mapping = request.env[MODEL_SLACK_USER_MAPPING].sudo().search([
            ('slack_user_id', '=', slack_user_id),
            ('state', '=', 'active')
        ], limit=1)

        if not mapping:
            return _("❌ You're not connected. Nothing to disconnect.")

        # Revoke access
        mapping.revoke_connection()

        # Clear conversation authentication
        conversation.write({'state': 'new', 'mapping_id': False})

        return _(
            "👋 **Disconnected successfully**\n\n"
            "Your Odoo account has been unlinked.\n"
            "Type 'connect' if you want to reconnect."
        )

    def _get_slack_user_info(self, slack_user_id):
        """
        Get Slack user information from API.
        """
        try:
            # Get bot token
            config = request.env[MODEL_RES_CONFIG_SETTINGS].sudo().get_slack_config()
            bot_token = config.get('bot_token')

            if not bot_token:
                _logger.error("No bot token for user info lookup")
                return {}

            # Call Slack API to get user info
            response = requests.get(
                'https://slack.com/api/users.info',
                headers={
                    'Authorization': f'Bearer {bot_token}',
                },
                params={
                    'user': slack_user_id
                },
                timeout=10
            )

            result = response.json()

            if result.get('ok'):
                user_data = result.get('user', {})
                profile = user_data.get('profile', {})
                return {
                    'display_name': profile.get('display_name') or profile.get('display_name_normalized', ''),
                    'real_name': profile.get('real_name') or profile.get('real_name_normalized', ''),
                    'email': profile.get('email', ''),
                    'team_id': user_data.get('team_id', ''),
                    'is_bot': user_data.get('is_bot', False),
                    'is_admin': user_data.get('is_admin', False),
                }
            else:
                _logger.error(f"Failed to get Slack user info: {result.get('error')}")
                return {}

        except Exception as e:
            _logger.error(f"Error getting Slack user info: {str(e)}")
            return {}

    def _execute_with_user_context(self, mapping, method, *args, **kwargs):
        """
        Execute a method with user context and proper error handling.
        Never uses sudo for business operations.
        """
        try:
            # First validate that user still has access
            if not mapping.validate_access():
                return _(
                    "⚠️ **Your access has expired or been revoked**\n\n"
                    "Please use `disconnect` and then `connect` to re-authenticate."
                )

            # Execute the method with user context
            return method(*args, **kwargs)

        except Exception as e:
            error_str = str(e)
            _logger.error(f"Permission/Access error for user {mapping.user_id.name}: {error_str}")

            # Detailed error handling
            if 'access' in error_str.lower() or 'permission' in error_str.lower():
                return _(
                    "🚫 **Permission Denied**\n\n"
                    "You don't have permission to perform this action.\n"
                    "Contact your Odoo administrator if you need access."
                )
            elif 'not found' in error_str.lower():
                return _("❌ Record not found or you don't have permission to view it.")
            elif 'read' in error_str.lower() and 'denied' in error_str.lower():
                return _("🚫 You don't have read permission for this module.")
            elif 'write' in error_str.lower() and 'denied' in error_str.lower():
                return _("🚫 You don't have write permission for this module.")
            elif 'create' in error_str.lower() and 'denied' in error_str.lower():
                return _("🚫 You don't have create permission for this module.")
            else:
                # Generic error but don't expose internal details
                return _(
                    "❌ **An error occurred**\n\n"
                    "This might be a permission issue or a system error.\n"
                    "Please try again or contact your administrator."
                )

    # CRM Command Handlers
    def _handle_search_command(self, parts, mapping):
        """
        Handle search command for CRM opportunities.
        Uses user's actual permissions through mapping.
        """
        if len(parts) < 2:
            return _("🔍 Usage: `buscar/search/b/s <term>` or just type anything to search")

        search_term = ' '.join(parts[1:])  # Join all terms into a single search phrase

        try:
            # Validate access first
            if not mapping.validate_access():
                return _("⚠️ Your access has expired. Please reconnect using `connect`")

            # Use the actual user's context, not sudo
            user = mapping.user_id
            lead_model = request.env[MODEL_CRM_LEAD].with_user(user)

            # Search for the complete phrase in opportunity name, partner name, and email
            domain = [
                ('type', '=', 'opportunity'),
                ('active', '=', True),
                '|', '|', '|',
                ('name', 'ilike', search_term),
                ('partner_id.name', 'ilike', search_term),
                ('partner_id.email', 'ilike', search_term),
                ('partner_id.parent_id.name', 'ilike', search_term)
            ]

            opportunities = lead_model.search(domain, limit=10, order='write_date desc')

            if not opportunities:
                return _("❌ No opportunities found for '%s'") % search_term

            # Build response with blocks for interactive buttons
            blocks = [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": _("🔍 *Found %s opportunities for '%s':*") % (len(opportunities), search_term)
                    }
                }
            ]

            # Get base URL for Odoo links
            base_url = request.env[MODEL_IR_CONFIG_PARAMETER].sudo().get_param(CONFIG_PARAM_WEB_BASE_URL)

            for opp in opportunities:
                # Use opportunity ID as token
                token = f"OPP_{opp.id}"

                # Format opportunity info
                partner_name = opp.partner_id.name if opp.partner_id else _('No partner')
                stage = opp.stage_id.name if opp.stage_id else _('No stage')
                revenue = _("€%s") % f"{opp.expected_revenue:,.2f}" if opp.expected_revenue else _("€0")

                # Get Odoo URL for this opportunity
                odoo_url = f"{base_url}/web#id={opp.id}&model=crm.lead&view_type=form"

                # Add opportunity section with text
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": _("📌 *%s*\n• Partner: %s\n• Stage: %s\n• Revenue: %s") % (opp.name, partner_name, stage, revenue)
                    }
                })

                # Add action buttons for this opportunity
                blocks.append({
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": _("📋 View Details"),
                                "emoji": True
                            },
                            "style": "primary",
                            "value": token,
                            "action_id": f"view_info_{token}"
                        },
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": _("👁️ View in Odoo"),
                                "emoji": True
                            },
                            "url": odoo_url,
                            "action_id": f"view_in_odoo_{token}"
                        },
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": _("📝 Add Note"),
                                "emoji": True
                            },
                            "value": token,
                            "action_id": f"add_note_{token}"
                        },
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": _("🔄 Move Stage"),
                                "emoji": True
                            },
                            "value": token,
                            "action_id": f"move_stage_{token}"
                        }
                    ]
                })

                # Add a divider between opportunities (except for the last one)
                if opp != opportunities[-1]:
                    blocks.append({"type": "divider"})

            # Update mapping activity
            mapping.update_last_activity('search')

            return {
                'blocks': blocks,
                'text': _("Found %s opportunities for '%s'") % (len(opportunities), search_term)  # Fallback text
            }

        except Exception as e:
            _logger.error(f"Error in search command: {str(e)}")

            # Check if it's a permission error
            if 'access' in str(e).lower() or 'permission' in str(e).lower():
                return _(
                    "⚠️ **Permission denied**\n\n"
                    "You don't have permission to access CRM opportunities.\n"
                    "Please contact your Odoo administrator."
                )

            return _("❌ Error searching opportunities: %s") % str(e)

    def _handle_info_command(self, parts, mapping):
        """
        Handle info command to show opportunity details.
        """
        if len(parts) < 2:
            return _("ℹ️ Usage: `info/ver <OPP_ID>` or `i <OPP_ID>` (e.g., `info OPP_42`)")

        token = parts[1]

        try:
            # Use the actual user's context
            user = mapping.user_id
            lead_model = request.env[MODEL_CRM_LEAD].with_user(user)

            # Extract ID from token format OPP_123
            try:
                if token.upper().startswith('OPP_'):
                    opp_id = int(token[4:])
                    opportunity = lead_model.browse(opp_id)
                    if not opportunity.exists():
                        opportunity = False
                else:
                    # Try to parse as direct ID
                    try:
                        opp_id = int(token)
                        opportunity = lead_model.browse(opp_id)
                        if not opportunity.exists():
                            opportunity = False
                    except ValueError:
                        opportunity = False
            except (ValueError, IndexError):
                opportunity = False

            if not opportunity:
                return _("❌ Opportunity not found: %s") % token

            # Build detailed response
            partner = opportunity.partner_id
            response = _(
                "📋 **Opportunity Details**\n\n"
                "**%s**\n"
                "• Odoo ID: `%s`\n"
                "• Stage: %s\n"
                "• Probability: %s%%\n"
                "• Expected Revenue: €%s\n"
                "• Expected Closing: %s\n"
            ) % (
                opportunity.name,
                token,
                opportunity.stage_id.name if opportunity.stage_id else _('No stage'),
                opportunity.probability,
                f"{opportunity.expected_revenue:,.2f}",
                opportunity.date_deadline or _('Not set')
            )

            if partner:
                response += _(
                    "\n**Partner Information:**\n"
                    "• Name: %s\n"
                    "• Email: %s\n"
                    "• Phone: %s\n"
                ) % (partner.name, partner.email or _('No email'), partner.phone or _('No phone'))

            if opportunity.user_id:
                response += _("\n**Salesperson:** %s\n") % opportunity.user_id.name

            if opportunity.tag_ids:
                tags = ', '.join(opportunity.tag_ids.mapped('name'))
                response += _("**Tags:** %s\n") % tags

            response += _("\n💡 Use `nota/note %s <message>` to add a note") % token

            # Update mapping activity
            mapping.update_last_activity('info')

            return response

        except Exception as e:
            _logger.error(f"Error in info command: {str(e)}")
            return _("❌ Error getting opportunity info: %s") % str(e)

    def _handle_note_command(self, parts, mapping):
        """
        Handle note command to add notes to opportunities.
        """
        if len(parts) < 3:
            return _("📝 Usage: `nota/note <OPP_ID> <message>` or `n <OPP_ID> <msg>` (e.g., `nota OPP_42 Call scheduled`)")

        token = parts[1]
        message = ' '.join(parts[2:])

        try:
            # Use the actual user's context
            user = mapping.user_id
            lead_model = request.env[MODEL_CRM_LEAD].with_user(user)

            # Extract ID from token format OPP_123
            try:
                if token.upper().startswith('OPP_'):
                    opp_id = int(token[4:])
                    opportunity = lead_model.browse(opp_id)
                    if not opportunity.exists():
                        opportunity = False
                else:
                    # Try to parse as direct ID
                    try:
                        opp_id = int(token)
                        opportunity = lead_model.browse(opp_id)
                        if not opportunity.exists():
                            opportunity = False
                    except ValueError:
                        opportunity = False
            except (ValueError, IndexError):
                opportunity = False

            if not opportunity:
                return _("❌ Opportunity not found: %s") % token

            # Use unified method to add note
            slack_user_info = {
                'slack_user_id': mapping.slack_user_id,
                'display_name': mapping.slack_display_name,
                'real_name': mapping.slack_real_name
            }

            success = self._add_note_to_opportunity(opportunity, message, slack_user_info)

            if not success:
                return _("❌ Error adding note to opportunity %s") % opportunity.name

            response = _(
                "✅ **Note added successfully!**\n\n"
                "Opportunity: %s\n"
                "Note: %s\n"
                "Added to: Chatter & Internal Notes"
            ) % (opportunity.name, message)

            # Update mapping activity
            mapping.update_last_activity('note')

            return response

        except Exception as e:
            _logger.error(f"Error in note command: {str(e)}")
            return _("❌ Error adding note: %s") % str(e)

    def _handle_move_command(self, parts, mapping):
        """
        Handle move command to change opportunity stage.
        """
        if len(parts) < 3:
            return _("📦 Usage: `mover/move <OPP_ID> <stage>` or `m <OPP_ID> <stage>` (e.g., `mover OPP_42 Won`)")

        token = parts[1]
        stage_name = ' '.join(parts[2:])

        try:
            # Use the actual user's context
            user = mapping.user_id
            lead_model = request.env[MODEL_CRM_LEAD].with_user(user)
            stage_model = request.env[MODEL_CRM_STAGE].with_user(user)

            # Extract ID from token format OPP_123
            try:
                if token.upper().startswith('OPP_'):
                    opp_id = int(token[4:])
                    opportunity = lead_model.browse(opp_id)
                    if not opportunity.exists():
                        opportunity = False
                else:
                    # Try to parse as direct ID
                    try:
                        opp_id = int(token)
                        opportunity = lead_model.browse(opp_id)
                        if not opportunity.exists():
                            opportunity = False
                    except ValueError:
                        opportunity = False
            except (ValueError, IndexError):
                opportunity = False

            if not opportunity:
                return _("❌ Opportunity not found: %s") % token

            # Find stage
            stage = stage_model.search([
                '|',
                ('name', 'ilike', stage_name),
                ('name', '=', stage_name)
            ], limit=1)

            if not stage:
                # List available stages
                stages = stage_model.search([])
                stage_list = '\n'.join([_("• %s") % s.name for s in stages])
                return _("❌ Stage '%s' not found.\n\nAvailable stages:\n%s") % (stage_name, stage_list)

            # Move to new stage
            old_stage = opportunity.stage_id.name if opportunity.stage_id else _('No stage')
            opportunity.write({'stage_id': stage.id})

            response = _(
                "✅ **Stage changed successfully!**\n\n"
                "Opportunity: %s\n"
                "From: %s\n"
                "To: %s\n"
            ) % (opportunity.name, old_stage, stage.name)

            # Update mapping activity
            mapping.update_last_activity('move')

            return response

        except Exception as e:
            _logger.error(f"Error in move command: {str(e)}")
            return _("❌ Error changing stage: %s") % str(e)

    def _add_note_to_opportunity(self, opportunity, note_text, slack_user_info):
        """
        Unified method to add a note to an opportunity.
        Adds to both chatter and internal notes field with consistent formatting.

        Args:
            opportunity: crm.lead record
            note_text: The note text to add
            slack_user_info: Dict with slack user information (slack_user_id, display_name, real_name)

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Add to chatter with emoji and prefix
            opportunity.message_post(
                body=_("📝 Note from Slack:\n%s") % note_text,
                message_type='comment',
                subtype_xmlid='mail.mt_note'
            )

            # Add to internal notes field
            current_notes = opportunity.description or ''

            # Use the mapped user's timezone (from opportunity context), not the HTTP request user
            user_tz = opportunity.env.user.tz or 'UTC'
            try:
                tz = pytz.timezone(user_tz)
                timestamp = datetime.now(tz).strftime('%Y-%m-%d %H:%M')
            except pytz.UnknownTimeZoneError:
                # Fallback to UTC if user's timezone is invalid
                timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')

            # Get the best available name for the user
            slack_user = (slack_user_info.get('real_name') or
                         slack_user_info.get('display_name') or
                         slack_user_info.get('slack_user_id', 'unknown'))

            # Format the new note entry
            new_note_entry = f"\n[{timestamp}] {note_text} (via slack from {slack_user})"

            # Update the internal notes field
            updated_notes = current_notes + new_note_entry if current_notes else new_note_entry.strip()
            opportunity.write({
                'description': updated_notes
            })

            return True

        except Exception as e:
            _logger.error(f"Error adding note to opportunity: {str(e)}")
            return False
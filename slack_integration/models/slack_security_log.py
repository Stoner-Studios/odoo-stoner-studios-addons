# -*- coding: utf-8 -*-
import logging
from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import AccessDenied

_logger = logging.getLogger(__name__)


class SlackSecurityLog(models.Model):
    """
    Security audit log for Slack integration.
    Tracks all API access attempts, security violations, and rate limiting.
    """
    _name = 'slack.security.log'
    _description = 'Slack Security Audit Log'
    _order = 'create_date desc'
    _rec_name = 'event_type'

    # Event identification
    event_type = fields.Selection([
        ('auth_success', 'Authentication Success'),
        ('auth_failed', 'Authentication Failed'),
        ('signature_invalid', 'Invalid Signature'),
        ('token_invalid', 'Invalid Token'),
        ('rate_limit', 'Rate Limit Exceeded'),
        ('replay_attack', 'Possible Replay Attack'),
        ('ip_blocked', 'IP Blocked'),
        ('permission_denied', 'Permission Denied'),
        ('suspicious_activity', 'Suspicious Activity'),
    ], string='Event Type', required=True, index=True)

    # Request details
    endpoint = fields.Char(string='Endpoint', index=True)
    http_method = fields.Char(string='HTTP Method')
    ip_address = fields.Char(string='IP Address', index=True)
    user_agent = fields.Text(string='User Agent')

    # Slack details
    slack_user_id = fields.Char(string='Slack User ID', index=True)
    slack_team_id = fields.Char(string='Slack Team ID', index=True)
    slack_channel_id = fields.Char(string='Slack Channel ID')

    # Security details
    signature_provided = fields.Char(string='Provided Signature')
    signature_expected = fields.Char(string='Expected Signature')
    timestamp_drift = fields.Integer(string='Timestamp Drift (seconds)',
                                     help='Difference between request timestamp and server time')

    # Response
    response_code = fields.Integer(string='Response Code')
    error_message = fields.Text(string='Error Message')

    # Additional data
    request_headers = fields.Text(string='Request Headers')
    request_body = fields.Text(string='Request Body (Sanitized)')
    additional_info = fields.Text(string='Additional Information')

    @api.model
    def log_security_event(self, event_type, **kwargs):
        """
        Log a security event with context information.
        """
        try:
            # Get request context if available
            if hasattr(self, 'env') and hasattr(self.env, 'context'):
                request_context = self.env.context
            else:
                request_context = {}

            # Create log entry
            log_data = {
                'event_type': event_type,
                'endpoint': kwargs.get('endpoint', ''),
                'http_method': kwargs.get('method', ''),
                'ip_address': kwargs.get('ip_address', ''),
                'user_agent': kwargs.get('user_agent', ''),
                'slack_user_id': kwargs.get('slack_user_id', ''),
                'slack_team_id': kwargs.get('slack_team_id', ''),
                'slack_channel_id': kwargs.get('slack_channel_id', ''),
                'signature_provided': kwargs.get('signature_provided', ''),
                'signature_expected': kwargs.get('signature_expected', ''),
                'timestamp_drift': kwargs.get('timestamp_drift', 0),
                'response_code': kwargs.get('response_code', 0),
                'error_message': kwargs.get('error_message', ''),
                'request_headers': kwargs.get('headers', ''),
                'request_body': kwargs.get('body', ''),
                'additional_info': kwargs.get('info', ''),
            }

            self.sudo().create(log_data)

            # Log to system logger for immediate visibility
            _logger.warning(_("🔒 Security Event: %s from IP %s") % (event_type, log_data['ip_address']))

        except Exception as e:
            _logger.error(f"Failed to log security event: {str(e)}")

    @api.model
    def check_rate_limit(self, ip_address, endpoint, limit_per_minute=30):
        """
        Check if IP has exceeded rate limit for endpoint.
        Returns True if within limit, raises AccessDenied if exceeded.
        """
        # Count requests in last minute
        one_minute_ago = datetime.now() - timedelta(minutes=1)
        recent_requests = self.sudo().search_count([
            ('ip_address', '=', ip_address),
            ('endpoint', '=', endpoint),
            ('create_date', '>', one_minute_ago.strftime('%Y-%m-%d %H:%M:%S'))
        ])

        if recent_requests >= limit_per_minute:
            # Log rate limit violation
            self.log_security_event(
                'rate_limit',
                ip_address=ip_address,
                endpoint=endpoint,
                error_message=_("Rate limit exceeded: %s/%s requests in last minute") % (recent_requests, limit_per_minute)
            )
            raise AccessDenied(_("Rate limit exceeded. Please try again later."))

        return True

    @api.model
    def is_ip_suspicious(self, ip_address):
        """
        Check if an IP has suspicious activity patterns.
        """
        # Check for recent security violations
        one_hour_ago = datetime.now() - timedelta(hours=1)
        violations = self.sudo().search_count([
            ('ip_address', '=', ip_address),
            ('event_type', 'in', ['auth_failed', 'signature_invalid', 'token_invalid', 'rate_limit']),
            ('create_date', '>', one_hour_ago.strftime('%Y-%m-%d %H:%M:%S'))
        ])

        # If more than 10 violations in last hour, consider suspicious
        return violations > 10

    @api.model
    def cleanup_old_logs(self, days=90):
        """
        Cleanup security logs older than specified days.
        Can be called by a scheduled action.
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        old_logs = self.sudo().search([
            ('create_date', '<', cutoff_date.strftime('%Y-%m-%d %H:%M:%S'))
        ])

        count = len(old_logs)
        old_logs.unlink()

        _logger.info(_("Cleaned up %s security log entries older than %s days") % (count, days))
        return count
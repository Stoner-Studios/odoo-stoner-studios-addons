# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError
from odoo.http import request
import logging
import time

_logger = logging.getLogger(__name__)

# Security constants
MAX_IMPERSONATE_ATTEMPTS = 5  # Maximum attempts per time window
RATE_LIMIT_WINDOW = 60  # Time window in seconds (1 minute)
IMPERSONATE_TIMEOUT = 3600  # Session timeout in seconds (1 hour)

# Action constants
ACTION_CLIENT_RELOAD = 'ir.actions.client'


class ResUsers(models.Model):
    _inherit = 'res.users'
    
    is_impersonated = fields.Boolean(
        string='Being Impersonated',
        compute='_compute_is_impersonated',
        help='True if this user is currently being impersonated'
    )
    
    def _compute_is_impersonated(self):
        """Check if user is currently being impersonated"""
        for user in self:
            user.is_impersonated = False
            if request and hasattr(request, 'session'):
                user.is_impersonated = (
                    request.session.get('impersonate_active', False) and
                    request.session.get('uid') == user.id
                )
    
    def action_impersonate(self):
        """Start impersonating this user with security controls"""
        self.ensure_one()

        # Validate request context
        if not request or not hasattr(request, 'session'):
            raise UserError(_('No active session available for impersonation'))

        # Security check: only system administrators can impersonate
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_('Only system administrators can impersonate users'))

        # Cannot impersonate yourself
        if self.id == self.env.uid:
            raise UserError(_('You cannot impersonate yourself'))

        # Cannot impersonate another admin (security measure)
        if self.has_group('base.group_system'):
            raise UserError(_('For security reasons, you cannot impersonate another administrator'))

        # Rate limiting: Check impersonation attempts
        attempts = request.session.get('impersonate_attempts', 0)
        last_attempt = request.session.get('impersonate_last_attempt', 0)
        current_time = time.time()

        if current_time - last_attempt < RATE_LIMIT_WINDOW:
            if attempts >= MAX_IMPERSONATE_ATTEMPTS:
                _logger.warning(
                    'Rate limit exceeded for user %s (ID: %s) trying to impersonate',
                    self.env.user.login, self.env.uid
                )
                raise UserError(_(
                    'Too many impersonation attempts. '
                    'For security, please wait %(seconds)s seconds before trying again.',
                    seconds=RATE_LIMIT_WINDOW
                ))
        else:
            # Reset counter after time window
            attempts = 0

        # Update rate limiting counters
        request.session['impersonate_attempts'] = attempts + 1
        request.session['impersonate_last_attempt'] = current_time

        # Get IP address for audit (handle proxies and Docker)
        ip_address = (
            request.httprequest.environ.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() or
            request.httprequest.environ.get('HTTP_X_REAL_IP') or
            request.httprequest.environ.get('REMOTE_ADDR') or
            'Unknown'
        )
        # Get reason from context (provided by wizard)
        reason = self.env.context.get('impersonate_reason', '')

        _logger.info('Impersonation START - IP: %s, Admin: %s, Target: %s, Reason: %s',
                     ip_address, self.env.user.login, self.login, reason or 'Not provided')

        # Log the impersonation with IP and reason (silent - no notification to user)
        self.env['user.impersonate.log'].create({
            'admin_user_id': self.env.uid,
            'target_user_id': self.id,
            'action': 'start',
            'ip_address': ip_address,
            'reason': reason,
        })

        # Store original user info and start time in session
        request.session['impersonate_original_uid'] = self.env.uid
        request.session['impersonate_original_login'] = self.env.user.login
        request.session['impersonate_active'] = True
        request.session['impersonate_target_login'] = self.login
        request.session['impersonate_target_uid'] = self.id
        request.session['impersonate_start_time'] = current_time

        # Change the session uid to the target user
        request.session.uid = self.id

        # CRITICAL: Clear cache and regenerate session token
        request.env.registry.clear_cache()
        from odoo.service import security
        request.session.session_token = security.compute_session_token(
            request.session, request.env
        )

        _logger.warning(
            'User %s (ID: %s) started impersonating user %s (ID: %s) from IP %s',
            self.env.user.login, self.env.uid, self.login, self.id, ip_address
        )

        # Force reload to apply new session
        return {
            'type': ACTION_CLIENT_RELOAD,
            'tag': 'reload',
            'params': {
                'menu_id': request.env.ref('base.menu_administration').id,
            },
        }
    
    @api.model
    def check_impersonation_status(self):
        """Check if current session is impersonating someone and enforce timeout"""
        if request and hasattr(request, 'session'):
            is_impersonating = request.session.get('impersonate_active', False)
            if is_impersonating:
                # Check for timeout
                start_time = request.session.get('impersonate_start_time', 0)
                current_time = time.time()
                elapsed = current_time - start_time

                if elapsed > IMPERSONATE_TIMEOUT:
                    # Timeout exceeded - automatically stop impersonation
                    _logger.warning(
                        'Impersonation timeout reached (%d seconds). Automatically stopping.',
                        IMPERSONATE_TIMEOUT
                    )
                    self.action_stop_impersonate()
                    return {
                        'is_impersonating': False,
                        'timeout': True,
                        'message': _('Impersonation session expired after %(minutes)s minutes',
                                   minutes=IMPERSONATE_TIMEOUT // 60)
                    }

                return {
                    'is_impersonating': True,
                    'original_user': request.session.get('impersonate_original_login', ''),
                    'target_user': request.session.get('impersonate_target_login', ''),
                    'original_uid': request.session.get('impersonate_original_uid'),
                    'target_uid': request.session.get('impersonate_target_uid', request.session.get('uid')),
                    'elapsed_time': int(elapsed),
                    'timeout_seconds': IMPERSONATE_TIMEOUT,
                }
        return {'is_impersonating': False}
    
    @api.model
    def action_stop_impersonate(self):
        """Stop impersonating and return to original user"""
        # Validate request context
        if not request or not hasattr(request, 'session'):
            raise UserError(_('No active session available'))

        if not request.session.get('impersonate_active'):
            return {'type': ACTION_CLIENT_RELOAD, 'tag': 'reload'}

        original_uid = request.session.get('impersonate_original_uid')
        original_login = request.session.get('impersonate_original_login')
        target_login = request.session.get('impersonate_target_login')
        target_uid = request.session.get('impersonate_target_uid', request.session.uid)

        # Get IP address for audit (handle proxies and Docker)
        ip_address = (
            request.httprequest.environ.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() or
            request.httprequest.environ.get('HTTP_X_REAL_IP') or
            request.httprequest.environ.get('REMOTE_ADDR') or
            'Unknown'
        )
        _logger.info('Impersonation STOP - IP: %s, Admin: %s, Target: %s',
                     ip_address, original_login, target_login)

        # Log the end of impersonation with IP
        self.env['user.impersonate.log'].sudo().create({
            'admin_user_id': original_uid,
            'target_user_id': target_uid,
            'action': 'stop',
            'ip_address': ip_address,
        })

        # Restore original uid
        request.session.uid = original_uid

        # Clean up all impersonate flags
        request.session.pop('impersonate_active', None)
        request.session.pop('impersonate_original_uid', None)
        request.session.pop('impersonate_original_login', None)
        request.session.pop('impersonate_target_login', None)
        request.session.pop('impersonate_target_uid', None)
        request.session.pop('impersonate_start_time', None)
        request.session.pop('impersonate_attempts', None)
        request.session.pop('impersonate_last_attempt', None)

        # CRITICAL: Clear cache and regenerate session token
        request.env.registry.clear_cache()
        from odoo.service import security
        request.session.session_token = security.compute_session_token(
            request.session, request.env
        )

        _logger.warning(
            'User %s stopped impersonating user %s from IP %s',
            original_login, target_login, ip_address
        )

        return {
            'type': ACTION_CLIENT_RELOAD,
            'tag': 'reload',
        }
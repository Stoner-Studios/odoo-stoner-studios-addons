# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request
from odoo.exceptions import AccessError, UserError
import logging

_logger = logging.getLogger(__name__)


class ImpersonateController(http.Controller):

    @http.route('/impersonate/status', type='json', auth='user')
    def get_impersonate_status(self):
        """Get current impersonation status - delegates to model method"""
        try:
            return request.env['res.users'].check_impersonation_status()
        except (AccessError, UserError) as e:
            _logger.error('Error checking impersonation status: %s', str(e))
            return {
                'success': False,
                'is_impersonating': False,
                'error': str(e)
            }

    @http.route('/impersonate/stop', type='json', auth='user')
    def stop_impersonate(self):
        """Stop impersonating and return to original user - delegates to model method"""
        if not request.session.get('impersonate_active'):
            return {'success': False, 'message': 'No active impersonation'}

        try:
            # Delegate to the model method to avoid code duplication
            action = request.env['res.users'].action_stop_impersonate()

            return {
                'success': True,
                'message': 'Impersonation stopped successfully',
                'reload': True,
                'action': action
            }

        except (AccessError, UserError, ValueError) as e:
            _logger.error('Error stopping impersonation: %s', str(e), exc_info=True)
            return {
                'success': False,
                'message': f'Error stopping impersonation: {str(e)}'
            }
        except Exception as e:
            _logger.critical('Unexpected error stopping impersonation: %s', str(e), exc_info=True)
            return {
                'success': False,
                'message': 'An unexpected error occurred. Please contact support.'
            }
    
    @http.route('/web/session/get_session_info', type='json', auth='user')
    def get_session_info_override(self):
        """Override session info to include impersonation data"""
        try:
            # Call the original method - now with auth='user' we have a valid user context
            info = request.env['ir.http'].session_info()
        except (ValueError, AttributeError) as e:
            _logger.error('Error getting session info: %s', str(e))
            # If there's an error, return basic info
            info = {
                'uid': request.session.uid if request.session else None,
                'is_system': False,
                'is_admin': False,
            }

        # Add impersonation info if available
        if request.session and request.session.get('impersonate_active'):
            info['impersonate_active'] = True
            info['impersonate_original_login'] = request.session.get('impersonate_original_login', '')
            info['impersonate_target_login'] = request.session.get('impersonate_target_login', '')

        return info
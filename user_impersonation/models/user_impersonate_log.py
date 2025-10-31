# -*- coding: utf-8 -*-

from odoo import api, fields, models


class UserImpersonateLog(models.Model):
    _name = 'user.impersonate.log'
    _description = 'User Impersonate Log'
    _order = 'create_date desc'
    _rec_name = 'create_date'
    
    admin_user_id = fields.Many2one(
        'res.users',
        string='Administrator',
        required=True,
        ondelete='cascade',
        help='Administrator who performed the impersonation'
    )
    
    target_user_id = fields.Many2one(
        'res.users',
        string='Impersonated User',
        required=True,
        ondelete='cascade',
        help='User that was impersonated'
    )
    
    action = fields.Selection([
        ('start', 'Start Impersonation'),
        ('stop', 'Stop Impersonation'),
    ], string='Action', required=True)

    ip_address = fields.Char(
        string='IP Address',
        help='IP address of the administrator performing the impersonation'
    )

    reason = fields.Text(
        string='Reason',
        help='Reason for the impersonation (for audit purposes)'
    )

    create_date = fields.Datetime(
        string='Date',
        readonly=True
    )
    
    duration = fields.Float(
        string='Duration (minutes)',
        compute='_compute_duration',
        store=True,
        help='Duration of the impersonation session in minutes'
    )
    
    @api.depends('action', 'create_date')
    def _compute_duration(self):
        """Calculate duration between start and stop actions"""
        for log in self:
            if log.action == 'stop':
                # Find the corresponding start log
                start_log = self.search([
                    ('admin_user_id', '=', log.admin_user_id.id),
                    ('target_user_id', '=', log.target_user_id.id),
                    ('action', '=', 'start'),
                    ('create_date', '<', log.create_date),
                ], order='create_date desc', limit=1)
                
                if start_log:
                    delta = log.create_date - start_log.create_date
                    log.duration = delta.total_seconds() / 60.0
                else:
                    log.duration = 0.0
            else:
                log.duration = 0.0
    
    def name_get(self):
        """Display format for the log entries"""
        result = []
        for log in self:
            name = f"{log.admin_user_id.name} → {log.target_user_id.name} ({log.create_date})"
            result.append((log.id, name))
        return result
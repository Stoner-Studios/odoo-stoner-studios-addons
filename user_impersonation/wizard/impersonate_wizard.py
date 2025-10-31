# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class ImpersonateWizard(models.TransientModel):
    _name = 'impersonate.wizard'
    _description = 'Impersonate User Wizard'

    user_id = fields.Many2one('res.users', string='User to Impersonate', required=True, readonly=True)
    reason = fields.Text(string='Reason for Impersonation', required=True,
                         help='Please provide a reason for this impersonation (for audit purposes)')

    def action_confirm(self):
        """Confirm and execute impersonation with reason"""
        self.ensure_one()
        return self.user_id.with_context(impersonate_reason=self.reason).action_impersonate()

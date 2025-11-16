# -*- coding: utf-8 -*-
{
    'name': 'Login As User (Secure Impersonation)',
    'version': '18.0.1.0.0',
    'category': 'Tools',
    'summary': 'Admin can login as any user with mandatory audit reasons and complete security trail',
    'description': """
        Login As User - Secure Impersonation for Odoo 18
        =================================================

        Allows system administrators to login as other users temporarily for support
        and debugging purposes, with complete audit trail and mandatory reasons.

        Features:
        ---------
        * Secure impersonation with multi-layer validation
        * Mandatory reason wizard for audit compliance
        * Rate limiting and session timeout (1 hour)
        * Visual indicators (banner and systray)
        * Complete audit logs with IP address tracking
        * Spanish translations included
    """,
    'author': 'Stoner Studios',
    'website': 'https://stonerstudios.com/en/',
    'maintainer': 'Stoner Studios',
    'support': 'support@stonerstudios.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'web',
    ],
    'data': [
        'security/ir_model.xml',
        'security/ir.model.access.csv',
        'wizard/impersonate_wizard_views.xml',
        'views/res_users_views.xml',
        'views/user_impersonate_log_views.xml',
    ],
    'images': [
        'static/description/banner.png',
    ],
    'assets': {
        'web.assets_backend': [
            'user_impersonation/static/src/css/impersonate.css',
            'user_impersonation/static/src/js/impersonate_warning.js',
            'user_impersonation/static/src/xml/impersonate_warning.xml',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}

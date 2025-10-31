# -*- coding: utf-8 -*-
{
    'name': 'Slack Integration',
    'version': '18.0.1.1.1',
    'category': 'Productivity/Integrations',
    'summary': 'Complete Slack integration for CRM opportunity management',
    'description': """
Slack Integration Module
========================

This module provides comprehensive Slack integration for CRM management, including:

* Slack bot with Direct Messages (DMs) for individual user authentication
* OAuth flow for connecting Slack users to their Odoo accounts
* Secure webhook endpoints with HMAC-SHA256 signature verification
* Rate limiting and comprehensive security audit logging
* User-specific permissions - all operations respect Odoo user permissions

Configuration:
--------------
Access the configuration menu at: Settings → Technical → Slack Integration
(Only accessible to system administrators for security reasons)

Features:
---------
* DM Bot Commands (available in English and Spanish, no slash commands needed):
  - connect - Link your Odoo account via OAuth
  - buscar/search/b/s <term> - Search CRM opportunities
  - info/ver/i <OPP_ID> - Get detailed opportunity information
  - nota/note/n <OPP_ID> <message> - Add notes to opportunities
  - mover/move/m <OPP_ID> <stage> - Change opportunity stages
  - status - Check your connection status
  - help - Get help with available commands

* Management Tools:
  - User Connections: Monitor all Slack-Odoo user mappings
  - Bot Conversations: Track active DM conversations
  - Security Log: Comprehensive audit trail (last 7 days by default, 45-day retention)

* Multilingual Support: Full translations in English and Spanish

Security:
---------
* HMAC-SHA256 signature verification (primary security mechanism)
* Timestamp verification to prevent replay attacks (5-minute window)
* Token validation (verification token and signing secret)
* Configurable rate limiting per IP address (300 commands/min, 600 interactive/min)
* Comprehensive security audit logging with automated cleanup
* Request validation and sanitization
* User-level permission enforcement (no sudo for business operations)

Perfect for teams that want to manage their CRM pipeline directly from Slack.
    """,
    'author': 'Stoner Studios',
    'website': 'https://stonerstudios.com',
    'maintainer': 'Stoner Studios',
    'support': 'support@stonerstudios.com',
    'depends': [
        'base',
        'mail',
        'crm',
    ],
    'data': [
        'security/ir_model.xml',
        'security/ir.model.access.csv',
        'security/ir_rules.xml',
        'data/ir_cron.xml',
        'views/slack_user_mapping_views.xml',
        'views/slack_conversation_views.xml',
        'views/slack_security_log_views.xml',
        'views/res_config_settings_views.xml',
        'views/oauth_templates.xml',
    ],
    'images': [
        'static/description/banner.png',
    ],
    'demo': [],
    'installable': True,
    'auto_install': False,
    'application': True,
    'license': 'LGPL-3',
}
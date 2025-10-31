# Slack Integration for Odoo CRM

Professional Slack integration module for Odoo CRM, developed by **Stoner Studios**.

**Version:** 18.0.1.0.0
**License:** LGPL-3
**Author:** Stoner Studios
**Compatible with:** Odoo 18.0

---

## 📋 Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Bot Commands](#bot-commands)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Security](#security)
- [Technical Architecture](#technical-architecture)
- [Development](#development)
- [Support](#support)

---

## Overview

This module provides a comprehensive Slack bot integration for Odoo CRM with enterprise-grade security, OAuth authentication, and user permission enforcement. Your team can search, view, and manage CRM opportunities directly from Slack DMs.

---

## Key Features

- **Slack Bot with Direct Messages**: Secure OAuth 2.0 authentication for individual users
- **Interactive Components**: Buttons and modals for enhanced user experience
- **Enterprise Security**: HMAC-SHA256 signature verification, rate limiting, and comprehensive logging
- **User Permissions**: All operations respect Odoo user permissions (no sudo abuse)
- **Configurable Settings**: Flexible rate limits and security options
- **Multilingual**: Supports 7 languages (English, Spanish, French, German, Portuguese BR, Italian, Dutch)
- **Audit Trail**: Complete security logging with analytics dashboard

---

## Bot Commands

Send these commands directly to your bot via DM. Commands are available in **English and Spanish**:

### Connection & Help
- `connect` - Link your Odoo account via OAuth
- `status` - Check your connection status
- `help` - Get help with available commands

### CRM Operations
- `buscar <term>` / `search <term>` / `b <term>` / `s <term>` - Search CRM opportunities
- `info <OPP_ID>` / `ver <OPP_ID>` / `i <OPP_ID>` - Get opportunity details
- `nota <OPP_ID> <message>` / `note <OPP_ID> <message>` / `n <OPP_ID> <msg>` - Add notes to opportunities
- `mover <OPP_ID> <stage>` / `move <OPP_ID> <stage>` / `m <OPP_ID> <stage>` - Change opportunity stages

**Note:** `<OPP_ID>` is the opportunity identifier in format `OPP_123` (where 123 is the Odoo opportunity ID). You get this ID when you search for opportunities.

---

## Installation

### 1. Install Module

1. Download the module from Odoo Apps marketplace
2. Place the `slack_integration` folder in your Odoo addons path
3. Update the Apps list in Odoo
4. Install the "Slack Integration" module

### 2. Create Slack App

1. Go to [https://api.slack.com/apps](https://api.slack.com/apps)
2. Click "Create New App" → "From scratch"
3. Enter App Name (e.g., "CRM Bot") and select your workspace
4. Click "Create App"

---

## Configuration

### Slack App Configuration

#### 1. OAuth & Permissions

Add these **Bot Token Scopes**:
- `chat:write` - Send messages as the bot
- `channels:read` - View basic channel information
- `im:history` - View messages in DMs
- `im:read` - View basic information about DMs
- `im:write` - Start DMs with users
- `users:read` - View users in workspace

#### 2. Event Subscriptions

1. Enable **Event Subscriptions**
2. Set **Request URL**: `https://your-odoo-domain.com/slack/events`
3. Subscribe to **bot events**:
   - `message.im` (Direct messages)
4. Click "Save Changes"

#### 3. Interactivity & Shortcuts

1. Enable **Interactivity**
2. Set **Request URL**: `https://your-odoo-domain.com/slack/interactive`
3. Click "Save Changes"

#### 4. OAuth & Installation

1. Go to **OAuth & Permissions**
2. Add **Redirect URL**: `https://your-odoo-domain.com/slack/oauth/authorize`
3. Click "Install to Workspace"
4. Copy the **Bot User OAuth Token** (starts with `xoxb-`)
5. Go to **Basic Information** → **App Credentials**
6. Copy the **Signing Secret**

### Odoo Configuration

1. Go to **Settings → Technical → Slack Integration** (accessible to system administrators)
2. Enable **Slack Integration**
3. Configure the following:
   - **Signing Secret**: Paste your signing secret (REQUIRED)
   - **Bot Token**: Paste your bot token (xoxb-...) (REQUIRED)
   - **Verification Token**: Optional, for backward compatibility
   - **Command Rate Limit**: Default 300 requests/minute
   - **Interactive Rate Limit**: Default 600 requests/minute
4. Click **Save**

**Note:** The Slack Integration menu is located in the Technical section to ensure only system administrators can manage the integration settings.

---

## Usage

### For End Users

1. Open Slack and find your bot in the "Apps" section
2. Open a Direct Message with the bot
3. Send the command `connect`
4. Click the OAuth link provided by the bot
5. Log in to Odoo (if not already logged in)
6. Your Slack account is now connected!
7. Start using commands like `search`, `info`, `note`, etc.

### For Administrators

**Monitor Connections:**
- Go to **Settings → Technical → Slack Integration → User Connections**
- View all Slack-Odoo user connections
- Activate or revoke access as needed

**Monitor Security:**
- Go to **Settings → Technical → Slack Integration → Security Log**
- View all requests, failures, and rate limiting events
- Filter by IP, user, status, or date
- Default view shows last 7 days of activity

**Track Conversations:**
- Go to **Settings → Technical → Slack Integration → Bot Conversations**
- See active conversations and message history
- Monitor conversation states

---

## Security

### Security Layers

1. **HMAC-SHA256 Signature Verification**
   - Every request from Slack is cryptographically verified
   - Primary security mechanism (recommended by Slack)

2. **Timestamp Verification**
   - Rejects requests older than 5 minutes
   - Prevents replay attacks

3. **Rate Limiting**
   - Configurable per IP address
   - Default: 300 commands/min, 600 interactions/min
   - Protects against abuse and DDoS

4. **OAuth 2.0 Flow**
   - Individual user authentication
   - CSRF protection with state tokens
   - 10-minute token expiration

5. **User Permission Enforcement**
   - All CRM operations use `.with_user(user)` pattern
   - No sudo abuse - respects Odoo permissions
   - Record rules ensure data isolation

6. **Comprehensive Audit Logging**
   - All requests logged with IP, user agent, headers
   - Security events tracked (failures, rate limits, etc.)
   - Automatic cleanup of logs >90 days

### Best Practices

- ✅ Always use HTTPS in production
- ✅ Keep tokens secure and never commit to version control
- ✅ Monitor security logs regularly
- ✅ Set appropriate rate limits for your usage
- ✅ Review user connections periodically
- ✅ Rotate signing secret if compromised

---

## Technical Architecture

### Main Models

#### 1. `slack.user.mapping`
Maps Slack users to Odoo users for OAuth authentication.

**Key Fields:**
- `slack_user_id` - Unique Slack ID
- `user_id` - Many2one to res.users
- `state` - Selection (pending, active, expired, revoked)
- `oauth_state_token` - Temporary token for OAuth flow
- `oauth_expires_at` - Token expiration (10 minutes)

#### 2. `slack.conversation`
Tracks DM conversations between bot and users.

**Key Fields:**
- `slack_user_id` - Slack user ID
- `channel_id` - DM channel ID
- `mapping_id` - Many2one to slack.user.mapping
- `state` - Selection (new, active, waiting, authenticated, idle)
- `last_command`, `last_message`, `last_response`

#### 3. `slack.security.log`
Complete security audit trail of all Slack requests.

**Key Fields:**
- `request_type` - Selection (event, command, interactive)
- `ip_address`, `user_agent`
- `request_headers`, `request_body`
- `status` - Success/failed
- `rate_limit_status`

### Controllers

#### 1. `/slack/events` (POST)
- Handles Slack Event Subscriptions API
- Processes DM messages to bot
- HMAC-SHA256 signature verification
- Rate limiting by IP

#### 2. `/slack/interactive` (POST)
- Handles Interactive Components (buttons, modals)
- Supports block_actions and view_submission
- Processes opportunity details, notes, stage changes

#### 3. `/slack/oauth/authorize` (GET)
- OAuth 2.0 flow for user authentication
- State token validation
- Links Slack user to Odoo account

### Security Implementation

```python
# HMAC-SHA256 Verification
sig_basestring = f"v0:{timestamp}:{request_body}"
my_signature = 'v0=' + hmac.new(
    signing_secret.encode(),
    sig_basestring.encode(),
    hashlib.sha256
).hexdigest()

# Timing-safe comparison
return hmac.compare_digest(my_signature, slack_signature)
```

### Cron Jobs

1. **Cleanup Expired OAuth States** - Every hour
2. **Cleanup Old Security Logs** - Daily (>90 days)
3. **Cleanup Idle Conversations** - Daily (>72 hours)

---

## Development

### File Structure

```
slack_integration/
├── __init__.py
├── __manifest__.py
├── controllers/
│   ├── __init__.py
│   ├── slack_bot.py          # Main bot controller (2,367 lines)
│   ├── slack_oauth.py         # OAuth flow
│   └── slack_frontend.py      # UI management
├── models/
│   ├── __init__.py
│   ├── slack_user_mapping.py
│   ├── slack_conversation.py
│   ├── slack_security_log.py
│   └── res_config_settings.py
├── views/
│   ├── slack_user_mapping_views.xml
│   ├── slack_conversation_views.xml
│   ├── slack_security_log_views.xml
│   ├── res_config_settings_views.xml
│   └── oauth_templates.xml
├── security/
│   ├── ir.model.access.csv
│   └── ir_rules.xml
├── data/
│   └── ir_cron.xml
├── i18n/
│   ├── es.po
│   ├── de.po
│   ├── fr.po
│   ├── it.po
│   ├── nl.po
│   └── pt_BR.po
└── static/
    └── description/
        ├── icon.png
        └── index.html
```

### Code Conventions

- **Logging**: Use `_logger.info/error/warning`
- **Method names**: `_handle_*_command`, `_open_*_modal`
- **User context**: Always use `.with_user(user)` for CRM operations
- **Security**: Never use `sudo()` for business logic
- **Timezone**: Use mapped user's timezone, not server timezone

### Testing Locally with ngrok

```bash
# Start Odoo
./odoo-bin -c odoo.conf

# Start ngrok
ngrok http 8069

# Configure Slack app with ngrok URL
Event Subscriptions: https://abc123.ngrok.io/slack/events
Interactive Components: https://abc123.ngrok.io/slack/interactive
OAuth Redirect: https://abc123.ngrok.io/slack/oauth/authorize
```

### Common Issues

**"Invalid signature"**
- Verify signing_secret in Settings
- Check server time synchronization

**"Opportunity not found"**
- Verify OPP_ID format (OPP_123)
- Check user has permission to view the opportunity

**"Permission denied"**
- User lacks Odoo CRM permissions
- Contact administrator

---

## Requirements

- **Odoo Version**: 18.0 or higher
- **Python**: 3.10+ (included with Odoo 18)
- **Dependencies**: base, mail, crm (all standard Odoo modules)
- **External**: None (no external Python packages required)
- **Slack**: Workspace with admin permissions to create apps

---

## Support

For support and questions:
- **Email**: support@stonerstudios.com
- **Website**: [https://stonerstudios.com](https://stonerstudios.com)

For bug reports or feature requests, please contact support with:
- Odoo version
- Module version
- Error logs (from Odoo and Security Logs)
- Steps to reproduce

---

## License

LGPL-3

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history and release notes.

---

**Developed by Stoner Studios** - Premium Odoo Solutions

Copyright © 2025 Stoner Studios

# User Impersonation for Odoo 18

Secure user impersonation module for Odoo 18 with mandatory audit reasons and comprehensive logging.

## Features

- 🔐 **Secure Impersonation**: Only system administrators can impersonate users
- 📝 **Mandatory Audit Reasons**: Wizard prompts for reason before each impersonation
- 🛡️ **Rate Limiting**: Maximum 5 attempts per minute
- ⏱️ **Session Timeout**: Automatic logout after 1 hour
- 📊 **Complete Audit Trail**: All sessions logged with IP address and reason
- 🎯 **Visual Indicators**: Banner and systray showing impersonation status
- 🌍 **Spanish Translations**: Full es_ES language pack included

## Installation

```bash
cd /path/to/odoo/addons
git clone -b 18.0 https://github.com/Stoner-Studios/odoo-stoner-studios-addons.git
# Restart Odoo
# Go to Apps → Update Apps List
# Search for "User Impersonation" → Install
```

## Usage

### Starting Impersonation

1. Navigate to **Settings → Users & Companies → Users**
2. Click the **"Impersonate User"** button (in form or list view)
3. **Enter a reason** for impersonation (mandatory for audit)
4. Click **Confirm**

### During Impersonation

- Orange banner at top shows impersonation status
- Systray indicator (top-right) provides quick access
- All actions performed as the impersonated user
- Session expires automatically after 1 hour

### Stopping Impersonation

Click **"Stop"** button in:
- Orange banner at top, or
- Systray indicator dropdown

### Viewing Audit Logs

**Settings → Technical → User Impersonation → Logs**

Each log includes:
- Administrator and target user
- Start/stop timestamps
- Session duration
- **Reason for impersonation**
- IP address

## Security

- **Permission Required**: `base.group_system` (Settings access)
- **Admin Protection**: Cannot impersonate other administrators
- **Self-Protection**: Cannot impersonate yourself
- **Rate Limiting**: 5 attempts per minute maximum
- **Session Timeout**: 1 hour automatic logout
- **IP Logging**: Full forensic tracking
- **Multi-Layer Validation**: Backend + frontend + ACL + business rules

## Configuration

Rate limiting and timeout settings can be configured in `models/res_users.py`:

- `MAX_IMPERSONATE_ATTEMPTS`: Maximum attempts per minute (default: 5)
- `RATE_LIMIT_WINDOW`: Time window in seconds (default: 60)
- `IMPERSONATE_TIMEOUT`: Session timeout in seconds (default: 3600)

## Technical Overview

### Architecture

**Backend:**
- Extended `res.users` model with impersonation methods
- `user.impersonate.log` model for audit trail
- `impersonate.wizard` for mandatory reason collection
- JSON endpoints for session management

**Frontend:**
- OWL components for reactive UI
- Real-time session status monitoring
- Responsive CSS design
- Systray integration

### Database Schema

The `user.impersonate.log` model stores:
- Administrator and target user references
- Start/stop timestamps and duration
- Mandatory reason text
- IP address for forensic analysis
- Active session status

### Security Implementation

**Multi-Layer Protection:**
1. Backend validation (permissions, user type, rate limits)
2. Frontend visibility controls
3. Access control lists (ACL)
4. Business logic validation

**Session Management:**
- Uses Odoo's built-in session mechanism
- Stores impersonation state in session
- Automatic timeout enforcement
- Secure token handling

## File Structure

```
user_impersonation/
├── __manifest__.py
├── controllers/main.py
├── models/
│   ├── res_users.py
│   └── user_impersonate_log.py
├── wizard/
│   ├── impersonate_wizard.py
│   └── impersonate_wizard_views.xml
├── views/
│   ├── res_users_views.xml
│   └── user_impersonate_log_views.xml
├── security/
│   ├── ir_model.xml
│   └── ir.model.access.csv
├── static/
│   ├── description/
│   └── src/
└── i18n/es_ES.po
```

## License

LGPL-3.0

## Author

**Stoner Studios**
Premium Odoo Development

- Email: support@stonerstudios.com
- Website: https://stonerstudios.com
- GitHub: https://github.com/Stoner-Studios

## Changelog

See [CHANGELOG.md](CHANGELOG.md)

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

**⚠️ Important**: Use responsibly and in compliance with privacy laws and company policies.

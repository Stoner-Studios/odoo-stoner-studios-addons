# Changelog

All notable changes to the Slack Integration for Odoo.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [18.0.1.1.1] - 2025-10-30

### Changed
- Improved marketplace page visual layout (reduced spacing between banner and content)
- Updated manifest images list to use banner.png
- Removed unused screenshot_config.png

## [18.0.1.1.0] - 2025-10-29

### Added
- Added `s` shortcut for search command (buscar/search/b/s)
- New marketplace banner and Slack interaction screenshot

### Changed
- Updated help command documentation to include new shortcuts
- Updated all user-facing documentation (README, HTML, translations)
- Improved Spanish translations with complete command shortcuts
- Moved configuration menu to Technical section for better admin control

### Improved
- Enhanced marketplace presentation with visual examples
- Better UX documentation with real usage screenshots

## [18.0.1.0.0] - 2025-10-23

### Initial Release

Complete Slack bot integration for Odoo CRM with enterprise-grade security.

#### Features

**Core Functionality**
- Slack bot with Direct Messages (no slash commands needed)
- OAuth 2.0 authentication - each user links their own Odoo account
- Search, view, and manage CRM opportunities from Slack
- Interactive buttons and modals for better UX
- Full user permission enforcement (all operations respect Odoo rights)

**Bot Commands** (English/Spanish)
- `connect` - Link your Odoo account
- `buscar/search/b/s <term>` - Search opportunities
- `info/ver/i <OPP_ID>` - View opportunity details
- `nota/note/n <OPP_ID> <message>` - Add notes
- `mover/move/m <OPP_ID> <stage>` - Change pipeline stage
- `status` - Check connection
- `help` - Show all commands

**Security**
- HMAC-SHA256 signature verification
- Timestamp verification (5-min window anti-replay)
- Configurable rate limiting (30 commands/min, 60 interactions/min)
- Comprehensive audit logging
- Request validation and sanitization

**Administration**
- User mapping management (Slack ↔ Odoo users)
- Connection state tracking
- Security event dashboard
- Automatic cleanup jobs (logs >90 days, expired OAuth states, idle conversations)

**Multilingual**
- 7 languages supported: English, Spanish, French, German, Portuguese (BR), Italian, Dutch
- Commands work in both English and Spanish

#### Technical

- **Odoo Version**: 18.0
- **Dependencies**: base, mail, crm (all standard Odoo modules)
- **External Dependencies**: None
- **License**: LGPL-3

---

**Developed by Stoner Studios**
Support: support@stonerstudios.com

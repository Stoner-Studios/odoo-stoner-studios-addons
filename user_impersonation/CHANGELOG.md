# Changelog

All notable changes to the User Impersonation module will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [18.0.1.0.0] - 2025-10-31

### Added
- Initial release for Odoo 18.0
- Secure user impersonation for system administrators
- Mandatory audit reason wizard before each impersonation
- Complete audit trail with session logging
- Rate limiting: Maximum 5 attempts per minute
- Automatic session timeout after 1 hour
- Visual indicators: Orange banner and systray icon
- Real-time session status monitoring
- IP address tracking for forensic analysis
- Multi-layer security validation (backend, frontend, ACL, business rules)
- Admin-to-admin impersonation protection
- Self-impersonation protection
- Spanish (es_ES) translations
- Responsive design for mobile and desktop
- OWL-based reactive UI components

### Security
- Permission-based access control (`base.group_system` required)
- Session token regeneration on start/stop
- Rate limiting enforcement
- Automatic session timeout
- Complete audit logging

### Technical
- Extended `res.users` model with impersonation methods
- New `user.impersonate.log` model for audit trail
- New `impersonate.wizard` for mandatory reason collection
- JSON endpoints for session management
- Systray integration
- Real-time session monitoring

---

**Note**: This is the initial stable release. Future versions will maintain backward compatibility within the 18.0.x.x.x version range.

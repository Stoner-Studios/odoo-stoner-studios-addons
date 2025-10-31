# Stoner Studios Odoo Addons

[![License: LGPL-3](https://img.shields.io/badge/License-LGPL%20v3-blue.svg)](https://www.gnu.org/licenses/lgpl-3.0)
[![Odoo Version](https://img.shields.io/badge/Odoo-18.0-714B67)](https://www.odoo.com/)

Premium Odoo modules developed and maintained by [Stoner Studios](https://stonerstudios.com).

This repository contains a collection of high-quality, production-ready Odoo modules designed to enhance your Odoo experience.

## Available Modules

| Module | Description | Status |
|--------|-------------|--------|
| [user_impersonation](./user_impersonation) | Secure user impersonation with mandatory audit reasons | ✅ Stable |
| [slack_integration](./slack_integration) | Complete Slack integration for CRM opportunity management | ✅ Stable |

## Installation

### Standard Installation

1. Clone this repository:
```bash
git clone https://github.com/Stoner-Studios/odoo-stoner-studios-addons.git
```

2. Add the repository path to your Odoo configuration:
```ini
[options]
addons_path = /path/to/odoo-stoner-studios-addons,/path/to/odoo/addons
```

3. Restart Odoo and update the app list

4. Install the desired modules from Apps menu

### Using Git Submodules

```bash
cd /path/to/your/odoo/custom/addons
git submodule add https://github.com/Stoner-Studios/odoo-stoner-studios-addons.git
```

## Version Compatibility

Each branch corresponds to an Odoo version:

- `18.0` - Compatible with Odoo 18.0 (current)
- `19.0` - Compatible with Odoo 19.0 (planned)

## Module Documentation

Each module has its own README with detailed documentation:

- **User Impersonation**: [user_impersonation/README.md](./user_impersonation/README.md)
- **Slack Integration**: [slack_integration/README.md](./slack_integration/README.md)

## Contributing

We welcome contributions! Here's how you can help:

1. **Report Issues**: Found a bug? [Open an issue](https://github.com/Stoner-Studios/odoo-stoner-studios-addons/issues)
2. **Suggest Features**: Have an idea? We'd love to hear it!
3. **Submit Pull Requests**:
   - Fork the repository
   - Create a feature branch (`git checkout -b feature/amazing-feature`)
   - Commit your changes (`git commit -m 'Add amazing feature'`)
   - Push to the branch (`git push origin feature/amazing-feature`)
   - Open a Pull Request

### Development Guidelines

- Follow [OCA guidelines](https://github.com/OCA/odoo-community.org/blob/master/website/Contribution/CONTRIBUTING.rst) for code quality
- Include tests for new features
- Update module CHANGELOG.md with your changes
- Ensure backwards compatibility within the same major version

## Support

### Commercial Support

Professional support, customizations, and priority bug fixes are available for businesses.

📧 Contact us at [support@stonerstudios.com](mailto:support@stonerstudios.com)

### Community Support

- **Issues**: [GitHub Issues](https://github.com/Stoner-Studios/odoo-stoner-studios-addons/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Stoner-Studios/odoo-stoner-studios-addons/discussions)

## License

Unless otherwise specified in individual modules, all modules in this repository are licensed under [LGPL-3](LICENSE).

Each module may have a different license - check the module's `__manifest__.py` file for details.

## About Stoner Studios

We specialize in developing high-quality Odoo modules and providing expert Odoo consulting services.

- 🌐 Website: [stonerstudios.com](https://stonerstudios.com)
- 📧 Email: [support@stonerstudios.com](mailto:support@stonerstudios.com)
- 🛍️ Odoo Apps Store: [Our Modules](https://apps.odoo.com/apps/modules/browse?author=Stoner%20Studios)

---

**Made with ❤️ by Stoner Studios**

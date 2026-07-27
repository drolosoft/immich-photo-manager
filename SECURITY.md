# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.4.x   | Yes       |
| < 1.4   | No        |

## Reporting a Vulnerability

If you discover a security vulnerability in immich-photo-manager, please report it responsibly:

1. **Email**: forge@drolosoft.com
2. **Subject**: `[SECURITY] immich-photo-manager — <brief description>`

Please include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact

We will acknowledge receipt within 48 hours and provide a timeline for a fix.

**Do not** open a public GitHub issue for security vulnerabilities.

## Security Considerations

- **API keys**: The plugin stores Immich API keys in environment variables or MCP configuration. Never commit real API keys to version control.
- **Network access**: The MCP server communicates only with the configured Immich instance. No data is sent to third parties.
- **Gallery files**: Generated HTML galleries embed thumbnails as base64. They contain no executable code beyond the gallery viewer UI.
- **No auto-delete**: The plugin never deletes photos without explicit user confirmation.

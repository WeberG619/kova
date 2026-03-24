# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 0.2.x   | :white_check_mark: |
| < 0.2   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability in NeverOnce, please report it responsibly.

**Email:** weber@bimopsstudio.com

**What to include:**
- Description of the vulnerability
- Steps to reproduce
- Potential impact

**Response timeline:**
- Acknowledgment within 48 hours
- Assessment and fix plan within 7 days
- Patch release within 14 days for confirmed vulnerabilities

Please do **not** open a public GitHub issue for security vulnerabilities.

## Security Design

NeverOnce is designed with security in mind:

- **Local-only storage** — all data stays in a local SQLite database, never transmitted externally
- **Zero dependencies** — no third-party code means no supply chain attack surface
- **No network access** — the library makes no outbound connections
- **File permissions** — database files inherit OS-level file permissions

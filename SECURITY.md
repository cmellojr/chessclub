# Security Policy

## Supported Versions

| Version | Supported |
|---|---|
| 0.1.x | ✅ Yes |

## Reporting a Vulnerability

**Please do not report security vulnerabilities via public GitHub Issues.**

If you discover a security issue (e.g. credential exposure, token leakage, unsafe file permissions), please report it privately by emailing:

**cmellojr@gmail.com**

Include in your report:

- A description of the vulnerability
- Steps to reproduce it
- Potential impact
- (Optional) A suggested fix

You will receive a response within 7 days. If the issue is confirmed, a fix will be released as soon as possible and you will be credited in the release notes (unless you prefer to remain anonymous).

## Scope

Security issues relevant to this project include:

- Exposure of stored credentials (`credentials.json`, `oauth_token.json`)
- Insecure file permissions on credential storage
- Token leakage through logs or error messages
- Authentication bypass

Issues with Chess.com's own platform or API should be reported directly to Chess.com.

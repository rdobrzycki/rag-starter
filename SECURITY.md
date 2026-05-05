# Security Policy

## Supported Versions

This project supports security fixes for the latest public release only.

| Version | Supported |
| --- | --- |
| Latest public release | Yes |
| `main` | Pre-release during the initial public launch window |
| Older releases | No |

During the initial launch window, `main` may contain unreleased hardening work.
Do not treat it as the supported stable release until a public version is
tagged.

## Reporting a Vulnerability

Please use GitHub private vulnerability reporting for security issues.

From the repository page:

1. Open the `Security` tab.
2. Select `Report a vulnerability`.
3. Share the affected version, reproduction steps, impact, and any suggested mitigation.

Do not open public issues, pull requests, or discussions for suspected
security vulnerabilities.

For regular bugs, usage questions, and feature requests, use the public issue
forms instead.

## Response Expectations

- Reports are handled on a best-effort basis.
- There is no SLA or guaranteed response window in v1.
- Fixes are prioritized for the latest public release.

## Release Gate

GitHub private vulnerability reporting must be enabled before the first public
push. If that reporting path is not enabled, the repository is not ready for
public release.

# Security Policy

MeSync is a private production repository. Treat source code, credentials,
configuration, deployment details, operational data, logs, backups, and legal
materials as confidential.

## Reporting

Report suspected vulnerabilities, leaked secrets, unsafe moderation behavior, or
payment/security incidents directly to the repository owner through the private
project channel. Do not disclose issues publicly.

## Handling Secrets

- Never commit `.env`, `.env.*`, runtime data, backups, tokens, API keys, payment
  secrets, bot tokens, session secrets, or production logs.
- Use `.env.example` only for non-secret placeholders.
- Rotate credentials immediately if a secret may have been exposed.

## Supported Version

| Version | Status |
| --- | --- |
| 1.0.x | Supported |

## Baseline Checks

Before pushing or releasing:

- Review staged files for secrets and production data.
- Run frontend builds for `web/` and `admin/`.
- Run focused backend tests for the changed subsystem.
- Confirm legal documents remain publicly available without authentication.

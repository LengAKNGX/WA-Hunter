# Hosted service

This directory contains the production WA Hunter web service currently used by
`lenga.com.cn`.

It intentionally uses only the Python standard library. The service provides:

- registration, login, CSRF protection, secure cookies, and private results;
- a bounded hunt form for two C++17 programs;
- a persistent SQLite queue with one background worker;
- multi-strategy generation and bounded counterexample minimization;
- downloadable reports and counterexamples;
- administrator-only ¥1 delivery confirmation.
- optional DeepSeek-assisted Oracle generation with mandatory administrator review.
- manual ¥1 payment claiming and administrator-confirmed delivery unlocking.

## Production requirements

- Linux with Python 3.12, G++ 13 or compatible, Firejail, systemd, and Nginx;
- a dedicated low-privilege `lenga-oj` account;
- writable `/opt/lenga-oj/data` and `/opt/lenga-oj-jobs` directories;
- the systemd restrictions in `lenga-oj.service`;
- HTTPS at the reverse proxy. Secure session cookies are enabled by default.
- a root-owned `/etc/wa-hunter/deepseek.env` (`0600`) loaded by systemd when AI Hunt is enabled.
- a private payment QR at `/etc/wa-hunter/payment/qr.png`, owned by `root:lenga-oj`
  with mode `0640`; it is served only through an authenticated, owned hunt route.

The AI path never treats generated code as ground truth automatically. It compiles the generated
Oracle inside the existing sandbox, pauses the task for administrator review, and only then allows
the deterministic differential-testing worker to run.

Do not run this as root and do not remove the Firejail, network, resource, or
filesystem restrictions. See `../SECURITY.md` and
`../docs/SERVER_DEPLOYMENT.md` before adapting the service.

The repository does not contain production databases, credentials, TLS keys,
administrator passwords, or server backups.

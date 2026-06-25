# Security

TavernMixer is designed for **trusted local or LAN** use.

## Before exposing to a network

1. Change `SECRET_KEY` in `.env` to a long random string.
2. Change the default admin password (`SEED_ADMIN_PASSWORD`) immediately after first login.
3. Keep `ALLOW_REGISTRATION=false` unless you want open sign-ups.
4. Do not bind to `0.0.0.0` on untrusted networks without a reverse proxy and TLS.
5. Passwords are stored as bcrypt hashes only — they cannot be recovered from the admin UI.

## Default credentials

On first run with an empty database:

| Variable | Default |
|----------|---------|
| `SEED_ADMIN_USERNAME` | `admin` |
| `SEED_ADMIN_PASSWORD` | `changeme` |

## CORS

Development mode allows broad CORS. Restrict origins in production via `config.py` / environment if needed.

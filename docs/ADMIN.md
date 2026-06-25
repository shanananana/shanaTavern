# Admin Guide

## Admin panel

URL: `/admin.html` (requires `is_admin` user)

- LLM connection status
- Create / list / delete users
- Create default characters and system ingredients

## Hidden ops page

URL: `/__tm/ops` (not linked from the UI; `noindex`)

Requires admin login. Features:

- Browse all users (aggregated by activity)
- View each user's chat sessions
- Read full message history across all users

Intended for self-hosted operators only. Do not expose this installation to untrusted networks without hardening (see [SECURITY.md](SECURITY.md)).

## CLI user management

Registration is off by default:

```bash
cd backend && source .venv/bin/activate
python ../scripts/add_user.py USERNAME PASSWORD [--nickname NAME] [--admin]
```

# TavernMixer

Local AI character chat platform — lightweight SillyTavern-style experience with FastAPI + vanilla HTML/JS.

**License:** [MIT](LICENSE)

## Features

- User accounts (registration can be disabled)
- 62 default characters with bundled AI-generated avatars
- Custom characters with full prompt fields (personality, scenario, lorebook, etc.)
- Ingredient library + recipes → one-click character generation
- Streaming chat via any OpenAI-compatible API (LM Studio, Ollama, vLLM…)
- Character import/export JSON, fork, favorites
- Mobile-friendly chat overlay
- Admin panel + optional hidden ops page for chat audit ([docs/ADMIN.md](docs/ADMIN.md))

## Requirements

- Python 3.10+
- An OpenAI-compatible LLM server (e.g. [LM Studio](https://lmstudio.ai/) on port 1234)

## Quick start

```bash
git clone <your-repo-url> TavernMixer
cd TavernMixer
cp .env.example .env
# edit .env — set LLM_BASE_URL and LLM_MODEL

cd backend
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Open **http://127.0.0.1:8787**

### Default admin (empty database only)

| Setting | Default |
|---------|---------|
| Username | `admin` |
| Password | `changeme` |

Configure via `.env`: `SEED_ADMIN_USERNAME`, `SEED_ADMIN_PASSWORD`. **Change the password after first login.**

### Add users (registration closed)

```bash
python scripts/add_user.py username password [--nickname NAME] [--admin]
```

Or use **Settings → Account management** when logged in as `ACCOUNT_MANAGER_USERNAME` (default: `admin`).

## Configuration

See [.env.example](.env.example). Key variables:

| Variable | Description |
|----------|-------------|
| `LLM_BASE_URL` | OpenAI-compatible API base URL |
| `LLM_MODEL` | Model name |
| `SECRET_KEY` | JWT signing key — change in production |
| `HOST` | Bind address (`127.0.0.1` local only, `0.0.0.0` for LAN) |
| `ALLOW_REGISTRATION` | `true` to allow public sign-up |

## Project layout

```
TavernMixer/
├── backend/           FastAPI app
├── frontend/          Static HTML/CSS/JS
├── data/
│   └── uploads/defaults/   Bundled character avatars (see docs/ASSETS.md)
├── scripts/add_user.py
├── docs/              ADMIN, SECURITY, ASSETS
├── start.sh           Foreground dev server
└── start-daemon.sh    Background server (+ optional ngrok)
```

## Security

Read [docs/SECURITY.md](docs/SECURITY.md) before exposing to LAN or the internet.

## Assets

Default character portraits are AI-generated and shipped with the repo. See [docs/ASSETS.md](docs/ASSETS.md).

## Background / LAN access

```bash
./start-daemon.sh
```

Optionally installs ngrok tunnel if `ngrok` is on PATH (no fixed domain in code).

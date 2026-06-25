# 安全说明 · Security

shanaTavern 面向**可信的本机 / 局域网**环境设计。

## 暴露到网络前

1. 将 `.env` 中的 `SECRET_KEY` 改为足够长的随机字符串。
2. 首次登录后立即修改默认管理员密码（`SEED_ADMIN_PASSWORD`）。
3. 保持 `ALLOW_REGISTRATION=false`，除非你需要开放注册（可能涉及内容审核与合规风险，请自行评估）。
4. 在不可信网络中不要裸奔绑定 `0.0.0.0`；建议使用反向代理 + HTTPS。
5. 密码仅以 bcrypt 哈希存储，管理后台无法查看明文。

## 默认凭据（空数据库首次启动）

| 变量 | 默认值 |
|------|--------|
| `SEED_ADMIN_USERNAME` | `admin` |
| `SEED_ADMIN_PASSWORD` | `changeme` |

## CORS

开发模式允许较宽的 CORS。生产环境可通过 `config.py` 或环境变量收紧来源。

## ngrok 公网隧道

- 需先在 [ngrok.com](https://ngrok.com/) 注册，并执行 `ngrok config add-authtoken <token>`（**不要**把 token 写进 `.env` 或 Git）
- 在 `.env` 中设 `ENABLE_NGROK=true` 后，由 `./start-daemon.sh` 启动隧道
- 免费版 URL 可能随重启变化；公网暴露等同于把整站开放给互联网，务必修改默认凭据并阅读上文安全项

---

shanaTavern is designed for **trusted local or LAN** use.

## Before exposing to a network

1. Change `SECRET_KEY` in `.env` to a long random string.
2. Change the default admin password (`SEED_ADMIN_PASSWORD`) immediately after first login.
3. Keep `ALLOW_REGISTRATION=false` unless you need open sign-ups (assess content moderation and compliance risks first).
4. Do not bind to `0.0.0.0` on untrusted networks without a reverse proxy and TLS.
5. Passwords are bcrypt hashes only — not recoverable from the admin UI.

## Default credentials (fresh install)

| Variable | Default |
|----------|---------|
| `SEED_ADMIN_USERNAME` | `admin` |
| `SEED_ADMIN_PASSWORD` | `changeme` |

## CORS

Development mode allows broad CORS. Restrict origins in production via `config.py` / environment if needed.

## ngrok public tunnel

- Sign up at [ngrok.com](https://ngrok.com/) and run `ngrok config add-authtoken <token>` once (never commit the token)
- Set `ENABLE_NGROK=true` in `.env`; `./start-daemon.sh` starts the tunnel
- Free-tier URLs may change on restart; exposing to the public internet requires changing default credentials and following the items above

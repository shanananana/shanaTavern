# 管理指南 · Admin Guide

## 管理后台

URL：`/admin.html`（需 `is_admin` 管理员账号）

- LLM 连接状态
- 创建 / 列表 / 删除用户
- 创建默认角色与系统配料

## 隐藏 ops 页

URL：`/__st/ops`（旧路径 `/__tm/ops` 会自动跳转；UI 无入口；`noindex`）

需管理员登录。功能：

- 按用户聚合浏览（按活跃度排序）
- 查看各用户的聊天会话
- 阅读全员完整消息记录

仅供自托管运维者使用。暴露到不可信网络前请先阅读 [SECURITY.md](SECURITY.md) 并做好加固。

## 命令行添加用户

注册默认关闭：

```bash
cd backend && source .venv/bin/activate
python ../scripts/add_user.py 用户名 密码 [--nickname 昵称] [--admin]
```

---

## Admin panel

URL: `/admin.html` (requires `is_admin` user)

- LLM connection status
- Create / list / delete users
- Create default characters and system ingredients

## Hidden ops page

URL: `/__st/ops` (legacy `/__tm/ops` redirects; not linked in UI; `noindex`)

Requires admin login:

- Browse all users (aggregated by activity)
- View each user's chat sessions
- Read full message history across all users

For self-hosted operators only. Harden before exposing to untrusted networks — see [SECURITY.md](SECURITY.md).

## CLI user management

Registration is off by default:

```bash
cd backend && source .venv/bin/activate
python ../scripts/add_user.py USERNAME PASSWORD [--nickname NAME] [--admin]
```

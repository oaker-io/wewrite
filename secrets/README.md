# WeWrite Secrets · 密钥集中管理

所有密钥**只在这个目录里本地存储**,永不入 git(见 `.gitignore` 第 1 行 `secrets/`)。对话里不再出现任何完整 key 值。

## 文件清单

| 文件 | 内容 | 被谁读 |
|------|------|--------|
| `keys.env` | 所有 API key / token,shell 格式 | install.sh 脚本 + `source` 到 shell |
| `wechat.json` | 微信 AppID + AppSecret(已经在 config.yaml 里存,这里做备份或单独用) | 直接读 config.yaml 已够 |

## keys.env 格式

```
# 行内注释:#
KEY_NAME=value_without_quotes

# 可以有空行,空格会被当成 value 一部分不要用
```

**加密选项(可选)**:如果你担心 Mac 本机其他用户能读,把 keys.env 用 `gpg` 加密成 keys.env.gpg。但默认 `chmod 600` 就够日常用。

## 每个 key 的用途 · 如何获取 · 如何轮换

### WECHAT_APPID / WECHAT_APPSECRET
- **用途**:`cli.py publish` 推草稿到微信公众号
- **位置**:`secrets/keys.env` + `config.yaml` 的 `wechat.appid` / `wechat.secret`(两处都可以,scripts 优先读 env)
- **哪里拿**:https://mp.weixin.qq.com → 开发 → 基本配置
- **轮换**:页面上点 "重置 AppSecret" → 复制到 keys.env

### GEMINI_API_KEY
- **用途**:图像生成 fallback 通道(`image.providers[1]`)
- **位置**:`secrets/keys.env` + `config.yaml` 的 `image.providers[1].api_key`
- **哪里拿**:https://aistudio.google.com/apikey
- **轮换**:Delete 旧 key,Create new → 复制到 keys.env(免费)

### POE_API_KEY
- **用途**:图像生成主通道(nano-banana-2)
- **位置**:`secrets/keys.env` + `config.yaml` 的 `image.providers[0].api_key`
- **哪里拿**:https://poe.com/api_key
- **轮换**:Poe 设置页撤销旧 key → 生成新 key → 复制到 keys.env

### MD2WECHAT_API_KEY
- **用途**:`--engine md2wx` 排版引擎(40 主题)
- **位置**:`~/.md2wx.json`(md2wx CLI 默认存这里)**或**环境变量 `MD2WECHAT_API_KEY`
- **哪里拿**:https://aipickgold.com 账号中心
- **轮换**:后台 revoke 旧 key → 新 key → `md2wx config set api-key <NEW>`

### DISCORD_BOT_TOKEN
- **用途**:Discord bot 登录 Discord
- **位置**:`launchctl setenv DISCORD_BOT_TOKEN <token>`(开机自动加载前要重新 setenv)
- **哪里拿**:https://discord.com/developers/applications → Bot → Reset Token
- **轮换**:Discord Developer Portal 页面 Reset → 重装 install.sh

### BARK_KEY(iPhone 推送)
- **用途**:`routine/notify.sh` 发推送
- **位置**:`launchctl setenv BARK_KEY <key>` + `secrets/keys.env`
- **哪里拿**:iPhone App Store 装 Bark app → 复制个人 URL 最后那串字符
- **轮换**:Bark app 里能重置 device key

## 使用

### 方式 1 · shell source

```bash
source secrets/keys.env
echo "$POE_API_KEY"
python3 somescript.py    # 脚本里 os.environ.get("POE_API_KEY")
```

### 方式 2 · 自动 source(推荐,加到 shell profile)

```bash
# ~/.zshrc 加一行:
[ -f /Users/mahaochen/wechatgzh/wewrite/secrets/keys.env ] && set -a && source /Users/mahaochen/wechatgzh/wewrite/secrets/keys.env && set +a
```

此后新开终端自动有 env 变量,任何脚本都能用。

### 方式 3 · launchd daemon

launchd 启动时不会自动 source,需要在 install 脚本里显式:

```bash
set -a; source secrets/keys.env; set +a
launchctl setenv DISCORD_BOT_TOKEN "$DISCORD_BOT_TOKEN"
launchctl setenv BARK_KEY "$BARK_KEY"
```

## 安全清单

- [x] `secrets/` 在 `.gitignore`
- [x] `config.yaml` 在 `.gitignore`
- [x] `~/.md2wx.json` 在 md2wx 自己的 gitignore
- [ ] `chmod 600 secrets/keys.env`(命令:`chmod 600 /Users/mahaochen/wechatgzh/wewrite/secrets/keys.env`)
- [ ] 如果共享 Mac 账号,考虑用 `gpg --symmetric keys.env` 加密

## 如果某个 key 泄露(过去的对话里贴过)

1. 立刻去对应服务后台 revoke / reset(见上面"轮换"步骤)
2. 把新 key 写到 `secrets/keys.env`
3. 所有 launchd daemon 重新加载(`launchctl setenv` 注入新值,或重跑 install.sh)

# wewe-rss · WeChat 公众号 → RSS 桥

把订阅的微信公众号文章转成 RSS,供 `scripts/fetch_kol.py` 每日凌晨抓。
本机 Docker 自建 · 不走付费数据 · 不走第三方公开服务。

## 一次性 setup(用户操作)

### 1. 装 Docker / OrbStack

推荐 **OrbStack**(轻量 + 启动快 + 不吃内存):
```bash
brew install orbstack
open -a OrbStack
```

或 Docker Desktop:`https://docker.com/products/docker-desktop`

装好验证:`docker --version`

### 2. 启动 wewe-rss

```bash
cd /Users/mahaochen/wechatgzh/wewrite/infra/wewe-rss
docker compose up -d
docker compose logs -f wewe-rss   # 看启动日志(Ctrl-C 退出 follow)
```

### 3. 扫码激活

1. 浏览器开 `http://localhost:4000`
2. 用 AUTH_CODE 登录(默认 `wewrite-zhichen-2026` · 见 docker-compose.yml)
3. 顶部「账号管理」→「新增」→ 用**你自己的微信扫码授权**
4. 授权完显示「已登录」即成功

⚠️ cookie 寿命 7-15 天 · 失效后 web UI 看到「登录失效」· 同样位置重扫一次即可。
fetch_kol.py 会在 cookie 失效时 push Discord 提醒。

### 4. 添加要订阅的公众号

1. web UI「公众号」→「新增」→ 搜公众号名(如「刘润」)
2. wewe-rss 自动解析出 biz_name(`__biz=MzI...==`)+ 文章列表
3. 每个公众号详情页有 RSS endpoint url:
   `http://localhost:4000/feeds/<biz_name>.rss`
4. 复制 url
5. 把 url 贴到 `wewrite/config/kol_list.yaml` 对应 KOL 的 `rss_url` 字段
6. 把 `status: pending` 改成 `status: active`

最后 8 + 7 = 15 个 KOL 全部 active 后,fetch_kol.py 会每天凌晨 03:00 自动拉。

## 维护

### 看状态
```bash
docker compose ps           # 容器状态
docker compose logs --tail=100 wewe-rss   # 最近 100 行日志
```

### 重启
```bash
docker compose restart wewe-rss
```

### 关停 / 卸载(数据保留)
```bash
docker compose down                # 停容器 · ./data 保留
docker compose down -v             # 停容器 + 删 ./data(慎)
```

### 升级镜像
```bash
docker compose pull
docker compose up -d
```

## 故障排查

| 现象 | 可能原因 | 解决 |
|---|---|---|
| `localhost:4000` 打不开 | 容器没起 | `docker compose ps` 看是否 running · 没起看 logs |
| 扫码后显示「登录失败」 | 微信限制(短期内换设备登录) | 等 1-2 小时再扫 |
| 公众号搜不到 | 公众号名打错 / wewe-rss 缓存问题 | 重启容器 · 或用更精确的全名 |
| RSS 为空 | KOL 最近没发文 / cookie 失效 | 看 web UI 状态 · 重扫码 |
| fetch_kol.py 抓 0 篇 | wewe-rss 没起 / RSS url 写错 | `curl http://localhost:4000/feeds/<biz>.rss` 自测 |

## 安全提醒

- **AUTH_CODE 改成强密码** · 默认值 `wewrite-zhichen-2026` 改成你的私密字串(改 `docker-compose.yml` 后 `docker compose up -d` 重启)
- 4000 端口**只绑 localhost** · 默认 docker compose 不暴露到 LAN(若要 LAN 访问需要改 ports)
- wewe-rss 持有你的 WeChat 登录态 · `./data/` 目录权限自己管好

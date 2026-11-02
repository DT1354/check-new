# 复用现有 Cloudflare Tunnel

前端由 Cloudflare Pages 直接托管，不经过服务器 Tunnel。Tunnel 只为本机
`127.0.0.1:8765` 的 API 增加一个独立 hostname，因此不会占用原项目端口，也不
需要再运行第二个 `cloudflared` 进程。

## Dashboard 管理的 Tunnel

进入 Cloudflare Zero Trust → Networks → Tunnels → 现有 Tunnel → Public
Hostnames，添加：

- Hostname：`api-checkin.example.com`
- Service type：HTTP
- URL：`localhost:8765`

## 本地配置文件管理的 Tunnel

先备份原配置，再把新规则放到最终 `http_status:404` 规则之前：

```yaml
ingress:
  - hostname: old-app.example.com
    service: http://localhost:原项目端口
  - hostname: api-checkin.example.com
    service: http://localhost:8765
  - service: http_status:404
```

修改后先验证，再重启：

```bash
sudo cp /etc/cloudflared/config.yml /etc/cloudflared/config.yml.bak
cloudflared tunnel ingress validate
sudo systemctl restart cloudflared
```

不要删除或改变原项目的 hostname/service。API 服务只监听回环地址，公网入口由
Cloudflare TLS 与 Tunnel 提供。

## Pages

在 Cloudflare Pages 连接 GitHub 仓库：

- Root directory：`frontend`
- Build command：`npm run build`
- Build output directory：`dist`
- 环境变量：`VITE_API_BASE_URL=https://api-checkin.example.com`

为 Pages 绑定 `checkin.example.com`，并把服务器
`FRONTEND_ORIGIN` 精确设置为 `https://checkin.example.com`。前端和 API 应使用
同一个主域名下的两个子域名，便于 Secure、SameSite Cookie 正常工作。

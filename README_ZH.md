# VPS 搭建与终极防漏自动化技能 (`vps-setup`)

[English](README.md) | **中文版**

---

专为 AI 开发者工作流（Claude、OpenAI、Gemini、Cursor）打造的高可靠 Linux VPS 自动化部署与本机终极防漏加固技能。在保留服务端长连接稳定与 WARP 分流强项的基础上，补齐无 `DIRECT` 策略锁死、海外 DoH 优先、每日自动更新白名单、模式 A/B 链式代理、iOS 小火箭 `.conf`、系统防火墙断网开关（`clash-guard`）与真 TUN 验收门禁。

## 核心特性

1. **Xray VLESS Reality 搭建与服务端防断流**：
   * 锁定 **Xray v26.6.27** 并配置 `"minClientVer": ""` 与 `www.apple.com` SNI，确保与 Mihomo / Clash Verge Rev 100% 兼容。
   * 缩短 `net.ipv4.tcp_keepalive_time` 至 30 秒，设置 Xray `connIdle` 为 1800 秒，开启 BBR，全局禁用 VPS IPv6 并阻断 UDP 443（QUIC）。
   * 内置运行在 `40000` 端口的 Cloudflare WARP 代理，用于 Google / Gemini 区域容灾分流。
2. **零回落终极防漏 Clash Verge 配置（支持模式 A / 模式 B）**：
   * **策略组彻底移除 `DIRECT`**：所有代理选择组均不含 `DIRECT`，节点失效即断网，杜绝回落或误触直连。
   * **海外 DNS 优先（`respect-rules: true`）**：主 `nameserver` 走经海外代理组转发的 DoH（`cloudflare-dns.com`、`1.1.1.1`、`dns.google`）；`nameserver-policy` 中 `geosite:geolocation-!cn` 优先于国内规则。
   * **每日自动更新白名单与完整防漏规则**：引入 `Loyalsoldier/clash-rules`（`direct.txt`、`cncidr.txt`），补齐 `100.64.0.0/10`、B 站 `mirrorakam`、微信直连、`claudemcpclient.com` 与全量遥测域名；拦截 IPv6（`IP-CIDR6,::/0,REJECT`）与 WebRTC STUN 端口（`3478`、`5349`、`19302`）。
   * **模式 B 链式代理（`dialer-proxy`）**：支持以 VPS 为高速跳板串联静态住宅 SOCKS5 落地，自动注入防死循环规则并关闭住宅代理 UDP。
3. **iOS 小火箭防漏配置 + 多平台支持**：
   * 同步输出 iOS Shadowrocket 专用 `.shadowrocket.conf`（`FINAL,PROXY` + `Loyalsoldier/surge-rules` + 禁用 IPv6 + `no-resolve`）。
   * VPS `24480` 端口同时提供 `clash.yaml` 与 `shadowrocket.conf` HTTP 订阅，并输出标准 `vless://` 分享链接。
4. **跨平台按需自动设防断网开关（`scripts/setup_killswitch.py`）**：
   * 在 `deploy_vps.py` 部署并生成配置后默认自动调用（携带 `--skip-backup`，可用 `--no-killswitch` 跳过）：自动生成桌面 `断网急救.txt` 并安装系统级断网防火墙（Windows 下自动拉起 UAC 提权安装防火墙规则与 `local.clash-guard` 任务；macOS 下安装 `pf` `com.apple/clash-guard` + `launchd`）。采用三态机制：**开机未开 TUN 时正常直连上网 → 开启 TUN 即自动 0ms 设防（同步禁 IPv6 与路由器 53/853 DNS 泄漏）→ 异常掉线保持锁死 → 电脑重启自动归零**。**绝不修改任何 Clash Verge 订阅文件（`profiles/` 与 `profiles.yaml`）**。
5. **只读 11 项防漏实测门禁（`scripts/verify_environment.py`）**：
   * 校验 YAML 静态配置、无代理环境变量真 TUN 接管（等效 `curl --noproxy '*'`）、国内直连、海外与遥测出口一致性、真实 `1.1.1.1/cdn-cgi/trace` + DoH + `isp.ac/dns-leak-test` 检测及断网开关就绪度审计。

## 仓库结构

```
├── SKILL.md                              # Antigravity 技能定义文件
├── README.md                             # 英文文档
├── README_ZH.md                          # 中文文档
├── LICENSE                               # MIT 开源许可证
├── .gitignore                            # 敏感配置文件 Git 忽略文件
├── scripts/
│   ├── deploy_vps.py                     # 基于 SSH 的全自动远程部署脚本（支持模式 A/B）
│   ├── vps_setup.sh                      # 远程 VPS 初始化静默脚本
│   ├── generate_clash_config.py          # 本地 Clash YAML 与 Shadowrocket .conf 生成器
│   ├── setup_killswitch.py               # 本机只读体检、备份还原与断网防火墙管理工具
│   └── verify_environment.py             # 只读 11 项防漏验证门禁检测脚本
└── templates/
    ├── clash_profile.yaml.template       # 终极防漏 Clash Verge 配置模板
    ├── shadowrocket.conf.template        # iOS Shadowrocket 防漏配置模板
    └── xray_server.json.template         # Xray 服务端配置模板
```

## 快速开始

### 选项 1：AI Agent 调用（推荐）

在 Antigravity、Cursor 或 Claude Code 的对话框中输入以下指令：

> "我新买了一台海外 VPS，IP 是 `x.x.x.x`，端口是 `xxxx`，密码是 `xxxx`，请用 vps-setup 技能帮我完成节点的配置。"

（若需「VPS 跳板 + 静态住宅 SOCKS5 落地」模式 B，也可以直接发送：）
> "我新买了一台海外 VPS（IP `x.x.x.x`，端口 `xxxx`，密码 `xxxx`）和一颗静态住宅 SOCKS5（IP `y.y.y.y`，端口 `1080`，账号 `user`，密码 `pass`），请用 vps-setup 模式 B 帮我完成配置。"

Agent 会读取 `SKILL.md`，连接到新 VPS，执行初始化，输出无 `DIRECT` 回落的 Clash Verge YAML、iOS 小火箭 `.shadowrocket.conf`，并在 TUN 已开启时自动启用系统断网防火墙。

### 选项 2：本地命令行执行

在终端中直接运行部署脚本（默认模式 A，并自动启用系统级断网防火墙；加 `--no-killswitch` 可跳过）：

```bash
python scripts/deploy_vps.py \
  --host <VPS_IP> \
  --port <SSH_PORT> \
  --user root \
  --password "<PASSWORD>" \
  --node-name "US-Residential-Node" \
  --output "US-Residential-Node.yaml"
```

本机断网防火墙手动管理（可选独立执行）：

```bash
# 只读环境体检
python scripts/setup_killswitch.py --action audit

# 备份配置并生成桌面「断网急救.txt」
python scripts/setup_killswitch.py --action backup

# 确认 TUN 已开启后手动安装系统断网开关（需管理员/sudo 权限）
python scripts/setup_killswitch.py --action install-killswitch --skip-backup
```

## 客户端导入指南

* **Windows / macOS (Clash Verge Rev)**：打开配置管理（Profiles），将生成的 `.yaml` 文件拖入窗口；使用时直接选择对应订阅并开启 **TUN 模式** 按钮即可（无需设置 Clash Verge 开机自启，可自由控制客户端启停），同时确保设置中 **DNS 覆写** 与 **IPv6** 开关处于关闭状态。
* **Android (Clash Meta for Android)**：进入配置 -> 新配置 -> 从 URL 导入，输入 `http://<VPS_IP>:24480/clash.yaml`。
* **iOS (Shadowrocket / Sing-box / Loon)**：先复制生成的 `vless://` 链接导入节点并选中，再导入生成的 `.shadowrocket.conf`（或 `http://<VPS_IP>:24480/shadowrocket.conf`）点击使用配置，首页保持「全局路由 = 配置」。

## 门禁验证检测

验证网络纯净度与防泄露性能（只读 11 项验收）：

```bash
python scripts/verify_environment.py --config US-Residential-Node.yaml --proxy http://127.0.0.1:7897
```

## 许可证

MIT 许可证

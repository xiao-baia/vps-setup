# VPS 搭建自动化技能 (`vps-setup`)

[English](README.md) | **中文版**

---

专为 AI 开发者工作流（Claude、OpenAI、Gemini、Cursor）配置高可靠 Linux VPS 节点并生成配套 Clash Verge / Mihomo 配置文件的自动化技能。

## 核心特性

1. **Xray VLESS Reality 搭建**：
   * 锁定 **Xray v26.6.27** 并配置 `"minClientVer": ""`，确保与 Mihomo 和 Clash Verge Rev 100% 兼容。
   * SNI 配置为 `www.apple.com`，避免超大 TLS 证书链引起的数据包分片丢包。
2. **内核级调优**：
   * 将 `net.ipv4.tcp_keepalive_time` 缩短至 30 秒，并将 Xray `connIdle` 配置为 1800 秒，消除长时间 AI 推理流中的 Broken Pipe 断连问题。
   * 开启 BBR 拥塞控制并在 VPS 全局禁用 IPv6，防止物理位置和 DNS 泄露。
3. **全维防泄露 Clash Verge / Shadowrocket 配置文件生成**：
   * 生成 1:1 结构对齐生产标准的 `.yaml` 与 `.conf` 配置文件，策略组移除 `DIRECT` 防误切。
   * 采用 Fake-IP（`198.18.0.0/16`）与默认经代理转发的海外 DoH（`1.1.1.1` / `8.8.8.8`），仅国内白名单与内网走阿里/腾讯 DoH。
   * 规则顶层拦截 IPv6（`IP-CIDR6,::/0,REJECT,no-resolve`），将内网保留地址（`private` / `lan` / `100.64.0.0/10`）与 B 站 CDN（`mirrorakam`）排在 `STUN` 端口与 `geolocation-!cn` 之前，并每日自动更新 `Loyalsoldier/clash-rules`。
4. **分平台防泄漏适配**：
   * **Windows**：主动检测并关闭 Windows SMHNR（`DisableSmartNameResolution = 1`），同时在桌面生成一键复原脚本 `复原Windows-SMHNR.bat`；配合新版 Mihomo `strict-route: true` 的 WFP 自动拦截公网 IPv6 旁路。
   * **macOS**：不主动修改系统网络设置；明确告知 macOS 无需关 SMHNR，并提示用户可自行检查 `scutil --dns` 及按需决定是否调整 Wi-Fi IPv6 模式。
5. **双轨出站路由与多平台支持**：
   * 默认采用原生住宅 IP 直连出站，内置端口 `40000` 的 Cloudflare WARP 作为热备。
   * 自动生成桌面端 `.yaml`、iOS `.conf` 与 `vless://` 链接，并在 `24480` 端口提供 HTTP 订阅服务。

## 仓库结构

```
├── SKILL.md                          # Antigravity 技能定义文件
├── README.md                         # 英文文档
├── README_ZH.md                      # 中文文档
├── LICENSE                           # MIT 开源许可证
├── .gitignore                        # 敏感配置文件 Git 忽略文件
├── scripts/
│   ├── deploy_vps.py                 # 基于 SSH 的全自动远程部署运行脚本
│   ├── vps_setup.sh                  # 远程 VPS 初始化静默脚本
│   ├── generate_clash_config.py      # 本地 YAML & Shadowrocket .conf 生成器
│   ├── windows_smhnr.py              # Windows SMHNR 检测/关闭/复原工具
│   └── verify_environment.py         # 端到端防泄漏实测门禁脚本（含真实 DNS/IPv6 检测）
└── templates/
    ├── clash_profile.yaml.template   # Clash Verge 客户端配置模板
    └── xray_server.json.template     # Xray 服务端配置模板
```

## 快速开始

### 选项 1：AI Agent 调用（推荐）

在 Antigravity、Cursor 或 Claude Code 的对话框中输入以下指令：

> "我新买了一台海外 VPS，IP 是 `x.x.x.x`，端口是 `xxxx`，密码是 `xxxx`，请用 vps-setup 技能帮我完成节点的配置。"

### 选项 2：本地命令行执行

```bash
python scripts/deploy_vps.py \
  --host <VPS_IP> \
  --port <SSH_PORT> \
  --user root \
  --password "<PASSWORD>" \
  --node-name "US-Residential-Node" \
  --output "US-Residential-Node.yaml"
```

## 门禁验证检测

开启 Clash Verge TUN 模式后直接运行（自动绕过代理环境变量，实测出口、DNS 泄露与 IPv6 阻断）：

```bash
python scripts/verify_environment.py
```

## 许可证

MIT 许可证

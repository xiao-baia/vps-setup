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
   * 开启 BBR 拥塞控制并在系统全局禁用 IPv6，防止物理位置和 DNS 泄露。
3. **全维防泄露 Clash Verge 配置文件生成**：
   * 生成 1:1 结构对齐生产标准的配置文件。
   * 采用 Fake-IP（`198.18.0.0/16`）与国内安全 DoH 引导，并配合通过代理转发的 Cloudflare DoH 作为 Fallback 兜底。
   * 捕获 WebRTC STUN 端口（`3478`、`5349`、`19302`）并丢弃所有 IPv6 流量（`IP-CIDR6,::/0,REJECT`）。
4. **双轨出站路由**：
   * 默认采用原生住宅 IP 直连出站（零人机验证码、最低延迟）。
   * 内置运行在 `40000` 端口的 Cloudflare WARP 代理作为静默热备，用于容灾分流。
5. **多平台支持**：
   * 自动生成桌面端本地 YAML 配置文件。
   * 在 `24480` 端口提供轻量级 HTTP 订阅服务，用于 Android 端 Clash Meta 导入。
   * 输出适用于 iOS（Shadowrocket、Sing-box、Loon）的标准 `vless://` 分享链接。

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
│   ├── generate_clash_config.py      # 本地 YAML 配置文件生成器
│   └── verify_environment.py         # 端到端验证门禁检测脚本
└── templates/
    ├── clash_profile.yaml.template   # Clash Verge 客户端配置模板
    └── xray_server.json.template     # Xray 服务端配置模板
```

## 快速开始

### 选项 1：AI Agent 调用（推荐）

在 Antigravity、Cursor 或 Claude Code 的对话框中输入以下指令：

> "我新买了一台海外 VPS，IP 是 `x.x.x.x`，端口是 `xxxx`，密码是 `xxxx`，请用 vps-setup 技能帮我完成节点的配置。"

Agent 会读取 `SKILL.md`，连接到新 VPS，执行初始化，并输出 Clash Verge YAML 配置文件。

### 选项 2：本地命令行执行

在终端中直接运行部署脚本：

```bash
python scripts/deploy_vps.py \
  --host <VPS_IP> \
  --port <SSH_PORT> \
  --user root \
  --password "<PASSWORD>" \
  --node-name "US-Residential-Node" \
  --output "US-Residential-Node.yaml"
```

## 客户端导入指南

* **Windows / macOS (Clash Verge Rev)**：打开配置管理（Profiles），将生成的 `.yaml` 文件拖入窗口，右键点击选择使用（Use），并开启 TUN 模式。
* **Android (Clash Meta for Android)**：进入配置 -> 新配置 -> 从 URL 导入，输入 `http://<VPS_IP>:24480/clash.yaml`。
* **iOS (Shadowrocket / Sing-box / Loon)**：复制生成的 `vless://` 链接，打开应用即可自动识别添加。

## 门禁验证检测

验证网络纯净度与防泄露性能：

```bash
python scripts/verify_environment.py --proxy http://127.0.0.1:7897
```

## 许可证

MIT 许可证

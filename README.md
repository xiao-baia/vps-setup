# VPS Setup Automation Skill (`vps-setup`)

[English Version](#english-version) | [中文版本](#中文版本)

---

<a name="english-version"></a>
## English Version

A specialized automation skill for configuring high-reliability Linux VPS endpoints and generating matching Clash Verge / Mihomo profiles for AI developer workflows (Claude, OpenAI, Gemini, Cursor).

### Key Features

1. **Xray VLESS Reality Setup**:
   * Pinned to **Xray v26.6.27** with `"minClientVer": ""` to ensure 100% compatibility with Mihomo and Clash Verge Rev.
   * SNI configured to `www.apple.com` to prevent packet fragmentation caused by oversized TLS certificate chains.
2. **Kernel-Level Tuning**:
   * Shortens `net.ipv4.tcp_keepalive_time` to 30s and configures Xray `connIdle` to 1800s to eliminate Broken Pipe disconnects during extended AI reasoning streams.
   * Enables BBR congestion control and disables IPv6 system-wide to avoid location leaks.
3. **Leak-Proof Clash Verge Profile Generation**:
   * Generates a 1:1 structured profile matching production standards.
   * Employs Fake-IP (`198.18.0.0/16`) and domestic DoH bootstrap with proxy-routed Cloudflare DoH fallback.
   * Traps WebRTC STUN ports (`3478`, `5349`, `19302`) and drops all IPv6 traffic (`IP-CIDR6,::/0,REJECT`).
4. **Dual-Track Outbound Routing**:
   * Direct egress for native residential IP connections by default (no CAPTCHA, lowest latency).
   * Built-in Cloudflare WARP proxy on port `40000` as a silent standby for fallback routing.
5. **Multi-Platform Support**:
   * Generates local YAML profiles for desktop.
   * Hosts a lightweight HTTP subscription service on port `24480` for Android Clash Meta import.
   * Outputs standard `vless://` share links for iOS (Shadowrocket, Sing-box, Loon).

### Repository Structure

```
├── SKILL.md                          # Antigravity skill definition file
├── README.md                         # Dual-language documentation
├── LICENSE                           # MIT License
├── .gitignore                        # Git ignore file for local secrets
├── scripts/
│   ├── deploy_vps.py                 # Automated remote deployment runner via SSH
│   ├── vps_setup.sh                  # Remote VPS initialization script
│   ├── generate_clash_config.py      # Local YAML profile generator
│   └── verify_environment.py         # End-to-end verification gate check
└── templates/
    ├── clash_profile.yaml.template   # Clash Verge configuration template
    └── xray_server.json.template     # Xray server configuration template
```

### Quick Start

#### Option 1: AI Agent Invocation (Recommended)

In Antigravity, Cursor, or Claude Code, enter the following command in the chat:

> "我新买了一台海外 VPS，IP 是 `x.x.x.x`，端口是 `xxxx`，密码是 `xxxx`，请用 vps-setup 技能帮我完成节点的配置。"

The agent will read `SKILL.md`, connect to the new VPS, run the initialization, and output the Clash Verge YAML profile.

#### Option 2: Local CLI Execution

Run the deployment script directly from your terminal:

```bash
python scripts/deploy_vps.py \
  --host <VPS_IP> \
  --port <SSH_PORT> \
  --user root \
  --password "<PASSWORD>" \
  --node-name "US-Residential-Node" \
  --output "US-Residential-Node.yaml"
```

### Client Import Guide

* **Windows / macOS (Clash Verge Rev)**: Open Profiles, drag and drop the generated `.yaml` file into the window, right-click to Use, and enable TUN Mode.
* **Android (Clash Meta for Android)**: Go to Profiles -> New Profile -> Import from URL, and enter `http://<VPS_IP>:24480/clash.yaml`.
* **iOS (Shadowrocket / Sing-box / Loon)**: Copy the generated `vless://` link and open the app to add automatically.

### Verification Gate Check

Verify network cleanliness and anti-leak performance:

```bash
python scripts/verify_environment.py --proxy http://127.0.0.1:7897
```

---

<a name="中文版本"></a>
## 中文版本

海外独享原生住宅 / 双 ISP VPS 全自动初始化与客户端防漏加固技能套件，专为访问 Claude 3.7、OpenAI o1/o3、Google Gemini 及 Cursor 等 AI 服务设计。

### 核心特性

1. **协议锁定与兼容免疫**：
   * 服务端锁定 **Xray v26.6.27** 并显式配置 `"minClientVer": ""`，杜绝高版本 Xray 强制后量子加密导致的 Mihomo 握手报错；
   * SNI 默认锚定 **`www.apple.com`**，彻底解决证书链过长导致的握手分片丢包。
2. **内核保活与深度防断连**：
   * 内核 `net.ipv4.tcp_keepalive_time` 缩短为 30s，Xray 空闲断开 `connIdle` 延长至 1800s，根除长思考流中的 `Broken pipe (os error 32)`；
   * 开启 BBR 拥塞控制，并在服务端全局关闭 IPv6。
3. **全维防泄漏客户端配置**：
   * 生成 1:1 结构对齐的 Clash Verge Rev / Mihomo YAML 配置文件；
   * 采用 Fake-IP 模式，国内安全 DoH 引导 + 代理专线 Cloudflare DoH Fallback；
   * 强制拦截 WebRTC STUN 端口（3478, 5349, 19302）走专属代理，首行阻断 IPv6 旁路（`IP-CIDR6,::/0,REJECT`）。
4. **双轨出站与容灾设计**：
   * 默认原生住宅 IP 直连出站（零人机验证码、最低延迟）；
   * 服务端内置 Cloudflare WARP 代理（40000 端口）作为静默热备通道。
5. **多端开箱即用**：
   * 自动生成电脑端 YAML 配置文件；
   * VPS 内置开机自启 HTTP 订阅服务（24480 端口），支持 Android 端 URL 直接导入；
   * 自动生成 iOS（Shadowrocket / Sing-box / Loon）标准 `vless://` 直连链接。

### 项目目录结构

```
├── SKILL.md                          # Antigravity 技能主定义文件
├── README.md                         # 中英文双语文档
├── LICENSE                           # MIT 开源许可证
├── .gitignore                        # 敏感配置文件忽略规则
├── scripts/
│   ├── deploy_vps.py                 # [本地端主入口] 一键全自动 SSH 编排与本地 YAML 回传
│   ├── vps_setup.sh                  # [VPS 服务端] 静默安装初始化脚本
│   ├── generate_clash_config.py      # [本地端] 1:1 格式对齐 YAML 与链接生成器
│   └── verify_environment.py         # [本地端] 全自动网络环境与防漏门禁检测脚本
└── templates/
    ├── clash_profile.yaml.template   # Clash Verge 客户端配置模板
    └── xray_server.json.template     # Xray 服务端配置模板
```

### 快速使用

#### 方式一：让 AI Agent 全自动部署（推荐）

在 Antigravity / Cursor / Claude Code 对话框中直接输入：

> “我新买了一台海外 VPS，IP 是 `x.x.x.x`，端口是 `xxxx`，密码是 `xxxx`，请用 vps-setup 技能帮我完成节点的配置。”

Agent 会自动激活该技能，远程连接新服务器并全自动初始化，直接在当前工作区生成专属的 Clash 配置文件及移动端导入链接。

#### 方式二：本地终端一键自动化执行

在本地终端运行：

```bash
python scripts/deploy_vps.py \
  --host <VPS_IP> \
  --port <SSH_PORT> \
  --user root \
  --password "<PASSWORD>" \
  --node-name "US-Residential-Node" \
  --output "US-Residential-Node.yaml"
```

### 客户端导入方法

* **电脑端（Windows / macOS - Clash Verge Rev）**：打开“订阅”页面，将生成的 `.yaml` 文件拖入，右键选择“使用”，并开启“系统代理”与“TUN 模式”。
* **手机端（Android - Clash Meta for Android）**：配置 -> 新配置 -> 从 URL 导入，输入 `http://<VPS_IP>:24480/clash.yaml` 保存即可。
* **手机端（iOS - Shadowrocket / Sing-box / Loon）**：复制生成的 `vless://` 链接，打开软件自动检测添加。

### 门禁自检检测

配置生效后，在本地终端运行检测脚本：

```bash
python scripts/verify_environment.py --proxy http://127.0.0.1:7897
```

---

## License

MIT License

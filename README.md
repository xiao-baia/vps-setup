# VPS Setup Automation Skill (`vps-setup`)

**English** | [中文版](README_ZH.md)

---

An automated provisioning and ultimate anti-leak hardening skill for AI developer workflows (Claude, OpenAI, Gemini, Cursor). Combines hardened Linux VPS deployment with zero-fallback Clash Verge / Mihomo profiles, iOS Shadowrocket split-tunneling, cross-platform system Kill Switch (`clash-guard`), and real TUN verification.

## Key Features

1. **Xray VLESS Reality & Anti-Drop Server Hardening**:
   * Pinned to **Xray v26.6.27** with `"minClientVer": ""` and `www.apple.com` SNI for 100% Mihomo / Clash Verge Rev compatibility.
   * Shortens `net.ipv4.tcp_keepalive_time` to 30s, sets Xray `connIdle` to 1800s, enables BBR, disables VPS IPv6, and blocks outbound UDP 443 (QUIC).
   * Built-in Cloudflare WARP proxy (`127.0.0.1:40000`) as standby routing for Google / Gemini.
2. **Zero-Fallback Clash Verge / Mihomo Profiles (Mode A & Mode B)**:
   * **Zero `DIRECT` in proxy groups**: All outbound proxy groups (`🚀 独享-AI与代码`, `🌐 谷歌与Gemini`, `🐟 漏网之鱼`, and Mode B `🔀 跳板节点`) omit `DIRECT` so node failure blocks traffic rather than leaking the domestic IP.
   * **Overseas-first DNS (`respect-rules: true`)**: Primary `nameserver` routes via proxy-bound overseas DoH (`cloudflare-dns.com`, `1.1.1.1`, `dns.google`), while `nameserver-policy` keeps `geosite:geolocation-!cn` ahead of `geosite:cn,private` and `rule-set:direct`.
   * **Auto-updating whitelists & leak traps**: Integrates daily `Loyalsoldier/clash-rules` (`direct.txt`, `cncidr.txt`), explicit `100.64.0.0/10`, Bilibili `mirrorakam`, WeChat, `claudemcpclient.com`, Claude telemetry domains, WebRTC STUN ports (`3478`, `5349`, `19302`), and `IP-CIDR6,::/0,REJECT`.
   * **Mode B Chained Proxy (`dialer-proxy`)**: Supports routing a static residential SOCKS5 exit through the VPS jump node with loop-prevention rules and UDP disabled.
3. **iOS Shadowrocket Anti-Leak `.conf` + Multi-Platform Outputs**:
   * Generates a companion `.shadowrocket.conf` (`FINAL,PROXY`, `Loyalsoldier/surge-rules`, IPv6 disabled, `no-resolve`) alongside the desktop `.yaml`, `vless://` share link, and VPS HTTP subscription server (`:24480/clash.yaml` & `:24480/shadowrocket.conf`).
4. **Cross-Platform Auto-Arm System Kill Switch (`scripts/setup_killswitch.py`)**:
   * Automatically invoked at the end of `deploy_vps.py` (with `--skip-backup`, unless `--no-killswitch` is passed) to generate `断网急救.txt` on Desktop and install the OS Kill Switch (`local.clash-guard`). Uses a three-state machine (**disarmed on boot/reboot** -> **auto-arms with 0ms block + IPv6/router-DNS drop when TUN turns on** -> **stays locked if TUN crashes/drops** -> **resets on reboot**). Never modifies any Clash Verge subscription files (`profiles/` or `profiles.yaml`).
5. **Real TUN & DNS Leak Verification Gate (`scripts/verify_environment.py`)**:
   * Audits generated YAML rules/DNS/groups, probes true TUN takeover without proxy environment variables (`ProxyHandler({})`), checks domestic direct vs. overseas/telemetry IP consistency, performs real `1.1.1.1/cdn-cgi/trace`, DoH, and `isp.ac/dns-leak-test` checks, and inspects Kill Switch readiness.

## Repository Structure

```
├── SKILL.md                              # Antigravity skill definition file
├── README.md                             # English documentation
├── README_ZH.md                          # Chinese documentation
├── LICENSE                               # MIT License
├── .gitignore                            # Git ignore file for local secrets
├── scripts/
│   ├── deploy_vps.py                     # Automated remote deployment runner via SSH (Mode A & B)
│   ├── vps_setup.sh                      # Remote VPS initialization script
│   ├── generate_clash_config.py          # Local Clash YAML & Shadowrocket .conf generator
│   ├── setup_killswitch.py               # Client audit, backup/restore & Kill Switch manager
│   └── verify_environment.py             # Read-only 11-item anti-leak verification gate
└── templates/
    ├── clash_profile.yaml.template       # Hardened Clash Verge configuration template
    ├── shadowrocket.conf.template        # iOS Shadowrocket anti-leak split-tunnel template
    └── xray_server.json.template         # Xray server configuration template
```

## Quick Start

### Option 1: AI Agent Invocation (Recommended)

In Antigravity, Cursor, or Claude Code, enter the following command in the chat:

> "我新买了一台海外 VPS，IP 是 `x.x.x.x`，端口是 `xxxx`，密码是 `xxxx`，请用 vps-setup 技能帮我完成节点的配置。"

（若需「VPS 跳板 + 静态住宅 SOCKS5 落地」模式 B，也可以直接发送：）
> "我新买了一台海外 VPS（IP `x.x.x.x`，端口 `xxxx`，密码 `xxxx`）和一颗静态住宅 SOCKS5（IP `y.y.y.y`，端口 `1080`，账号 `user`，密码 `pass`），请用 vps-setup 模式 B 帮我完成配置。"

The agent will read `SKILL.md`, connect to the new VPS, execute the initialization, output the zero-fallback Clash Verge YAML and iOS Shadowrocket `.conf`, and automatically enable the system Kill Switch (when TUN is active).

### Option 2: Local CLI Execution

Run the deployment script directly from your terminal (Mode A by default; automatically invokes Kill Switch unless `--no-killswitch` is passed):

```bash
python scripts/deploy_vps.py \
  --host <VPS_IP> \
  --port <SSH_PORT> \
  --user root \
  --password "<PASSWORD>" \
  --node-name "US-Residential-Node" \
  --output "US-Residential-Node.yaml"
```

Local Kill Switch management (optional standalone control):

```bash
# Read-only system audit
python scripts/setup_killswitch.py --action audit

# Backup configs & generate emergency rescue guide
python scripts/setup_killswitch.py --action backup

# Install OS Kill Switch manually (only after TUN is confirmed active)
python scripts/setup_killswitch.py --action install-killswitch --skip-backup
```

## Client Import Guide

* **Windows / macOS (Clash Verge Rev)**: Open Profiles, drag and drop the generated `.yaml` file into the window; when using, simply select the profile, click Use, and toggle **TUN Mode** on (no Auto-Launch required—you remain in full control of starting/stopping Clash Verge). Make sure **DNS Override** and **IPv6** toggles stay OFF.
* **Android (Clash Meta for Android)**: Go to Profiles -> New Profile -> Import from URL, and enter `http://<VPS_IP>:24480/clash.yaml`.
* **iOS (Shadowrocket / Sing-box / Loon)**: Copy the generated `vless://` link into Shadowrocket, then import the generated `.shadowrocket.conf` (or `http://<VPS_IP>:24480/shadowrocket.conf`) in Config and tap **Use Config** (keep Global Routing = `Config`).

## Verification Gate Check

Verify network cleanliness and anti-leak performance (read-only 11-item audit):

```bash
python scripts/verify_environment.py --config US-Residential-Node.yaml --proxy http://127.0.0.1:7897
```

## License

MIT License

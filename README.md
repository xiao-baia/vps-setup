# VPS Setup Automation Skill (`vps-setup`)

**English** | [中文版](README_ZH.md)

---

A specialized automation skill for configuring high-reliability Linux VPS endpoints and generating matching Clash Verge / Mihomo profiles for AI developer workflows (Claude, OpenAI, Gemini, Cursor).

## Key Features

1. **Xray VLESS Reality Setup**:
   * Pinned to **Xray v26.6.27** with `"minClientVer": ""` to ensure 100% compatibility with Mihomo and Clash Verge Rev.
   * SNI configured to `www.apple.com` to prevent packet fragmentation caused by oversized TLS certificate chains.
2. **Kernel-Level Tuning**:
   * Shortens `net.ipv4.tcp_keepalive_time` to 30s and configures Xray `connIdle` to 1800s to eliminate Broken Pipe disconnects during extended AI reasoning streams.
   * Enables BBR congestion control and disables IPv6 system-wide to prevent location and DNS leaks.
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

## Repository Structure

```
├── SKILL.md                          # Antigravity skill definition file
├── README.md                         # English documentation
├── README_ZH.md                      # Chinese documentation
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

## Quick Start

### Option 1: AI Agent Invocation (Recommended)

In Antigravity, Cursor, or Claude Code, enter the following command in the chat:

> "我新买了一台海外 VPS，IP 是 `x.x.x.x`，端口是 `xxxx`，密码是 `xxxx`，请用 vps-setup 技能帮我完成节点的配置。"

The agent will read `SKILL.md`, connect to the new VPS, execute the initialization, and output the Clash Verge YAML profile.

### Option 2: Local CLI Execution

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

## Client Import Guide

* **Windows / macOS (Clash Verge Rev)**: Open Profiles, drag and drop the generated `.yaml` file into the window, right-click to Use, and enable TUN Mode.
* **Android (Clash Meta for Android)**: Go to Profiles -> New Profile -> Import from URL, and enter `http://<VPS_IP>:24480/clash.yaml`.
* **iOS (Shadowrocket / Sing-box / Loon)**: Copy the generated `vless://` link and open the app to add automatically.

## Verification Gate Check

Verify network cleanliness and anti-leak performance:

```bash
python scripts/verify_environment.py --proxy http://127.0.0.1:7897
```

## License

MIT License

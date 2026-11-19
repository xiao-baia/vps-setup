# VPS Setup Automation Skill (`vps-setup`)

**English** | [中文版](README_ZH.md)

---

A specialized automation skill for configuring high-reliability Linux VPS endpoints and generating matching Clash Verge / Mihomo & Shadowrocket anti-leak profiles for AI developer workflows (Claude, OpenAI, Gemini, Cursor).

## Key Features

1. **Xray VLESS Reality Setup**:
   * Pinned to **Xray v26.6.27** with `"minClientVer": ""` to ensure 100% compatibility with Mihomo and Clash Verge Rev.
   * SNI configured to `www.apple.com` to prevent packet fragmentation caused by oversized TLS certificate chains.
2. **Kernel-Level Tuning**:
   * Shortens `net.ipv4.tcp_keepalive_time` to 30s and configures Xray `connIdle` to 1800s to eliminate Broken Pipe disconnects during extended AI reasoning streams.
   * Enables BBR congestion control and disables IPv6 on the VPS.
3. **Leak-Proof Clash Verge & Shadowrocket Profile Generation**:
   * Generates 1:1 production-aligned `.yaml` and `.conf` profiles with no `DIRECT` fallback in overseas proxy groups.
   * Uses Fake-IP (`198.18.0.0/16`) and proxy-routed overseas DoH (`1.1.1.1` / `8.8.8.8`) as the default nameserver, limiting domestic DoH strictly to CN/private policies.
   * Places `IP-CIDR6,::/0,REJECT,no-resolve` at the top, puts LAN/reserved ranges (`private`, `lan`, `100.64.0.0/10`) and Bilibili CDN (`mirrorakam`) ahead of `STUN` ports and `GEOSITE,geolocation-!cn`, and auto-updates `Loyalsoldier/clash-rules` daily.
4. **OS-Aware Anti-Leak Hardening**:
   * **Windows**: Automatically detects and disables Windows SMHNR (`DisableSmartNameResolution = 1`) with a one-click desktop restore `.bat`; relies on modern Mihomo `strict-route: true` WFP enforcement to block IPv6 bypass.
   * **macOS**: Never modifies macOS system network settings automatically; informs the user that SMHNR does not apply to macOS and advises checking `scutil --dns` and optionally adjusting Wi-Fi IPv6 mode at their own discretion.
5. **Dual-Track Outbound Routing & Multi-Platform Support**:
   * Direct native residential IP egress by default, with Cloudflare WARP on port `40000` as standby.
   * Outputs desktop `.yaml`, iOS `.conf`, `vless://` links, and hosts an HTTP subscription server on port `24480`.

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
│   ├── generate_clash_config.py      # Local YAML & Shadowrocket .conf generator
│   ├── windows_smhnr.py              # Windows SMHNR status/disable/restore utility
│   └── verify_environment.py         # Real end-to-end DNS/IPv6 anti-leak gate check
└── templates/
    ├── clash_profile.yaml.template   # Clash Verge configuration template
    └── xray_server.json.template     # Xray server configuration template
```

## Quick Start

```bash
python scripts/deploy_vps.py \
  --host <VPS_IP> \
  --port <SSH_PORT> \
  --user root \
  --password "<PASSWORD>" \
  --node-name "US-Residential-Node" \
  --output "US-Residential-Node.yaml"
```

## Verification Gate Check

With Clash Verge TUN mode enabled, run:

```bash
python scripts/verify_environment.py
```

## License

MIT License

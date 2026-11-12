# VPS Setup Automation Skill

A specialized automation skill for configuring high-reliability Linux VPS endpoints and generating matching Clash Verge / Mihomo profiles for AI developer workflows.

## Features

- **Xray VLESS Reality Setup**: Automated installation pinned to Xray v26.6.27 with apple.com SNI and client compatibility settings.
- **Kernel Tuning**: Configures TCP keepalive (`tcp_keepalive_time=30`), BBR congestion control, and disables IPv6 to prevent routing and DNS leaks.
- **Client Configuration Generation**: Generates 1:1 structured Clash Verge / Mihomo YAML profiles with Fake-IP, DNS fallback routing, and WebRTC STUN isolation.
- **Dual-Mode Outbound**: Direct egress for native residential connections with optional Cloudflare WARP local proxy.
- **Mobile Subscription**: Built-in lightweight HTTP service for mobile profile downloads.

## Repository Contents

```
├── SKILL.md                          # Antigravity skill definition
├── README.md                         # Project documentation
├── .gitignore                        # Standard ignore rules
├── scripts/
│   ├── deploy_vps.py                 # Automated remote deployment runner
│   ├── vps_setup.sh                  # Server-side setup script
│   ├── generate_clash_config.py      # Local YAML profile generator
│   └── verify_environment.py         # Connectivity and anti-leak verification
└── templates/
    ├── clash_profile.yaml.template   # Clash Verge configuration template
    └── xray_server.json.template     # Xray server configuration template
```

## Usage

### Local CLI Execution

Deploy to a new VPS and generate the local profile:

```bash
python scripts/deploy_vps.py \
  --host <VPS_IP> \
  --port <SSH_PORT> \
  --user root \
  --password "<PASSWORD>" \
  --node-name "US-Residential-Node" \
  --output "US-Residential-Node.yaml"
```

### Antigravity Agent Execution

Invoke the skill directly in Antigravity chat:

> "我新买了一台海外 VPS，IP 是 `x.x.x.x`，端口是 `xxxx`，密码是 `xxxx`，请用 vps-setup 技能帮我完成节点的配置。"

## License

MIT License

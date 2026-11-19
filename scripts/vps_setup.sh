#!/usr/bin/env bash
# ==============================================================================
# Claude Anti-Ban Network Setup Script for Linux VPS (Debian / Ubuntu)
# Features:
# 1. Pinned Xray-core v26.6.27 with VLESS Reality (XTLS-rprx-vision + Chrome Fingerprint)
# 2. Reality with SNI www.apple.com and minClientVer="" for 100% Mihomo/Clash compatibility
# 3. Cloudflare WARP Socks5 Local Proxy on port 40000
# 4. Smart routing: Claude/OpenAI -> Native Residential IP; Google/Gemini -> Direct or WARP
# 5. Linux Kernel tuning: TCP Keepalive (30s) + Disable IPv6 leak prevention + BBR
# 6. Automatic HTTP Subscription Service on port 24480 for mobile Clash Meta URL import
# ==============================================================================

set -euo pipefail

# Default Parameters
PORT="${PORT:-24433}"
SNI="${SNI:-www.apple.com}"
SUB_PORT="${SUB_PORT:-24480}"
WARP_PORT="40000"

# Color Codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

if [ "$(id -u)" -ne 0 ]; then
    log_error "This script must be run as root!"
    exit 1
fi

log_info "Step 1: Installing dependencies..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq curl wget jq openssl gnupg lsb-release iptables procps python3 ufw- || true

# ------------------------------------------------------------------------------
# 2. Kernel Tuning: Disable IPv6, Enable TCP Keepalive & BBR
# ------------------------------------------------------------------------------
log_info "Step 2: Tuning Linux Kernel parameters (Anti-leak & Keepalive)..."

cat > /etc/sysctl.d/99-claude-antiban.conf << 'EOF'
# Disable IPv6 to prevent DNS and WebRTC leaks
net.ipv6.conf.all.disable_ipv6 = 1
net.ipv6.conf.default.disable_ipv6 = 1
net.ipv6.conf.lo.disable_ipv6 = 1

# TCP Keepalive for long reasoning AI streams (prevent Broken Pipe)
net.ipv4.tcp_keepalive_time = 30
net.ipv4.tcp_keepalive_intvl = 10
net.ipv4.tcp_keepalive_probes = 3

# Fast BBR Congestion Control
net.core.default_qdisc = fq
net.ipv4.tcp_congestion_control = bbr
EOF

sysctl --system >/dev/null 2>&1 || true

# ------------------------------------------------------------------------------
# 3. Install Official Xray-core (Pinned to v26.6.27 for Mihomo / Clash compatibility)
# ------------------------------------------------------------------------------
log_info "Step 3: Installing official Xray-core (v26.6.27)..."
CURRENT_XRAY_VER=$(xray version 2>/dev/null | head -n1 | awk '{print $2}' || true)
if [ "$CURRENT_XRAY_VER" != "26.6.27" ]; then
    curl -fsSL https://github.com/XTLS/Xray-install/raw/main/install-release.sh -o /tmp/xray_inst.sh
    bash /tmp/xray_inst.sh install --version v26.6.27
fi

# Ensure single config drop-in
mkdir -p /etc/systemd/system/xray.service.d/
cat > /etc/systemd/system/xray.service.d/10-donot_touch_single_conf.conf << 'EOF'
[Service]
ExecStart=
ExecStart=/usr/local/bin/xray run -config /usr/local/etc/xray/config.json
EOF
systemctl daemon-reload

# ------------------------------------------------------------------------------
# 4. Install & Configure Cloudflare WARP (in Proxy Mode on port 40000)
# ------------------------------------------------------------------------------
log_info "Step 4: Setting up Cloudflare WARP for Gemini / fallback routing..."

if ! command -v warp-cli &> /dev/null; then
    curl -fsSL https://pkg.cloudflareclient.com/pubkey.gpg | gpg --yes --dearmor --output /usr/share/keyrings/cloudflare-warp-archive-keyring.gpg
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/cloudflare-warp-archive-keyring.gpg] https://pkg.cloudflareclient.com/ $(lsb_release -cs) main" | tee /etc/apt/sources.list.d/cloudflare-client.list
    apt-get update -qq
    apt-get install -y -qq cloudflare-warp
fi

# Ensure warp-svc is running
systemctl enable --now warp-svc >/dev/null 2>&1 || true
sleep 3

# Register and set to proxy mode
warp-cli --accept-tos registration new >/dev/null 2>&1 || warp-cli --accept-tos register >/dev/null 2>&1 || true
warp-cli --accept-tos mode proxy >/dev/null 2>&1 || true
warp-cli --accept-tos proxy port ${WARP_PORT} >/dev/null 2>&1 || true
warp-cli --accept-tos connect >/dev/null 2>&1 || true

# Test WARP local proxy
sleep 2
WARP_TEST=$(curl -s --socks5 "127.0.0.1:${WARP_PORT}" https://cloudflare.com/cdn-cgi/trace 2>/dev/null | grep -E "warp=on|warp=plus" || true)
if [ -n "$WARP_TEST" ]; then
    log_info "Cloudflare WARP proxy active on 127.0.0.1:${WARP_PORT}"
else
    log_warn "WARP is connecting. It will auto-reconnect if needed."
fi

# ------------------------------------------------------------------------------
# 5. Generate Reality Keys and Credentials
# ------------------------------------------------------------------------------
log_info "Step 5: Generating VLESS Reality credentials..."

UUID=$(/usr/local/bin/xray uuid)
X25519_OUTPUT=$(/usr/local/bin/xray x25519)
PRIVATE_KEY=$(echo "$X25519_OUTPUT" | grep -i "private" | awk -F': ' '{print $2}' | tr -d ' \r\n')
PUBLIC_KEY=$(echo "$X25519_OUTPUT" | grep -i "public" | awk -F': ' '{print $2}' | tr -d ' \r\n')
SHORT_ID=$(openssl rand -hex 8)

# Detect Public IPv4
SERVER_IP=$(curl -s -4 https://api.ipify.org || curl -s -4 https://ipinfo.io/ip || curl -s -4 https://icanhazip.com || echo "YOUR_VPS_IP")

# Default: Google & Gemini uses Native Residential Direct (100% matches current live VPS setup)
GOOGLE_OUTBOUND="${GOOGLE_OUTBOUND:-direct}"
log_info "Google & Gemini outbound routing set to: ${GOOGLE_OUTBOUND} (Native Residential Direct)"

# ------------------------------------------------------------------------------
# 6. Write Xray Configuration (/usr/local/etc/xray/config.json)
# ------------------------------------------------------------------------------
log_info "Step 6: Writing Xray server configuration..."

mkdir -p /usr/local/etc/xray/

cat > /usr/local/etc/xray/config.json << EOF
{
  "log": {
    "loglevel": "warning"
  },
  "policy": {
    "levels": {
      "0": {
        "handshake": 4,
        "connIdle": 1800,
        "uplinkOnly": 2,
        "downlinkOnly": 5,
        "statsUserUplink": false,
        "statsUserDownlink": false,
        "bufferSize": 4
      }
    }
  },
  "inbounds": [
    {
      "port": ${PORT},
      "protocol": "vless",
      "settings": {
        "clients": [
          {
            "id": "${UUID}",
            "flow": "xtls-rprx-vision"
          }
        ],
        "decryption": "none"
      },
      "streamSettings": {
        "network": "tcp",
        "security": "reality",
        "realitySettings": {
          "show": true,
          "dest": "${SNI}:443",
          "xver": 0,
          "serverNames": [
            "${SNI}"
          ],
          "privateKey": "${PRIVATE_KEY}",
          "shortIds": [
            "${SHORT_ID}"
          ],
          "minClientVer": ""
        }
      },
      "sniffing": {
        "enabled": true,
        "destOverride": [
          "http",
          "tls"
        ]
      }
    }
  ],
  "outbounds": [
    {
      "tag": "direct",
      "protocol": "freedom",
      "settings": {
        "domainStrategy": "UseIPv4"
      }
    },
    {
      "tag": "warp",
      "protocol": "socks",
      "settings": {
        "servers": [
          {
            "address": "127.0.0.1",
            "port": ${WARP_PORT}
          }
        ]
      }
    },
    {
      "tag": "block",
      "protocol": "blackhole",
      "settings": {}
    }
  ],
  "routing": {
    "domainStrategy": "IPIfNonMatch",
    "rules": [
      {
        "type": "field",
        "port": 443,
        "network": "udp",
        "outboundTag": "block"
      },
      {
        "type": "field",
        "ip": [
          "geoip:private"
        ],
        "outboundTag": "block"
      },
      {
        "type": "field",
        "domain": [
          "domain:claude.ai",
          "domain:anthropic.com",
          "domain:openai.com",
          "domain:chatgpt.com",
          "domain:oaistatic.com",
          "domain:oaiusercontent.com"
        ],
        "outboundTag": "direct"
      },
      {
        "type": "field",
        "domain": [
          "geosite:google",
          "domain:gemini.google.com",
          "domain:aistudio.google.com",
          "domain:generativelanguage.googleapis.com"
        ],
        "outboundTag": "${GOOGLE_OUTBOUND}"
      },
      {
        "type": "field",
        "ip": [
          "geoip:google"
        ],
        "outboundTag": "${GOOGLE_OUTBOUND}"
      },
      {
        "type": "field",
        "network": "tcp,udp",
        "outboundTag": "direct"
      }
    ]
  }
}
EOF

# Restart Xray
systemctl enable xray >/dev/null 2>&1 || true
systemctl restart xray

# Verify Xray is running
sleep 2
if systemctl is-active --quiet xray; then
    log_info "Xray service successfully started!"
else
    log_error "Xray failed to start! Checking logs..."
    journalctl -u xray -n 20 --no-pager
    exit 1
fi

# Ensure port is open in iptables
if command -v iptables &> /dev/null; then
    iptables -I INPUT -p tcp --dport "${PORT}" -j ACCEPT || true
fi

# ------------------------------------------------------------------------------
# 7. Generate Mobile Clash Profile & Start Subscription Service
# ------------------------------------------------------------------------------
log_info "Step 7: Setting up HTTP subscription service for Clash Meta (Port ${SUB_PORT})..."

mkdir -p /var/www/sub

cat > /var/www/sub/clash.yaml << EOF
port: 7890
socks-port: 7891
mixed-port: 7897
mode: rule
unified-delay: true
keep-alive-interval: 15
log-level: info
allow-lan: false
ipv6: false
external-controller: 127.0.0.1:9097
geo-auto-update: true
geo-update-interval: 24

dns:
  enable: true
  ipv6: false
  enhanced-mode: fake-ip
  fake-ip-range: 198.18.0.1/16
  fake-ip-filter:
    - "*.lan"
    - "*.local"
    - "*.arpa"
    - "time.*.com"
    - "ntp.*.com"
    - "+.msftconnecttest.com"
    - "+.msftncsi.com"
    - "localhost.ptlogin2.qq.com"
  respect-rules: false
  default-nameserver:
    - 223.5.5.5
    - 119.29.29.29
  proxy-server-nameserver:
    - "https://dns.alidns.com/dns-query"
    - "https://doh.pub/dns-query"
  direct-nameserver:
    - "https://dns.alidns.com/dns-query"
    - "https://doh.pub/dns-query"
  nameserver-policy:
    "geosite:geolocation-!cn":
      - "https://1.1.1.1/dns-query#🚀 独享-AI与代码"
      - "https://8.8.8.8/dns-query#🚀 独享-AI与代码"
    "rule-set:direct":
      - "https://dns.alidns.com/dns-query"
      - "https://doh.pub/dns-query"
    "geosite:cn,private":
      - "https://dns.alidns.com/dns-query"
      - "https://doh.pub/dns-query"
  nameserver:
    - "https://1.1.1.1/dns-query#🚀 独享-AI与代码"
    - "https://8.8.8.8/dns-query#🚀 独享-AI与代码"

tun:
  enable: true
  stack: mixed
  device: Mihomo
  dns-hijack:
    - "any:53"
    - "tcp://any:53"
  auto-route: true
  strict-route: true
  auto-detect-interface: true
  inet4-address:
    - 198.18.0.1/30

proxies:
  - name: "🇺🇸 独享-Claude-原生住宅9929"
    type: vless
    server: ${SERVER_IP}
    port: ${PORT}
    uuid: ${UUID}
    network: tcp
    udp: true
    tls: true
    flow: xtls-rprx-vision
    servername: ${SNI}
    reality-opts:
      public-key: ${PUBLIC_KEY}
      short-id: ${SHORT_ID}
    client-fingerprint: chrome

proxy-groups:
  - name: "🚀 独享-AI与代码"
    type: select
    proxies:
      - "🇺🇸 独享-Claude-原生住宅9929"

  - name: "🌐 谷歌与Gemini"
    type: select
    proxies:
      - "🇺🇸 独享-Claude-原生住宅9929"

  - name: "🐟 漏网之鱼"
    type: select
    proxies:
      - "🇺🇸 独享-Claude-原生住宅9929"

rule-providers:
  direct:
    type: http
    behavior: domain
    format: yaml
    url: "https://cdn.jsdelivr.net/gh/Loyalsoldier/clash-rules@release/direct.txt"
    path: ./ruleset/direct.yaml
    interval: 86400
  cncidr:
    type: http
    behavior: ipcidr
    format: yaml
    url: "https://cdn.jsdelivr.net/gh/Loyalsoldier/clash-rules@release/cncidr.txt"
    path: ./ruleset/cncidr.yaml
    interval: 86400

rules:
  # ==========================================
  # 0. 防泄漏加固：顶层拦截全部 IPv6 流量（配合 tun.strict-route: true 与 dns.ipv6: false）
  # ==========================================
  - IP-CIDR6,::/0,REJECT,no-resolve

  # ==========================================
  # 1. Claude / Anthropic 全生态专属规则（全走国外独享代理）
  # ==========================================
  - GEOSITE,anthropic,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,anthropic.com,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,claude.ai,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,claude.com,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,claudeusercontent.com,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,claudemcpclient.com,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,clau.de,🚀 独享-AI与代码
  - DOMAIN-KEYWORD,anthropic,🚀 独享-AI与代码
  - DOMAIN-KEYWORD,claude,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,sentry.io,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,statsigapi.net,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,statsig.com,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,featuregates.org,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,intercom.io,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,intercomcdn.com,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,stripe.com,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,stripe.network,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,hcaptcha.com,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,challenges.cloudflare.com,🚀 独享-AI与代码

  # ==========================================
  # 1.5 内网保留地址与 B 站 CDN 直连（必须排在 STUN 端口与 geolocation-!cn 之前）
  # ==========================================
  - GEOSITE,private,DIRECT
  - GEOIP,lan,DIRECT,no-resolve
  - IP-CIDR,100.64.0.0/10,DIRECT,no-resolve
  - DOMAIN-KEYWORD,mirrorakam,DIRECT

  # ==========================================
  # 1.8 WebRTC STUN 防泄漏（公网 STUN 全走海外代理）
  # ==========================================
  - DOMAIN-KEYWORD,stun,🚀 独享-AI与代码
  - DST-PORT,3478,🚀 独享-AI与代码
  - DST-PORT,5349,🚀 独享-AI与代码
  - DST-PORT,19302,🚀 独享-AI与代码

  # ==========================================
  # 2. 其他主流 AI 服务（OpenAI / Grok / Perplexity / Cursor）
  # ==========================================
  - GEOSITE,openai,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,openai.com,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,chatgpt.com,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,oaistatic.com,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,oaiusercontent.com,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,x.ai,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,grok.com,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,perplexity.ai,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,cursor.com,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,cursor.sh,🚀 独享-AI与代码

  # ==========================================
  # 3. 谷歌与 Gemini 规则（VPS 内部直接走原生住宅 IP 直连）
  # ==========================================
  - DOMAIN-SUFFIX,gemini.google.com,🌐 谷歌与Gemini
  - DOMAIN-SUFFIX,aistudio.google.com,🌐 谷歌与Gemini
  - DOMAIN-SUFFIX,generativelanguage.googleapis.com,🌐 谷歌与Gemini
  - DOMAIN-SUFFIX,proactivebackend-pa.googleapis.com,🌐 谷歌与Gemini
  - DOMAIN-KEYWORD,antigravity,🌐 谷歌与Gemini
  - GEOSITE,google,🌐 谷歌与Gemini
  - GEOIP,google,🌐 谷歌与Gemini,no-resolve

  # ==========================================
  # 4. 国外常用服务与开发者生态（全走国外代理）
  # ==========================================
  - DOMAIN-SUFFIX,github.com,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,githubusercontent.com,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,githubcopilot.com,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,v2ex.com,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,ippure.com,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,ipinfo.io,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,ipapi.co,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,browserleaks.com,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,browserleaks.net,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,surfsharkdns.com,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,fastly-analytics.com,🚀 独享-AI与代码
  - GEOSITE,geolocation-!cn,🚀 独享-AI与代码

  # ==========================================
  # 5. 国内网站直连（每日自动更新白名单，no-resolve 杜绝本地 DNS 泄漏）
  # ==========================================
  - RULE-SET,direct,DIRECT
  - RULE-SET,cncidr,DIRECT,no-resolve
  - GEOSITE,cn,DIRECT
  - GEOIP,cn,DIRECT,no-resolve

  # ==========================================
  # 6. 最终兜底（走国外代理）
  # ==========================================
  - MATCH,🐟 漏网之鱼
EOF

cat > /var/www/sub/shadowrocket.conf << 'EOF'
# Shadowrocket Anti-Leak Configuration (Generated by vps-setup)
# 使用方式：先通过 vless:// 链接导入并选中节点，再通过 URL 导入本 .conf 配置文件即可生效

[General]
bypass-system = true
skip-proxy = 192.168.0.0/16, 10.0.0.0/8, 172.16.0.0/12, 127.0.0.1, localhost, *.local
tun-excluded-routes = 10.0.0.0/8, 100.64.0.0/10, 127.0.0.0/8, 169.254.0.0/16, 172.16.0.0/12, 192.168.0.0/16, 224.0.0.0/4, 255.255.255.255/32
dns-server = 223.5.5.5, 119.29.29.29
fallback-dns-server = https://1.1.1.1/dns-query, https://8.8.8.8/dns-query
hijack-dns = *:53
ipv6 = false
prefer-ipv6 = false
dns-direct-system = false
icmp-auto-reply = true
always-reject-url-rewrite = false
private-ip-answer = true

[Rule]
# 0. 防泄漏加固：顶层拦截 IPv6 旁路
IP-CIDR6,::/0,REJECT,no-resolve

# 1. Claude / Anthropic 全生态
DOMAIN-SUFFIX,anthropic.com,PROXY
DOMAIN-SUFFIX,claude.ai,PROXY
DOMAIN-SUFFIX,claude.com,PROXY
DOMAIN-SUFFIX,claudeusercontent.com,PROXY
DOMAIN-SUFFIX,claudemcpclient.com,PROXY
DOMAIN-SUFFIX,clau.de,PROXY
DOMAIN-KEYWORD,anthropic,PROXY
DOMAIN-KEYWORD,claude,PROXY
DOMAIN-SUFFIX,sentry.io,PROXY
DOMAIN-SUFFIX,statsigapi.net,PROXY
DOMAIN-SUFFIX,statsig.com,PROXY
DOMAIN-SUFFIX,featuregates.org,PROXY
DOMAIN-SUFFIX,intercom.io,PROXY
DOMAIN-SUFFIX,intercomcdn.com,PROXY
DOMAIN-SUFFIX,stripe.com,PROXY
DOMAIN-SUFFIX,stripe.network,PROXY
DOMAIN-SUFFIX,hcaptcha.com,PROXY
DOMAIN-SUFFIX,challenges.cloudflare.com,PROXY

# 1.5 内网保留地址与 B 站 CDN 直连（必须排在 STUN 端口与 proxy.txt 之前）
IP-CIDR,192.168.0.0/16,DIRECT,no-resolve
IP-CIDR,10.0.0.0/8,DIRECT,no-resolve
IP-CIDR,172.16.0.0/12,DIRECT,no-resolve
IP-CIDR,100.64.0.0/10,DIRECT,no-resolve
IP-CIDR,127.0.0.1/32,DIRECT,no-resolve
DOMAIN-KEYWORD,mirrorakam,DIRECT

# 1.8 WebRTC STUN 防泄漏
DOMAIN-KEYWORD,stun,PROXY
DEST-PORT,3478,PROXY
DEST-PORT,5349,PROXY
DEST-PORT,19302,PROXY

# 2. 其他主流 AI 服务
DOMAIN-SUFFIX,openai.com,PROXY
DOMAIN-SUFFIX,chatgpt.com,PROXY
DOMAIN-SUFFIX,oaistatic.com,PROXY
DOMAIN-SUFFIX,oaiusercontent.com,PROXY
DOMAIN-SUFFIX,x.ai,PROXY
DOMAIN-SUFFIX,grok.com,PROXY
DOMAIN-SUFFIX,perplexity.ai,PROXY
DOMAIN-SUFFIX,cursor.com,PROXY
DOMAIN-SUFFIX,cursor.sh,PROXY

# 3. 谷歌与 Gemini
DOMAIN-SUFFIX,gemini.google.com,PROXY
DOMAIN-SUFFIX,aistudio.google.com,PROXY
DOMAIN-SUFFIX,generativelanguage.googleapis.com,PROXY
DOMAIN-SUFFIX,proactivebackend-pa.googleapis.com,PROXY
DOMAIN-KEYWORD,antigravity,PROXY
DOMAIN-SUFFIX,google.com,PROXY
DOMAIN-SUFFIX,googleapis.com,PROXY
DOMAIN-SUFFIX,gstatic.com,PROXY
DOMAIN-SUFFIX,googleusercontent.com,PROXY
DOMAIN-SUFFIX,googletagmanager.com,PROXY
DOMAIN-SUFFIX,doubleclick.net,PROXY
DOMAIN-SUFFIX,google-analytics.com,PROXY

# 4. 开发者与 IP 检测生态（排在国内白名单前）
DOMAIN-SUFFIX,github.com,PROXY
DOMAIN-SUFFIX,githubusercontent.com,PROXY
DOMAIN-SUFFIX,githubcopilot.com,PROXY
DOMAIN-SUFFIX,v2ex.com,PROXY
DOMAIN-SUFFIX,ippure.com,PROXY
DOMAIN-SUFFIX,ipinfo.io,PROXY
DOMAIN-SUFFIX,ipapi.co,PROXY
DOMAIN-SUFFIX,browserleaks.com,PROXY
DOMAIN-SUFFIX,browserleaks.net,PROXY
DOMAIN-SUFFIX,surfsharkdns.com,PROXY
DOMAIN-SUFFIX,fastly-analytics.com,PROXY
RULE-SET,https://cdn.jsdelivr.net/gh/Loyalsoldier/surge-rules@release/ruleset/proxy.txt,PROXY

# 5. 国内网站直连（自动更新白名单，no-resolve 防泄漏）
RULE-SET,https://cdn.jsdelivr.net/gh/Loyalsoldier/surge-rules@release/ruleset/direct.txt,DIRECT
GEOIP,CN,DIRECT,no-resolve

# 6. 最终兜底
FINAL,PROXY
EOF

cat > /etc/systemd/system/clash-sub.service << EOF
[Unit]
Description=Clash Subscription Profile HTTP Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/var/www/sub
ExecStart=/usr/bin/python3 -m http.server ${SUB_PORT} --bind 0.0.0.0
Restart=always

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable clash-sub >/dev/null 2>&1 || true
systemctl restart clash-sub

if command -v iptables &> /dev/null; then
    iptables -I INPUT -p tcp --dport "${SUB_PORT}" -j ACCEPT || true
fi

# ------------------------------------------------------------------------------
# 8. Output Result Metadata & Subscription URLs
# ------------------------------------------------------------------------------
VLESS_URL="vless://${UUID}@${SERVER_IP}:${PORT}?security=reality&encryption=none&pbk=${PUBLIC_KEY}&headerType=none&fp=chrome&type=tcp&flow=xtls-rprx-vision&sni=${SNI}&sid=${SHORT_ID}#%F0%9F%87%BA%F0%9F%87%B8%20%E7%8B%AC%E4%BA%AB-Claude-%E5%8E%9F%E7%94%9F%E4%BD%8F%E5%AE%859929"
CLASH_SUB_URL="http://${SERVER_IP}:${SUB_PORT}/clash.yaml"
SHADOWROCKET_CONF_URL="http://${SERVER_IP}:${SUB_PORT}/shadowrocket.conf"

echo ""
echo "==================== SETUP COMPLETE ===================="
echo -e "${GREEN}[VLESS Share Link (iOS Shadowrocket / Sing-box / Loon)]${NC}:"
echo "${VLESS_URL}"
echo ""
echo -e "${GREEN}[iOS Shadowrocket Anti-Leak Conf URL (Configuration -> Add from URL)]${NC}:"
echo "${SHADOWROCKET_CONF_URL}"
echo ""
echo -e "${GREEN}[Android / Desktop Clash Subscription URL (Clash Meta for Android / Clash Verge)]${NC}:"
echo "${CLASH_SUB_URL}"
echo ""
echo "Below is the machine-readable node configuration JSON:"
echo ""

cat << JSON_OUTPUT
###JSON_OUTPUT_START###
{
  "server_ip": "${SERVER_IP}",
  "port": ${PORT},
  "uuid": "${UUID}",
  "flow": "xtls-rprx-vision",
  "security": "reality",
  "sni": "${SNI}",
  "public_key": "${PUBLIC_KEY}",
  "short_id": "${SHORT_ID}",
  "fingerprint": "chrome",
  "warp_port": ${WARP_PORT},
  "subscription_url": "${CLASH_SUB_URL}",
  "shadowrocket_conf_url": "${SHADOWROCKET_CONF_URL}",
  "vless_url": "${VLESS_URL}"
}
###JSON_OUTPUT_END###
JSON_OUTPUT

echo ""
echo "Share this JSON with the Agent or your client config generator."
echo "========================================================"

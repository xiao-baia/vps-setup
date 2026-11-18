#!/usr/bin/env python3
"""
Generate a hardened, anti-leak Clash Verge / Mihomo YAML profile,
an iOS Shadowrocket anti-leak .conf profile, and a VLESS Share Link
from VPS setup output.
"""

import argparse
import json
import os
import sys

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import urllib.parse

TEMPLATE_YAML = """port: 7890
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
  - name: "{node_name}"
    type: vless
    server: {server_ip}
    port: {port}
    uuid: {uuid}
    network: tcp
    udp: true
    tls: true
    flow: {flow}
    servername: {sni}
    reality-opts:
      public-key: {public_key}
      short-id: {short_id}
    client-fingerprint: {fingerprint}

proxy-groups:
  - name: "🚀 独享-AI与代码"
    type: select
    proxies:
      - "{node_name}"

  - name: "🌐 谷歌与Gemini"
    type: select
    proxies:
      - "{node_name}"

  - name: "🐟 漏网之鱼"
    type: select
    proxies:
      - "{node_name}"

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
  # 0. 防泄漏加固：拦截 IPv6 旁路 & 代理全部 WebRTC STUN
  # ==========================================
  - IP-CIDR6,::/0,REJECT,no-resolve
  - DOMAIN-KEYWORD,stun,🚀 独享-AI与代码
  - DST-PORT,3478,🚀 独享-AI与代码
  - DST-PORT,5349,🚀 独享-AI与代码
  - DST-PORT,19302,🚀 独享-AI与代码

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
  # 3. 谷歌与 Gemini 规则（VPS 内部直接走原生 IP 直连，若受限由服务端无缝兜底）
  # ==========================================
  - DOMAIN-SUFFIX,gemini.google.com,🌐 谷歌与Gemini
  - DOMAIN-SUFFIX,aistudio.google.com,🌐 谷歌与Gemini
  - DOMAIN-SUFFIX,generativelanguage.googleapis.com,🌐 谷歌与Gemini
  - DOMAIN-SUFFIX,proactivebackend-pa.googleapis.com,🌐 谷歌与Gemini
  - DOMAIN-KEYWORD,antigravity,🌐 谷歌与Gemini
  - GEOSITE,google,🌐 谷歌与Gemini
  - GEOIP,google,🌐 谷歌与Gemini,no-resolve

  # ==========================================
  # 4. 国外常用服务与开发者生态（排在国内名单前，防混入名单的海外域名误走直连）
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
  # 5. 国内网站与内网直连（每日自动更新白名单，no-resolve 杜绝本地 DNS 泄漏）
  # ==========================================
  - GEOSITE,private,DIRECT
  - GEOIP,lan,DIRECT,no-resolve
  - IP-CIDR,100.64.0.0/10,DIRECT,no-resolve
  - DOMAIN-KEYWORD,mirrorakam,DIRECT
  - RULE-SET,direct,DIRECT
  - RULE-SET,cncidr,DIRECT,no-resolve
  - GEOSITE,cn,DIRECT
  - GEOIP,cn,DIRECT,no-resolve

  # ==========================================
  # 6. 最终兜底（走国外代理）
  # ==========================================
  - MATCH,🐟 漏网之鱼
"""

TEMPLATE_SHADOWROCKET_CONF = """# Shadowrocket Anti-Leak Configuration (Generated by vps-setup)
# 使用方式：先通过 vless:// 链接导入并选中节点，再导入本 .conf 配置文件即可生效

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
# 0. 防泄漏加固：拦截 IPv6 旁路 & 代理 WebRTC STUN
IP-CIDR6,::/0,REJECT,no-resolve
DOMAIN-KEYWORD,stun,PROXY
DEST-PORT,3478,PROXY
DEST-PORT,5349,PROXY
DEST-PORT,19302,PROXY

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

# 5. 国内网站与内网直连（自动更新白名单，no-resolve 防泄漏）
IP-CIDR,192.168.0.0/16,DIRECT,no-resolve
IP-CIDR,10.0.0.0/8,DIRECT,no-resolve
IP-CIDR,172.16.0.0/12,DIRECT,no-resolve
IP-CIDR,100.64.0.0/10,DIRECT,no-resolve
IP-CIDR,127.0.0.1/32,DIRECT,no-resolve
DOMAIN-KEYWORD,mirrorakam,DIRECT
RULE-SET,https://cdn.jsdelivr.net/gh/Loyalsoldier/surge-rules@release/ruleset/direct.txt,DIRECT
GEOIP,CN,DIRECT,no-resolve

# 6. 最终兜底
FINAL,PROXY
"""


def generate_vless_url(server_ip, port, uuid, public_key, short_id, sni="www.apple.com", node_name="🇺🇸 独享-Claude-原生住宅9929"):
    encoded_name = urllib.parse.quote(node_name)
    return (
        f"vless://{uuid}@{server_ip}:{port}?"
        f"security=reality&encryption=none&pbk={public_key}&"
        f"headerType=none&fp=chrome&type=tcp&flow=xtls-rprx-vision&"
        f"sni={sni}&sid={short_id}#{encoded_name}"
    )


def main():
    parser = argparse.ArgumentParser(description="Generate Clash Verge/Mihomo Profile & Shadowrocket Conf for Claude Anti-Ban VPS")
    parser.add_argument("--json-input", help="Path to JSON output file from vps_setup.sh")
    parser.add_argument("--ip", help="Server IPv4 address")
    parser.add_argument("--port", type=int, default=24433, help="Xray Reality port (default: 24433)")
    parser.add_argument("--uuid", help="User UUID")
    parser.add_argument("--public-key", help="Reality Public Key")
    parser.add_argument("--short-id", help="Reality Short ID")
    parser.add_argument("--sni", default="www.apple.com", help="Reality SNI (default: www.apple.com)")
    parser.add_argument("--flow", default="xtls-rprx-vision", help="Flow (default: xtls-rprx-vision)")
    parser.add_argument("--fingerprint", default="chrome", help="Client fingerprint (default: chrome)")
    parser.add_argument("--name", default="🇺🇸 独享-Claude-原生住宅9929", help="Node Display Name")
    parser.add_argument("--output", default="Claude-US-Residential-9929.yaml", help="Output YAML file path")
    parser.add_argument("--sr-output", help="Output Shadowrocket .conf file path (default: derived from --output)")

    args = parser.parse_args()

    params = {
        "server_ip": args.ip,
        "port": args.port,
        "uuid": args.uuid,
        "public_key": args.public_key,
        "short_id": args.short_id,
        "sni": args.sni,
        "flow": args.flow,
        "fingerprint": args.fingerprint,
        "node_name": args.name
    }

    if args.json_input and os.path.exists(args.json_input):
        with open(args.json_input, "r", encoding="utf-8") as f:
            data = json.load(f)
            params["server_ip"] = data.get("server_ip", params["server_ip"])
            params["port"] = data.get("port", params["port"])
            params["uuid"] = data.get("uuid", params["uuid"])
            params["public_key"] = data.get("public_key", params["public_key"])
            params["short_id"] = data.get("short_id", params["short_id"])
            params["sni"] = data.get("sni", params["sni"])
            params["flow"] = data.get("flow", params["flow"])
            params["fingerprint"] = data.get("fingerprint", params["fingerprint"])

    required_keys = ["server_ip", "port", "uuid", "public_key", "short_id"]
    for k in required_keys:
        if not params.get(k):
            print(f"Error: Missing required parameter '--{k.replace('_', '-')}'", file=sys.stderr)
            sys.exit(1)

    yaml_content = TEMPLATE_YAML.format(**params)
    out_path = os.path.abspath(args.output)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(yaml_content)

    if args.sr_output:
        sr_out_path = os.path.abspath(args.sr_output)
    else:
        base, _ = os.path.splitext(out_path)
        sr_out_path = f"{base}.conf"
    os.makedirs(os.path.dirname(sr_out_path) or ".", exist_ok=True)
    with open(sr_out_path, "w", encoding="utf-8") as f:
        f.write(TEMPLATE_SHADOWROCKET_CONF)

    vless_link = generate_vless_url(
        params["server_ip"],
        params["port"],
        params["uuid"],
        params["public_key"],
        params["short_id"],
        params["sni"],
        params["node_name"]
    )

    print(f"\n[SUCCESS] Generated Clash YAML Profile: {out_path}")
    print(f"[SUCCESS] Generated Shadowrocket Conf:  {sr_out_path}")
    print("\n[VLESS Share Link (for iOS Shadowrocket / Sing-box / Loon)]:")
    print(vless_link)
    print("")


if __name__ == "__main__":
    main()

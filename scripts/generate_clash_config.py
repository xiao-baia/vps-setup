#!/usr/bin/env python3
"""
Generate a hardened, anti-leak Clash Verge / Mihomo YAML profile and VLESS Share Link
from VPS setup output.
Matches the exact production architecture of Claude-US-Residential-9929.yaml.
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
    "geosite:cn,private":
      - "https://dns.alidns.com/dns-query"
      - "https://doh.pub/dns-query"
  nameserver:
    - "https://dns.alidns.com/dns-query"
    - "https://doh.pub/dns-query"
  fallback:
    - "https://cloudflare-dns.com/dns-query#🚀 独享-AI与代码"
    - "https://1.1.1.1/dns-query#🚀 独享-AI与代码"
  fallback-filter:
    geoip: true
    geoip-code: CN
    ipcidr:
      - 240.0.0.0/4
      - 0.0.0.0/32

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
      - DIRECT

  - name: "🌐 谷歌与Gemini"
    type: select
    proxies:
      - "{node_name}"
      - DIRECT

  - name: "🐟 漏网之鱼"
    type: select
    proxies:
      - "{node_name}"
      - DIRECT

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
  # 5. 国内网站与内网直连（no-resolve 杜绝本地 DNS 泄漏）
  # ==========================================
  - GEOSITE,private,DIRECT
  - GEOIP,lan,DIRECT,no-resolve
  - GEOSITE,cn,DIRECT
  - GEOIP,cn,DIRECT,no-resolve

  # ==========================================
  # 6. 最终兜底（走国外代理）
  # ==========================================
  - MATCH,🐟 漏网之鱼
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
    parser = argparse.ArgumentParser(description="Generate Clash Verge/Mihomo Profile for Claude Anti-Ban VPS")
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
    print("\n[VLESS Share Link (for iOS Shadowrocket / Sing-box / Loon)]:")
    print(vless_link)
    print("")

if __name__ == "__main__":
    main()

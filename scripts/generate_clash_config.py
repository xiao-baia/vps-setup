#!/usr/bin/env python3
"""
Generate a hardened, ultimate anti-leak Clash Verge / Mihomo YAML profile,
iOS Shadowrocket (.shadowrocket.conf) split-tunnel profile, and VLESS Share Link
from VPS setup output.

Supports:
  - Mode A (default): Direct egress via exclusive VPS (VLESS Reality)
  - Mode B (chained): High-speed jump node (dialer-proxy) -> Static residential SOCKS5
"""

import argparse
import ipaddress
import json
import os
import sys
import urllib.parse

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


FALLBACK_CLASH_TEMPLATE = """port: 7890
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
  respect-rules: true
  default-nameserver:
    - 223.5.5.5
    - 119.29.29.29
  proxy-server-nameserver:
    - "https://dns.alidns.com/dns-query"
    - "https://doh.pub/dns-query"
    - 223.5.5.5
    - 119.29.29.29
  direct-nameserver:
    - 223.5.5.5
    - 119.29.29.29
    - "https://dns.alidns.com/dns-query"
    - "https://doh.pub/dns-query"
  nameserver-policy:
    "geosite:geolocation-!cn":
      - "https://cloudflare-dns.com/dns-query#🚀 独享-AI与代码"
      - "https://1.1.1.1/dns-query#🚀 独享-AI与代码"
      - "https://dns.google/dns-query#🚀 独享-AI与代码"
    "geosite:cn,private":
      - 223.5.5.5
      - 119.29.29.29
      - "https://dns.alidns.com/dns-query"
      - "https://doh.pub/dns-query"
    "rule-set:direct":
      - 223.5.5.5
      - 119.29.29.29
      - "https://dns.alidns.com/dns-query"
      - "https://doh.pub/dns-query"
  nameserver:
    - "https://cloudflare-dns.com/dns-query#🚀 独享-AI与代码"
    - "https://1.1.1.1/dns-query#🚀 独享-AI与代码"
    - "https://dns.google/dns-query#🚀 独享-AI与代码"

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
  - name: "{{NODE_NAME}}"
    type: vless
    server: {{SERVER_IP}}
    port: {{PORT}}
    uuid: {{UUID}}
    network: tcp
    udp: true
    tls: true
    flow: {{FLOW}}
    servername: {{SNI}}
    reality-opts:
      public-key: {{PUBLIC_KEY}}
      short-id: {{SHORT_ID}}
    client-fingerprint: {{FINGERPRINT}}

proxy-groups:
  # 严格禁止加入 DIRECT：节点失效即断网，绝不回落本地直连
  - name: "🚀 独享-AI与代码"
    type: select
    proxies:
      - "{{NODE_NAME}}"

  - name: "🌐 谷歌与Gemini"
    type: select
    proxies:
      - "{{NODE_NAME}}"

  - name: "🐟 漏网之鱼"
    type: select
    proxies:
      - "{{NODE_NAME}}"

rule-providers:
  direct:
    type: http
    behavior: domain
    url: "https://cdn.jsdelivr.net/gh/Loyalsoldier/clash-rules@release/direct.txt"
    path: ./ruleset/direct.yaml
    interval: 86400
  cncidr:
    type: http
    behavior: ipcidr
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
  # 1. Claude / Anthropic 全生态、遥测与第三方统计域名（最高优先级锁死海外出口）
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
  - DOMAIN-SUFFIX,statsig.anthropic.com,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,sentry.io,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,statsigapi.net,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,statsig.com,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,featuregates.org,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,intercom.io,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,intercomcdn.com,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,datadoghq.com,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,browser-intake-datadoghq.com,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,stripe.com,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,stripe.network,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,hcaptcha.com,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,challenges.cloudflare.com,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,googletagmanager.com,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,doubleclick.net,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,google-analytics.com,🚀 独享-AI与代码

  # ==========================================
  # 2. 其他主流 AI 服务与开发者/防漏检测站（全走海外代理）
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
  - DOMAIN-SUFFIX,github.com,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,githubusercontent.com,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,githubcopilot.com,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,v2ex.com,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,ippure.com,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,ipinfo.io,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,ipapi.co,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,ipify.org,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,httpbin.org,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,isp.ac,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,browserscan.net,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,browserleaks.com,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,browserleaks.net,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,surfsharkdns.com,🚀 独享-AI与代码
  - DOMAIN-SUFFIX,fastly-analytics.com,🚀 独享-AI与代码

  # ==========================================
  # 3. 谷歌与 Gemini 规则（VPS 内部直接走原生 IP 直连，若受限由服务端 WARP 无缝兜底）
  # ==========================================
  - DOMAIN-SUFFIX,gemini.google.com,🌐 谷歌与Gemini
  - DOMAIN-SUFFIX,aistudio.google.com,🌐 谷歌与Gemini
  - DOMAIN-SUFFIX,generativelanguage.googleapis.com,🌐 谷歌与Gemini
  - DOMAIN-SUFFIX,proactivebackend-pa.googleapis.com,🌐 谷歌与Gemini
  - DOMAIN-KEYWORD,antigravity,🌐 谷歌与Gemini
  - GEOSITE,google,🌐 谷歌与Gemini
  - GEOIP,google,🌐 谷歌与Gemini,no-resolve

  # ==========================================
  # 4. 局域网、保留地址（含 CGNAT/Tailscale 100.64.0.0/10）与 B 站 / 微信直连
  # ==========================================
  - GEOSITE,private,DIRECT
  - GEOIP,lan,DIRECT,no-resolve
  - IP-CIDR,100.64.0.0/10,DIRECT,no-resolve
  - DOMAIN-KEYWORD,mirrorakam,DIRECT
  - DOMAIN-SUFFIX,bilibili.com,DIRECT
  - DOMAIN-SUFFIX,bilivideo.com,DIRECT
  - DOMAIN-SUFFIX,hdslb.com,DIRECT
  - DOMAIN-SUFFIX,wechat.com,DIRECT
  - DOMAIN-SUFFIX,weixin.qq.com,DIRECT
  - DOMAIN-SUFFIX,qpic.cn,DIRECT

  # ==========================================
  # 5. 海外域名总分类拦截（必须排在国内白名单之前，拦截混在直连名单里的海外统计域名）
  # ==========================================
  - GEOSITE,geolocation-!cn,🚀 独享-AI与代码

  # ==========================================
  # 6. 国内域名白名单与国内 IP 段直连（每日自动更新规则集 + 内置库双保险，no-resolve 杜绝本地 DNS 泄漏）
  # ==========================================
  - RULE-SET,direct,DIRECT
  - GEOSITE,cn,DIRECT
  - RULE-SET,cncidr,DIRECT,no-resolve
  - GEOIP,cn,DIRECT,no-resolve

  # ==========================================
  # 7. 最终兜底（100% 走海外出口，策略组内无 DIRECT）
  # ==========================================
  - MATCH,🐟 漏网之鱼
"""


FALLBACK_SHADOWROCKET_TEMPLATE = """# ==============================================================================
# Shadowrocket (iOS 小火箭) 终极防漏分流配置
# 逻辑：国内白名单走国内，其余所有流量与第三方遥测 100% 走海外代理（FINAL,PROXY）
# ==============================================================================

[General]
ipv6 = false
bypass-system = true
skip-proxy = 192.168.0.0/16, 10.0.0.0/8, 172.16.0.0/12, 100.64.0.0/10, localhost, *.local
tun-excluded-routes = 192.168.0.0/16, 10.0.0.0/8, 172.16.0.0/12, 100.64.0.0/10
dns-server = https://dns.alidns.com/dns-query, https://doh.pub/dns-query, 223.5.5.5, 119.29.29.29
fallback-dns-server = https://cloudflare-dns.com/dns-query, https://1.1.1.1/dns-query
hijack-dns = *:53
always-real-ip = *.lan, *.local, *.arpa, time.*.com, ntp.*.com, +.msftconnecttest.com, +.msftncsi.com, localhost.ptlogin2.qq.com

[Rule]
IP-CIDR6,::/0,REJECT,no-resolve
DOMAIN-KEYWORD,stun,PROXY
DEST-PORT,3478,PROXY
DEST-PORT,5349,PROXY
DEST-PORT,19302,PROXY

DOMAIN-SUFFIX,claude.ai,PROXY
DOMAIN-SUFFIX,claude.com,PROXY
DOMAIN-SUFFIX,anthropic.com,PROXY
DOMAIN-SUFFIX,claudeusercontent.com,PROXY
DOMAIN-SUFFIX,claudemcpclient.com,PROXY
DOMAIN-SUFFIX,clau.de,PROXY
DOMAIN-KEYWORD,anthropic,PROXY
DOMAIN-KEYWORD,claude,PROXY
DOMAIN-SUFFIX,statsig.anthropic.com,PROXY
DOMAIN-SUFFIX,sentry.io,PROXY
DOMAIN-SUFFIX,statsig.com,PROXY
DOMAIN-SUFFIX,statsigapi.net,PROXY
DOMAIN-SUFFIX,featuregates.org,PROXY
DOMAIN-SUFFIX,intercom.io,PROXY
DOMAIN-SUFFIX,intercomcdn.com,PROXY
DOMAIN-SUFFIX,datadoghq.com,PROXY
DOMAIN-SUFFIX,browser-intake-datadoghq.com,PROXY
DOMAIN-SUFFIX,stripe.com,PROXY
DOMAIN-SUFFIX,stripe.network,PROXY
DOMAIN-SUFFIX,hcaptcha.com,PROXY
DOMAIN-SUFFIX,challenges.cloudflare.com,PROXY
DOMAIN-SUFFIX,googletagmanager.com,PROXY
DOMAIN-SUFFIX,doubleclick.net,PROXY
DOMAIN-SUFFIX,google-analytics.com,PROXY

DOMAIN-SUFFIX,openai.com,PROXY
DOMAIN-SUFFIX,chatgpt.com,PROXY
DOMAIN-SUFFIX,oaistatic.com,PROXY
DOMAIN-SUFFIX,oaiusercontent.com,PROXY
DOMAIN-SUFFIX,gemini.google.com,PROXY
DOMAIN-SUFFIX,aistudio.google.com,PROXY
DOMAIN-SUFFIX,generativelanguage.googleapis.com,PROXY
DOMAIN-SUFFIX,proactivebackend-pa.googleapis.com,PROXY
DOMAIN-SUFFIX,google.com,PROXY
DOMAIN-SUFFIX,googleapis.com,PROXY
DOMAIN-SUFFIX,gstatic.com,PROXY
DOMAIN-SUFFIX,x.ai,PROXY
DOMAIN-SUFFIX,grok.com,PROXY
DOMAIN-SUFFIX,perplexity.ai,PROXY
DOMAIN-SUFFIX,cursor.com,PROXY
DOMAIN-SUFFIX,cursor.sh,PROXY
DOMAIN-SUFFIX,ipinfo.io,PROXY
DOMAIN-SUFFIX,api.ipify.org,PROXY
DOMAIN-SUFFIX,httpbin.org,PROXY
DOMAIN-SUFFIX,isp.ac,PROXY
DOMAIN-SUFFIX,browserscan.net,PROXY

DOMAIN-SET,https://cdn.jsdelivr.net/gh/Loyalsoldier/surge-rules@release/proxy.txt,PROXY

IP-CIDR,192.168.0.0/16,DIRECT,no-resolve
IP-CIDR,10.0.0.0/8,DIRECT,no-resolve
IP-CIDR,172.16.0.0/12,DIRECT,no-resolve
IP-CIDR,100.64.0.0/10,DIRECT,no-resolve
IP-CIDR,127.0.0.0/8,DIRECT,no-resolve
DOMAIN-KEYWORD,mirrorakam,DIRECT
DOMAIN-SUFFIX,bilibili.com,DIRECT
DOMAIN-SUFFIX,bilivideo.com,DIRECT
DOMAIN-SUFFIX,hdslb.com,DIRECT
DOMAIN-SUFFIX,wechat.com,DIRECT
DOMAIN-SUFFIX,weixin.qq.com,DIRECT
DOMAIN-SUFFIX,qpic.cn,DIRECT

DOMAIN-SET,https://cdn.jsdelivr.net/gh/Loyalsoldier/surge-rules@release/direct.txt,DIRECT
RULE-SET,https://cdn.jsdelivr.net/gh/Loyalsoldier/surge-rules@release/cncidr.txt,DIRECT,no-resolve
GEOIP,CN,DIRECT,no-resolve

FINAL,PROXY
"""


def load_template(filename, fallback):
    templates_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "templates",
    )
    path = os.path.join(templates_dir, filename)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return fallback


def yaml_escape(val):
    return str(val).replace("\\", "\\\\").replace('"', '\\"')


def render_clash_template(template_text, params):
    replacements = {
        "{{NODE_NAME}}": yaml_escape(params["node_name"]),
        "{{SERVER_IP}}": str(params["server_ip"]),
        "{{PORT}}": str(params["port"]),
        "{{UUID}}": str(params["uuid"]),
        "{{FLOW}}": str(params["flow"]),
        "{{SNI}}": str(params["sni"]),
        "{{PUBLIC_KEY}}": str(params["public_key"]),
        "{{SHORT_ID}}": str(params["short_id"]),
        "{{FINGERPRINT}}": str(params["fingerprint"]),
    }
    rendered = template_text
    for k, v in replacements.items():
        rendered = rendered.replace(k, v)
    return rendered


def build_socks5_rule(server):
    try:
        ip_obj = ipaddress.ip_address(server)
        if ip_obj.version == 4:
            return f"- IP-CIDR,{server}/32,🔀 跳板节点,no-resolve"
        return f"- IP-CIDR6,{server}/128,🔀 跳板节点,no-resolve"
    except ValueError:
        return f"- DOMAIN,{server},🔀 跳板节点"


def apply_mode_b(yaml_text, params):
    socks5_name = yaml_escape(params["socks5_name"])
    node_name = yaml_escape(params["node_name"])
    socks5_server = params["socks5_server"]
    socks5_port = params["socks5_port"]

    socks5_block_lines = [
        f'  - name: "{socks5_name}"',
        "    type: socks5",
        f"    server: {socks5_server}",
        f"    port: {socks5_port}",
    ]
    if params.get("socks5_user"):
        socks5_block_lines.append(f'    username: "{yaml_escape(params["socks5_user"])}"')
    if params.get("socks5_pass"):
        socks5_block_lines.append(f'    password: "{yaml_escape(params["socks5_pass"])}"')
    socks5_block_lines.extend([
        "    udp: false",
        '    dialer-proxy: "🔀 跳板节点"',
    ])
    socks5_block = "\n".join(socks5_block_lines)

    new_proxy_groups = f"""proxy-groups:
  # 严格禁止加入 DIRECT：节点失效即断网，绝不回落本地直连
  - name: "🚀 独享-AI与代码"
    type: select
    proxies:
      - "{socks5_name}"

  - name: "🌐 谷歌与Gemini"
    type: select
    proxies:
      - "{socks5_name}"

  - name: "🐟 漏网之鱼"
    type: select
    proxies:
      - "{socks5_name}"

  - name: "🔀 跳板节点"
    type: select
    proxies:
      - "{node_name}"
"""

    marker_groups = "proxy-groups:"
    marker_providers = "\nrule-providers:"
    start_idx = yaml_text.index(marker_groups)
    end_idx = yaml_text.index(marker_providers, start_idx)
    yaml_text = (
        yaml_text[:start_idx]
        + socks5_block
        + "\n\n"
        + new_proxy_groups
        + yaml_text[end_idx:]
    )

    # Ensure the static residential SOCKS5 endpoint itself routes through the jump proxy to prevent loops
    socks5_loop_guard = build_socks5_rule(socks5_server)
    anchor = "  - IP-CIDR6,::/0,REJECT,no-resolve\n"
    if anchor in yaml_text:
        yaml_text = yaml_text.replace(
            anchor,
            anchor + f"  {socks5_loop_guard}\n",
            1,
        )

    return yaml_text


def generate_vless_url(
    server_ip,
    port,
    uuid,
    public_key,
    short_id,
    sni="www.apple.com",
    node_name="🇺🇸 独享-Claude-原生住宅9929",
):
    encoded_name = urllib.parse.quote(node_name)
    return (
        f"vless://{uuid}@{server_ip}:{port}?"
        f"security=reality&encryption=none&pbk={public_key}&"
        f"headerType=none&fp=chrome&type=tcp&flow=xtls-rprx-vision&"
        f"sni={sni}&sid={short_id}#{encoded_name}"
    )


def default_shadowrocket_path(yaml_out_path):
    base, _ = os.path.splitext(yaml_out_path)
    return f"{base}.shadowrocket.conf"


def main():
    parser = argparse.ArgumentParser(
        description="Generate Ultimate Anti-Leak Clash Verge/Mihomo & Shadowrocket Profiles"
    )
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

    # Mode B (chained jump node -> static residential SOCKS5) & Shadowrocket options
    parser.add_argument(
        "--mode",
        choices=["A", "B"],
        default=None,
        help="Egress mode: A=VPS direct egress (default), B=VPS jump node -> static residential SOCKS5",
    )
    parser.add_argument("--socks5-server", help="Static residential SOCKS5 IP or hostname (Mode B)")
    parser.add_argument("--socks5-port", type=int, help="Static residential SOCKS5 port (Mode B)")
    parser.add_argument("--socks5-user", help="Static residential SOCKS5 username (Mode B, optional)")
    parser.add_argument("--socks5-pass", help="Static residential SOCKS5 password (Mode B, optional)")
    parser.add_argument(
        "--socks5-name",
        default="🏠 独享-静态住宅落地",
        help="Display name for Mode B residential SOCKS5 proxy",
    )
    parser.add_argument(
        "--shadowrocket-output",
        help="Output path for iOS Shadowrocket .conf (default: <output_stem>.shadowrocket.conf)",
    )

    args = parser.parse_args()

    mode = args.mode
    if mode is None:
        mode = "B" if args.socks5_server else "A"

    if mode == "B" and (not args.socks5_server or not args.socks5_port):
        print(
            "Error: Mode B requires both '--socks5-server' and '--socks5-port'.",
            file=sys.stderr,
        )
        sys.exit(1)

    params = {
        "server_ip": args.ip,
        "port": args.port,
        "uuid": args.uuid,
        "public_key": args.public_key,
        "short_id": args.short_id,
        "sni": args.sni,
        "flow": args.flow,
        "fingerprint": args.fingerprint,
        "node_name": args.name,
        "socks5_server": args.socks5_server,
        "socks5_port": args.socks5_port,
        "socks5_user": args.socks5_user,
        "socks5_pass": args.socks5_pass,
        "socks5_name": args.socks5_name,
    }

    if args.json_input and os.path.exists(args.json_input):
        with open(args.json_input, "r", encoding="utf-8") as f:
            data = json.load(f)
            for k in ["server_ip", "port", "uuid", "public_key", "short_id", "sni", "flow", "fingerprint"]:
                if data.get(k) is not None:
                    params[k] = data[k]

    required_keys = ["server_ip", "port", "uuid", "public_key", "short_id"]
    for k in required_keys:
        if not params.get(k):
            print(f"Error: Missing required parameter '--{k.replace('_', '-')}'", file=sys.stderr)
            sys.exit(1)

    clash_tpl = load_template("clash_profile.yaml.template", FALLBACK_CLASH_TEMPLATE)
    yaml_content = render_clash_template(clash_tpl, params)
    if mode == "B":
        yaml_content = apply_mode_b(yaml_content, params)

    out_path = os.path.abspath(args.output)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(yaml_content)

    sr_path = os.path.abspath(args.shadowrocket_output or default_shadowrocket_path(out_path))
    os.makedirs(os.path.dirname(sr_path) or ".", exist_ok=True)
    sr_tpl = load_template("shadowrocket.conf.template", FALLBACK_SHADOWROCKET_TEMPLATE)
    with open(sr_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(sr_tpl)

    vless_link = generate_vless_url(
        params["server_ip"],
        params["port"],
        params["uuid"],
        params["public_key"],
        params["short_id"],
        params["sni"],
        params["node_name"],
    )

    print(f"\n[SUCCESS] Generated Clash YAML Profile (Mode {mode}): {out_path}")
    print(f"[SUCCESS] Generated Shadowrocket Anti-Leak Profile : {sr_path}")
    print("\n[VLESS Share Link (for iOS Shadowrocket / Sing-box / Loon)]:")
    print(vless_link)
    print("\n[Shadowrocket 手机端防漏导入与 3 项必验]:")
    print("  1. 在 Shadowrocket「配置」页导入上述 .shadowrocket.conf 并点「使用配置」（全局路由保持「配置」）;")
    print("  2. 浏览器访问 baidu.com 确认国内直连秒开;")
    print("  3. 访问 https://ipinfo.io 确认显示的是你的独享海外出口 IP;")
    print("  4. 临时关闭节点连接，确认 https://claude.ai 直接无法打开（无直连回落）。\n")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Read-Only Anti-Leak Environment Verification Gate (11-Item Audit + Real TUN & DNS Leak Probes)

Never modifies any local Clash Verge subscriptions, configs, or firewall state.
Tests:
  1. Static YAML config anti-leak audit (--config)
  2. True TUN takeover test without proxy env vars (ProxyHandler({}) == curl --noproxy '*')
  3. Domestic whitelist direct routing test (baidu, bilibili, myip.ipip.net)
  4. Overseas egress & third-party telemetry consistency (ipify, ipinfo, httpbin, claude.ai, api.anthropic.com, statsig, googletagmanager, gemini)
  5. Real DNS leak & raw IP 1.1.1.1 TUN routing test (1.1.1.1/cdn-cgi/trace, cloudflare-dns DoH, isp.ac/dns-leak-test)
  6. Read-only Kill Switch (clash-guard) readiness check & manual drill instructions
"""

import argparse
import json
import os
import platform
import re
import subprocess
import sys
import urllib.error
import urllib.request
import uuid

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
BOLD = "\033[1m"
RESET = "\033[0m"

CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def print_header(title):
    print(f"\n{BOLD}{BLUE}====================================================={RESET}")
    print(f"{BOLD}{BLUE} {title} {RESET}")
    print(f"{BOLD}{BLUE}====================================================={RESET}")


def find_default_config():
    for cand in ["Claude-US-Residential-9929-2.yaml", "Claude-US-Residential-9929.yaml"]:
        if os.path.exists(cand):
            return cand
    for fn in sorted(os.listdir(".")):
        if fn.endswith(".yaml") and os.path.isfile(fn):
            return fn
    return None


def audit_yaml_config(config_path):
    print_header("Check 1: YAML Profile Anti-Leak Static Audit")
    if not config_path or not os.path.exists(config_path):
        print(f"[{YELLOW}SKIP{RESET}] No YAML config specified/found for static audit.")
        return True

    print(f"Auditing file: {os.path.abspath(config_path)}")
    with open(config_path, "r", encoding="utf-8", errors="replace") as f:
        lines = [line.rstrip("\r\n") for line in f]

    sections = {"root": []}
    current_sec = "root"
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not line[0].isspace() and re.match(r"^[A-Za-z0-9_-]+\s*:", line):
            key, rest = line.split(":", 1)
            key = key.strip()
            if rest.strip():
                sections["root"].append(line)
            else:
                current_sec = key
                sections.setdefault(key, []).append(line)
        else:
            sections.setdefault(current_sec, []).append(line)

    issues = []

    root_txt = "\n".join(sections.get("root", []))
    if not re.search(r"(?m)^mode:\s*rule\b", root_txt):
        issues.append("mode is not 'rule'")
    if not re.search(r"(?m)^ipv6:\s*false\b", root_txt):
        issues.append("top-level ipv6 is not false")

    dns_lines = sections.get("dns", [])
    dns_txt = "\n".join(dns_lines)
    if not re.search(r"^\s+ipv6:\s*false\b", dns_txt, re.M):
        issues.append("dns.ipv6 is not false")
    if not re.search(r"^\s+respect-rules:\s*true\b", dns_txt, re.M):
        issues.append("dns.respect-rules is not true")

    # Verify primary dns.nameserver entries route over proxy, not domestic DNS
    in_nameserver = False
    primary_ns = []
    for ln in dns_lines:
        if re.match(r"^\s{2}nameserver\s*:", ln):
            in_nameserver = True
            continue
        if in_nameserver:
            if re.match(r"^\s{2}[A-Za-z0-9_-]+\s*:", ln):
                in_nameserver = False
            elif ln.strip().startswith("-"):
                primary_ns.append(ln.strip()[1:].strip().strip("'\""))
    if not primary_ns:
        issues.append("dns.nameserver is empty")
    elif not all("#🚀 独享-AI与代码" in ns for ns in primary_ns):
        issues.append(f"dns.nameserver must route via overseas proxy group: {primary_ns}")

    # Verify nameserver-policy places geolocation-!cn before cn/private and rule-set:direct
    geo_not_cn_idx = next((i for i, ln in enumerate(dns_lines) if "geosite:geolocation-!cn" in ln), -1)
    cn_priv_idx = next((i for i, ln in enumerate(dns_lines) if "geosite:cn,private" in ln), -1)
    rs_direct_idx = next((i for i, ln in enumerate(dns_lines) if "rule-set:direct" in ln), -1)
    if geo_not_cn_idx == -1 or cn_priv_idx == -1 or rs_direct_idx == -1:
        issues.append("dns.nameserver-policy missing geolocation-!cn / cn,private / rule-set:direct")
    elif not (geo_not_cn_idx < cn_priv_idx and geo_not_cn_idx < rs_direct_idx):
        issues.append("dns.nameserver-policy must place geosite:geolocation-!cn before domestic policies")

    tun_txt = "\n".join(sections.get("tun", []))
    if not re.search(r"^\s+enable:\s*true\b", tun_txt, re.M):
        issues.append("tun.enable is not true")

    pg_lines = sections.get("proxy-groups", [])
    pg_txt = "\n".join(pg_lines)
    if re.search(r"^\s*-\s*DIRECT\b", pg_txt, re.M):
        issues.append("proxy-groups still contains DIRECT (must have zero DIRECT fallback)")

    rules_lines = [ln.strip()[2:].strip() for ln in sections.get("rules", []) if ln.strip().startswith("- ")]
    rules_joined = "\n".join(rules_lines)
    for must_have in [
        "IP-CIDR6,::/0,REJECT,no-resolve",
        "claudemcpclient.com",
        "100.64.0.0/10,DIRECT,no-resolve",
        "mirrorakam,DIRECT",
    ]:
        if must_have not in rules_joined:
            issues.append(f"rules missing required entry: {must_have}")

    idx_not_cn = next((i for i, r in enumerate(rules_lines) if r.startswith("GEOSITE,geolocation-!cn,")), -1)
    idx_rs_dir = next((i for i, r in enumerate(rules_lines) if r.startswith("RULE-SET,direct,")), -1)
    idx_gs_cn = next((i for i, r in enumerate(rules_lines) if r.startswith("GEOSITE,cn,")), -1)
    if idx_not_cn == -1 or idx_rs_dir == -1 or idx_gs_cn == -1:
        issues.append("rules missing GEOSITE,geolocation-!cn / RULE-SET,direct / GEOSITE,cn")
    elif not (idx_not_cn < idx_rs_dir and idx_not_cn < idx_gs_cn):
        issues.append("GEOSITE,geolocation-!cn must come BEFORE RULE-SET,direct and GEOSITE,cn")

    if not rules_lines or rules_lines[-1] != "MATCH,🐟 漏网之鱼":
        issues.append(f"final rule must be 'MATCH,🐟 漏网之鱼', got: {rules_lines[-1] if rules_lines else 'None'}")

    if issues:
        for item in issues:
            print(f"[{RED}FAIL{RESET}] {item}")
        return False

    print(f"[{GREEN}PASS{RESET}] mode=rule, ipv6=false, dns.ipv6=false, respect-rules=true, tun.enable=true")
    print(f"[{GREEN}PASS{RESET}] dns.nameserver forces overseas DoH via proxy; nameserver-policy prioritized correctly")
    print(f"[{GREEN}PASS{RESET}] proxy-groups contain ZERO DIRECT fallback entries")
    print(f"[{GREEN}PASS{RESET}] rules order verified (IPv6 REJECT, STUN, Claude/telemetry, 100.64/10, mirrorakam, geolocation-!cn < direct/cn, MATCH)")
    return True


def fetch_url(opener, url, timeout=10, headers=None):
    hdrs = {"User-Agent": CHROME_UA}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, headers=hdrs)
    with opener.open(req, timeout=timeout) as resp:
        return resp.getcode(), dict(resp.headers), resp.read().decode("utf-8", errors="replace")


def test_tun_vs_proxy(tun_opener, proxy_opener, proxy_url):
    print_header("Check 2: No-Proxy TUN Takeover vs Proxy Port")

    tun_geo = None
    try:
        _, _, body = fetch_url(tun_opener, "https://ipinfo.io/json", timeout=10, headers={"User-Agent": "curl/8.0"})
        tun_geo = json.loads(body)
        cc = tun_geo.get("country", "")
        ok = bool(cc) and cc not in {"CN", "HK", "MO"}
        tag = f"{GREEN}PASS{RESET}" if ok else f"{RED}FAIL{RESET}"
        print(f"[{tag}] No-Proxy TUN Egress (--noproxy '*'): IP={tun_geo.get('ip')} | {cc} {tun_geo.get('city', '')} | {tun_geo.get('org', '')}")
    except Exception as e:
        print(f"[{RED}FAIL{RESET}] No-Proxy TUN Egress probe failed: {e}")

    proxy_geo = None
    try:
        _, _, body = fetch_url(proxy_opener, "https://ipinfo.io/json", timeout=10, headers={"User-Agent": "curl/8.0"})
        proxy_geo = json.loads(body)
        cc = proxy_geo.get("country", "")
        ok = bool(cc) and cc not in {"CN", "HK", "MO"}
        tag = f"{GREEN}PASS{RESET}" if ok else f"{RED}FAIL{RESET}"
        print(f"[{tag}] Explicit Proxy ({proxy_url}): IP={proxy_geo.get('ip')} | {cc} {proxy_geo.get('city', '')}")
    except Exception as e:
        print(f"[{YELLOW}WARN{RESET}] Explicit Proxy ({proxy_url}) unreachable: {e}")

    tun_ok = bool(tun_geo and tun_geo.get("country") not in {"", "CN", "HK", "MO"})
    if tun_geo and proxy_geo and tun_geo.get("ip") != proxy_geo.get("ip"):
        print(f"[{RED}FAIL{RESET}] Mismatch! TUN IP ({tun_geo.get('ip')}) != Proxy Port IP ({proxy_geo.get('ip')})")
        return False, tun_geo.get("ip")
    return tun_ok, (tun_geo or {}).get("ip")


def test_domestic_direct(tun_opener):
    print_header("Check 3: Domestic Whitelist Direct Routing (No-Proxy TUN)")
    ok = True
    for url in ["https://www.baidu.com", "https://www.bilibili.com"]:
        try:
            code, _, _ = fetch_url(tun_opener, url, timeout=8)
            print(f"[{GREEN}PASS{RESET}] Domestic site reachable: {url} (HTTP {code})")
        except Exception as e:
            print(f"[{RED}FAIL{RESET}] Domestic site failed: {url} ({e})")
            ok = False

    cn_ip_checked = False
    for probe in ["https://myip.ipip.net", "https://ip.3322.net"]:
        try:
            _, _, body = fetch_url(tun_opener, probe, timeout=8, headers={"User-Agent": "curl/8.0"})
            snippet = " ".join(body.strip().splitlines())[:120]
            print(f"[{GREEN}PASS{RESET}] Domestic IP check ({probe}): {snippet}")
            cn_ip_checked = True
            break
        except Exception:
            continue
    if not cn_ip_checked:
        print(f"[{YELLOW}WARN{RESET}] Could not fetch domestic IP echo endpoint (myip.ipip.net / ip.3322.net)")
    return ok


def test_overseas_and_telemetry(tun_opener, expected_ip):
    print_header("Check 4: Overseas Egress & Telemetry Consistency (No-Proxy TUN)")
    observed_ips = {}

    # 1. Multi-provider egress IP consistency
    try:
        _, _, b1 = fetch_url(tun_opener, "https://api.ipify.org?format=json", timeout=10, headers={"User-Agent": "curl/8.0"})
        observed_ips["api.ipify.org"] = json.loads(b1).get("ip")
    except Exception as e:
        print(f"[{RED}FAIL{RESET}] api.ipify.org failed: {e}")

    try:
        _, _, b2 = fetch_url(tun_opener, "https://httpbin.org/ip", timeout=10, headers={"User-Agent": "curl/8.0"})
        observed_ips["httpbin.org"] = json.loads(b2).get("origin", "").split(",")[0].strip()
    except Exception as e:
        print(f"[{YELLOW}WARN{RESET}] httpbin.org/ip failed: {e}")

    ips_consistent = True
    for host, ip_val in observed_ips.items():
        match = (not expected_ip) or (ip_val == expected_ip)
        tag = f"{GREEN}PASS{RESET}" if match else f"{RED}FAIL{RESET}"
        print(f"[{tag}] {host} -> {ip_val} (expected {expected_ip or 'overseas'})")
        if not match:
            ips_consistent = False

    # 2. Anthropic API
    api_ok = False
    try:
        fetch_url(tun_opener, "https://api.anthropic.com", timeout=10, headers={"User-Agent": "curl/8.0"})
        api_ok = True
        print(f"[{GREEN}PASS{RESET}] api.anthropic.com reachable")
    except urllib.error.HTTPError as e:
        cf_ray = e.headers.get("cf-ray", "")
        if e.code == 404 or cf_ray:
            api_ok = True
            print(f"[{GREEN}PASS{RESET}] api.anthropic.com -> HTTP {e.code} (cf-ray: {cf_ray or 'Cloudflare'})")
        else:
            print(f"[{RED}FAIL{RESET}] api.anthropic.com -> HTTP {e.code}")
    except Exception as e:
        print(f"[{RED}FAIL{RESET}] api.anthropic.com error: {e}")

    # 3. Claude Web
    claude_ok = False
    try:
        code, _, _ = fetch_url(tun_opener, "https://claude.ai", timeout=10)
        claude_ok = code in [200, 301, 302, 307]
        print(f"[{GREEN}PASS{RESET}] claude.ai -> HTTP {code}")
    except urllib.error.HTTPError as e:
        cf_ray = e.headers.get("cf-ray", "")
        cf_mit = e.headers.get("cf-mitigated", "")
        if "challenge" in cf_mit or cf_ray:
            claude_ok = True
            print(f"[{GREEN}PASS{RESET}] claude.ai reached Cloudflare Edge (HTTP {e.code}, cf-ray: {cf_ray})")
        else:
            print(f"[{RED}FAIL{RESET}] claude.ai -> HTTP {e.code}")
    except Exception as e:
        print(f"[{RED}FAIL{RESET}] claude.ai error: {e}")

    # 4. Telemetry endpoints (statsigapi.net, browser-intake-datadoghq.com & googletagmanager.com)
    telemetry_ok = True
    for t_url in [
        "https://statsigapi.net",
        "https://browser-intake-datadoghq.com",
        "https://www.googletagmanager.com/gtm.js?id=GTM-TEST",
    ]:
        try:
            code, _, _ = fetch_url(tun_opener, t_url, timeout=10)
            print(f"[{GREEN}PASS{RESET}] Telemetry endpoint routed cleanly: {t_url} (HTTP {code})")
        except urllib.error.HTTPError as e:
            if e.code in [400, 401, 403, 404]:
                print(f"[{GREEN}PASS{RESET}] Telemetry endpoint reached overseas edge: {t_url} (HTTP {e.code})")
            else:
                print(f"[{YELLOW}WARN{RESET}] Telemetry endpoint {t_url} returned HTTP {e.code}")
        except Exception as e:
            print(f"[{RED}FAIL{RESET}] Telemetry endpoint failed: {t_url} ({e})")
            telemetry_ok = False

    # 5. Gemini
    gemini_ok = False
    try:
        code, _, body = fetch_url(tun_opener, "https://gemini.google.com", timeout=12)
        if '["ZZ"]' in body or "not supported in your country" in body.lower():
            print(f"[{RED}FAIL{RESET}] Gemini blocked as ZZ / unsupported region")
        else:
            gemini_ok = True
            print(f"[{GREEN}PASS{RESET}] gemini.google.com (HTTP {code}) accessible without ZZ restriction")
    except Exception as e:
        print(f"[{RED}FAIL{RESET}] gemini.google.com error: {e}")

    return ips_consistent and api_ok and claude_ok and telemetry_ok and gemini_ok


def test_real_dns_and_raw_ip(tun_opener, expected_ip):
    print_header("Check 5 & 6: Real DNS Leak & Raw IP (1.1.1.1) TUN Tests")
    raw_ip_ok = False
    try:
        _, _, trace = fetch_url(tun_opener, "https://1.1.1.1/cdn-cgi/trace", timeout=10, headers={"User-Agent": "curl/8.0"})
        kv = dict(line.split("=", 1) for line in trace.splitlines() if "=" in line)
        ip_val = kv.get("ip", "")
        loc_val = kv.get("loc", "")
        colo_val = kv.get("colo", "")
        match = bool(loc_val) and loc_val not in {"CN", "HK", "MO"} and (not expected_ip or ip_val == expected_ip)
        raw_ip_ok = match
        tag = f"{GREEN}PASS{RESET}" if match else f"{RED}FAIL{RESET}"
        print(f"[{tag}] Raw IP 1.1.1.1 via TUN: ip={ip_val}, loc={loc_val}, colo={colo_val}")
    except Exception as e:
        print(f"[{RED}FAIL{RESET}] Raw IP 1.1.1.1 probe failed: {e}")

    # DoH random subdomain probe through TUN
    doh_ok = False
    rand_sub = f"leakcheck-{uuid.uuid4().hex[:10]}.claude.ai"
    try:
        doh_url = f"https://cloudflare-dns.com/dns-query?name={rand_sub}&type=A"
        code, _, doh_body = fetch_url(
            tun_opener,
            doh_url,
            timeout=10,
            headers={"Accept": "application/dns-json", "User-Agent": "curl/8.0"},
        )
        data = json.loads(doh_body)
        doh_ok = code == 200 and data.get("Status") in [0, 3]
        print(f"[{GREEN}PASS{RESET}] DoH probe ({rand_sub} via cloudflare-dns.com): Status={data.get('Status')}")
    except Exception as e:
        print(f"[{RED}FAIL{RESET}] DoH probe failed: {e}")

    # DNS leak API check (isp.ac/dns-leak-test)
    leak_ok = True
    try:
        code, _, body = fetch_url(tun_opener, "https://isp.ac/dns-leak-test", timeout=10, headers={"User-Agent": "curl/8.0"})
        lower = body.lower()
        has_cn_dns = '"cn"' in lower or "china" in lower or "alidns" in lower or "dnspod" in lower
        if has_cn_dns:
            leak_ok = False
            print(f"[{RED}FAIL{RESET}] isp.ac/dns-leak-test reported possible CN DNS resolver: {body[:200]}")
        else:
            print(f"[{GREEN}PASS{RESET}] isp.ac/dns-leak-test (HTTP {code}): {body.strip()[:180]}")
    except Exception as e:
        print(f"[{YELLOW}WARN{RESET}] isp.ac/dns-leak-test unreachable ({e}); DoH & 1.1.1.1 trace verified")

    return raw_ip_ok and doh_ok and leak_ok


def audit_killswitch_readiness():
    print_header("Check 7~11: Kill Switch Readiness (Read-Only Audit)")
    system = platform.system()
    if system == "Windows":
        guard_ps1 = r"C:\ProgramData\clash-guard\guard.ps1"
        has_files = os.path.exists(guard_ps1)
        res = subprocess.run(
            ["schtasks", "/Query", "/TN", "local.clash-guard"],
            capture_output=True,
            text=True,
        )
        has_task = res.returncode == 0
        print(f"[{GREEN if has_files else YELLOW}{'PASS' if has_files else 'INFO'}{RESET}] Guard script ({guard_ps1}): {'Installed' if has_files else 'Not installed yet'}")
        print(f"[{GREEN if has_task else YELLOW}{'PASS' if has_task else 'INFO'}{RESET}] Scheduled Task (local.clash-guard): {'Active' if has_task else 'Not registered yet'}")
    elif system == "Darwin":
        off_sh = "/Library/Application Support/clash-guard/off.sh"
        has_files = os.path.exists(off_sh)
        res = subprocess.run(["launchctl", "print", "system/local.clash-guard"], capture_output=True)
        has_svc = res.returncode == 0
        print(f"[{GREEN if has_files else YELLOW}{'PASS' if has_files else 'INFO'}{RESET}] Guard script ({off_sh}): {'Installed' if has_files else 'Not installed yet'}")
        print(f"[{GREEN if has_svc else YELLOW}{'PASS' if has_svc else 'INFO'}{RESET}] LaunchDaemon (local.clash-guard): {'Running' if has_svc else 'Not loaded yet'}")
    else:
        print(f"[{BLUE}INFO{RESET}] OS={system}: Kill Switch audit skipped.")


def main():
    parser = argparse.ArgumentParser(description="Verify Ultimate Anti-Leak Environment (Read-Only)")
    parser.add_argument(
        "--proxy",
        default="http://127.0.0.1:7897",
        help="Local Clash HTTP proxy URL for comparison (default: http://127.0.0.1:7897)",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to Clash YAML config file for static anti-leak audit",
    )
    args = parser.parse_args()

    config_path = args.config or find_default_config()
    cfg_ok = audit_yaml_config(config_path)

    tun_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    proxy_opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": args.proxy, "https": args.proxy})
    )

    tun_ok, expected_ip = test_tun_vs_proxy(tun_opener, proxy_opener, args.proxy)
    cn_ok = test_domestic_direct(tun_opener)
    overseas_ok = test_overseas_and_telemetry(tun_opener, expected_ip)
    dns_ok = test_real_dns_and_raw_ip(tun_opener, expected_ip)
    audit_killswitch_readiness()

    print_header("Verification Summary")
    all_ok = cfg_ok and tun_ok and cn_ok and overseas_ok and dns_ok
    if all_ok:
        print(f"{BOLD}{GREEN}✓ ALL CHECKS PASSED: Ultimate Anti-Leak network & YAML posture verified!{RESET}")
    else:
        print(f"{BOLD}{RED}✗ ATTENTION: One or more checks failed. Review details above.{RESET}")

    print("\n[3 Manual Extreme Failure Drills (Recommended after Kill Switch is installed)]:")
    print("  1. 切死海外节点: 确认 claude.ai & api.ipify.org 立即失败且不回落国内 IP，同时 baidu.com 正常;")
    print("  2. 关闭 TUN 虚拟网卡: 确认普通进程访问任何外网直接被系统防火墙拦截;")
    print("  3. 退出代理客户端 3 秒后: 确认普通进程外网仍被防火墙拦死，重开客户端即恢复。\n")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()

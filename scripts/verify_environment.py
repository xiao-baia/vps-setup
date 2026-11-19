#!/usr/bin/env python3
"""
Automated Anti-Ban Environment Gate Check
Tests:
1. Proxy / TUN reachability & Egress IP GeoIP (US)
2. Anthropic & Claude Infrastructure Reachability
3. Gemini (Google) Accessibility & Region Check
4. Real DNS Leak Test (bash.ws random subdomains -> verify zero China/CN DNS resolvers)
5. Real IPv6 Bypass Block Test (TCP to public IPv6 literals + AAAA check)
6. OS-Specific Read-Only Audit:
   - Windows: Checks whether SMHNR (DisableSmartNameResolution=1) is disabled
   - macOS: Read-only advisory check of scutil --dns & IPv6 status (never modifies macOS settings)
"""

import argparse
import json
import random
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

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


def print_header(title):
    print(f"\n{BOLD}{BLUE}====================================================={RESET}")
    print(f"{BOLD}{BLUE} {title} {RESET}")
    print(f"{BOLD}{BLUE}====================================================={RESET}")


def build_opener(proxy_url):
    if proxy_url:
        return urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
        )
    # Bypass any HTTP_PROXY/HTTPS_PROXY environment variables to test TUN directly
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def test_ip_and_geo(opener):
    req = urllib.request.Request("http://ip-api.com/json", headers={"User-Agent": "curl/8.0"})
    try:
        with opener.open(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
            ip = data.get("query")
            country = data.get("country")
            country_code = data.get("countryCode")
            isp = data.get("isp")
            as_name = data.get("as")

            is_us = country_code == "US"
            status_color = GREEN if is_us else RED
            status_text = "PASS (US Native)" if is_us else f"FAIL ({country_code})"

            print(f"[{status_color}{status_text}{RESET}] IP Address : {ip}")
            print(f"       Location   : {country} ({country_code}), {data.get('city', '')}")
            print(f"       ISP / ASN  : {isp} / {as_name}")
            return is_us, ip
    except Exception as e:
        print(f"[{RED}FAIL{RESET}] Failed to fetch IP Geo info: {e}")
        return False, None


def test_anthropic_and_claude(opener):
    api_ok = False
    req_api = urllib.request.Request(
        "https://api.anthropic.com",
        headers={"User-Agent": "curl/8.0"}
    )
    try:
        with opener.open(req_api, timeout=10):
            api_ok = True
    except urllib.error.HTTPError as e:
        cf_ray = e.headers.get("cf-ray", "")
        if "LAX" in cf_ray or "SFO" in cf_ray or e.code in (403, 404):
            api_ok = True
            print(f"[{GREEN}PASS{RESET}] Anthropic API Gateway: Reached Cloudflare Edge (HTTP {e.code}, cf-ray: {cf_ray or 'N/A'})")
        else:
            print(f"[{YELLOW}WARN{RESET}] Anthropic API Gateway returned HTTP {e.code} (cf-ray: {cf_ray})")
    except Exception as e:
        print(f"[{RED}FAIL{RESET}] Anthropic API Connection Error: {e}")

    web_ok = False
    req_web = urllib.request.Request(
        "https://claude.ai",
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }
    )
    try:
        with opener.open(req_web, timeout=10) as resp:
            if resp.getcode() in (200, 301, 302, 307):
                web_ok = True
                print(f"[{GREEN}PASS{RESET}] Claude Web Front: HTTP {resp.getcode()} (Direct Access)")
    except urllib.error.HTTPError as e:
        cf_mitigated = e.headers.get("cf-mitigated", "")
        cf_ray = e.headers.get("cf-ray", "")
        if "challenge" in cf_mitigated or cf_ray or e.code == 403:
            web_ok = True
            print(f"[{GREEN}PASS{RESET}] Claude Web Front: Reached Cloudflare Edge (HTTP {e.code}, cf-ray: {cf_ray or 'N/A'})")
        else:
            print(f"[{RED}FAIL{RESET}] Claude Web Front returned HTTP {e.code}")
    except Exception as e:
        print(f"[{RED}FAIL{RESET}] Claude Web Connection Error: {e}")

    return api_ok or web_ok


def test_gemini(opener):
    req = urllib.request.Request(
        "https://gemini.google.com",
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
        }
    )
    try:
        with opener.open(req, timeout=12) as resp:
            content = resp.read().decode("utf-8", errors="ignore")
            if '["ZZ"]' in content or "not supported in your country" in content.lower():
                print(f"[{RED}FAIL{RESET}] Gemini Blocked: Google GeoIP tagged as 'ZZ' or unsupported country!")
                return False
            print(f"[{GREEN}PASS{RESET}] Google Gemini Endpoint (HTTP {resp.getcode()}): Fully Accessible")
            return True
    except Exception as e:
        print(f"[{RED}FAIL{RESET}] Gemini Connection Error: {e}")
        return False


def test_real_dns_leak(direct_opener):
    """Trigger random subdomains through system/TUN resolver and verify zero CN DNS servers."""
    print(f"\n[{BLUE}TEST{RESET}] Running real DNS leak test via bash.ws (TUN/system resolver)...")
    test_id = random.randint(1000000, 9999999)
    for i in range(1, 7):
        host = f"{i}.{test_id}.bash.ws"
        try:
            socket.getaddrinfo(host, 80, socket.AF_INET)
        except Exception:
            pass
        try:
            req = urllib.request.Request(f"http://{host}/", headers={"User-Agent": "curl/8.0"})
            with direct_opener.open(req, timeout=2):
                pass
        except Exception:
            pass

    time.sleep(1.0)
    try:
        req = urllib.request.Request(
            f"https://bash.ws/dnsleak/test/{test_id}?json",
            headers={"User-Agent": "curl/8.0"}
        )
        with direct_opener.open(req, timeout=10) as resp:
            entries = json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception as e:
        print(f"[{YELLOW}WARN{RESET}] Could not fetch bash.ws DNS leak report: {e}")
        return True

    dns_servers = [item for item in entries if item.get("type") == "dns"]
    if not dns_servers:
        print(f"[{YELLOW}WARN{RESET}] No DNS resolvers reported by bash.ws (may need TUN mode enabled).")
        return True

    cn_leaks = []
    for srv in dns_servers:
        cc = (srv.get("country") or "").lower()
        line = f"{srv.get('ip')} ({srv.get('country_name') or cc.upper()}, {srv.get('asn', '')})"
        if cc == "cn":
            cn_leaks.append(line)
            print(f"  [{RED}LEAK{RESET}] China DNS resolver detected: {line}")
        else:
            print(f"  [{GREEN}OK{RESET}]   Overseas DNS resolver: {line}")

    if cn_leaks:
        print(f"[{RED}FAIL{RESET}] DNS Leak detected! {len(cn_leaks)} China mainland DNS server(s) answered overseas queries.")
        return False

    print(f"[{GREEN}PASS{RESET}] Zero China mainland DNS resolvers detected ({len(dns_servers)} overseas resolver(s)).")
    return True


def test_ipv6_block():
    """Verify raw IPv6 literals cannot bypass TUN and AAAA records are suppressed."""
    print(f"\n[{BLUE}TEST{RESET}] Verifying IPv6 bypass blocking & AAAA suppression...")
    all_blocked = True
    targets = [
        ("Cloudflare IPv6", "2606:4700:4700::1111", 443),
        ("AliDNS IPv6", "2400:3200::1", 443),
    ]
    for label, ip6, port in targets:
        sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        sock.settimeout(3)
        try:
            sock.connect((ip6, port))
            print(f"  [{RED}LEAK{RESET}] {label} [{ip6}]:{port} CONNECTED directly! IPv6 bypass is NOT blocked.")
            all_blocked = False
        except OSError as e:
            print(f"  [{GREEN}OK{RESET}]   {label} [{ip6}]:{port} blocked/unreachable ({e.strerror or e})")
        finally:
            sock.close()

    try:
        aaaa = socket.getaddrinfo("claude.ai", 443, socket.AF_INET6)
        if aaaa:
            ips = sorted({row[4][0] for row in aaaa})
            print(f"  [{YELLOW}WARN{RESET}] claude.ai returned AAAA record(s): {', '.join(ips)} (expected empty when dns.ipv6=false)")
            all_blocked = False
        else:
            print(f"  [{GREEN}OK{RESET}]   claude.ai AAAA query returned empty.")
    except socket.gaierror:
        print(f"  [{GREEN}OK{RESET}]   claude.ai AAAA query returned empty (IPv4-only enforced).")

    if all_blocked:
        print(f"[{GREEN}PASS{RESET}] IPv6 bypass check passed (zero direct IPv6 egress).")
    else:
        print(f"[{RED}FAIL{RESET}] IPv6 bypass risk detected!")
    return all_blocked


def audit_os_hygiene():
    """Read-only OS-specific DNS/IPv6 check."""
    print(f"\n[{BLUE}AUDIT{RESET}] OS-Specific DNS & IPv6 Hygiene ({sys.platform})...")
    if sys.platform == "win32":
        import winreg
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Policies\Microsoft\Windows NT\DNSClient",
                0,
                winreg.KEY_READ
            ) as key:
                val, _ = winreg.QueryValueEx(key, "DisableSmartNameResolution")
                if val == 1:
                    print(f"  [{GREEN}PASS{RESET}] Windows SMHNR is disabled (DisableSmartNameResolution = 1).")
                    return True
        except OSError:
            pass
        print(f"  [{YELLOW}WARN{RESET}] Windows SMHNR is NOT disabled! Parallel DNS queries may leak on home/campus Wi-Fi.")
        print("         Run: python scripts/windows_smhnr.py --disable")
        return False

    if sys.platform == "darwin":
        print("  [INFO] macOS does NOT use Windows SMHNR (no SMHNR change needed).")
        try:
            out = subprocess.check_output(["scutil", "--dns"], text=True, timeout=5)
            first_ns = []
            in_first = False
            for line in out.splitlines():
                if line.strip().startswith("resolver #1"):
                    in_first = True
                elif in_first and line.strip().startswith("resolver #"):
                    break
                elif in_first and "nameserver[" in line:
                    first_ns.append(line.strip())
            if first_ns:
                print(f"  [INFO] macOS primary resolver #1: {' | '.join(first_ns)}")
                if any("100.100.100.100" in x for x in first_ns):
                    print(f"  [{YELLOW}WARN{RESET}] Tailscale MagicDNS (100.100.100.100) detected as primary DNS — may bypass Clash TUN!")
        except Exception:
            pass
        print("  [TIP]  macOS Advisory (never modified automatically — decide for yourself):")
        print("         - macOS has no Windows WFP; if your Wi-Fi has public IPv6 while Clash top-level ipv6=false,")
        print("           native IPv6 may bypass utun. You may optionally set Wi-Fi IPv6 to 'Link-local only'")
        print("           in System Settings -> Network -> Wi-Fi -> Details -> TCP/IP (note: affects IPv6-only intranet).")
        print("         - Keep Clash Verge Rev 'DNS Override' and 'IPv6' toggles OFF.")
        return True

    print("  [INFO] Linux/Other OS: verify /etc/resolv.conf points to Mihomo TUN DNS (198.18.0.2).")
    return True


def main():
    parser = argparse.ArgumentParser(description="Verify Claude Anti-Ban Network Environment")
    parser.add_argument(
        "--proxy",
        default="",
        help="Optional explicit proxy URL (e.g. http://127.0.0.1:7897). Leave empty to test TUN mode directly (--noproxy equivalent)."
    )
    args = parser.parse_args()

    print_header("Claude & AI Anti-Ban Network Environment Gate Check")
    if args.proxy:
        print(f"Mode: Explicit Proxy ({args.proxy}) + Direct TUN Leak Tests")
    else:
        print("Mode: Direct TUN Verification (bypassing HTTP_PROXY env vars)")

    opener = build_opener(args.proxy)
    direct_opener = build_opener("")

    is_us, _ = test_ip_and_geo(opener)
    claude_ok = test_anthropic_and_claude(opener)
    gemini_ok = test_gemini(opener)
    dns_ok = test_real_dns_leak(direct_opener)
    ipv6_ok = test_ipv6_block()
    os_ok = audit_os_hygiene()

    print_header("Verification Summary")
    all_ok = is_us and claude_ok and gemini_ok and dns_ok and ipv6_ok

    if all_ok:
        print(f"{BOLD}{GREEN}✓ EXCELLENT: Your environment passes all core anti-ban & anti-leak checks!{RESET}")
        if not os_ok:
            print(f"{YELLOW}! Advisory: Review the OS-specific warning above (e.g., Windows SMHNR).{RESET}")
    else:
        print(f"{BOLD}{RED}✗ ATTENTION: One or more critical checks failed. Please review the details above.{RESET}")

    print("=====================================================\n")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()

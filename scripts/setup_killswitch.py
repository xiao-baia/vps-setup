#!/usr/bin/env python3
"""
Local Client Hardening, Backup/Restore, Emergency Guide & Cross-Platform Kill Switch (clash-guard).
Aligns with the Ultimate Anti-Leak Specification:
  - Read-only environment & proxy client audit (--action audit)
  - Full client config backup + offline restore script + 断网急救.txt (--action backup)
  - Harden Clash Verge global UI toggles (TUN on, UI DNS/profile DNS overrides & IPv6 off; Auto-Launch left under user control) (--action harden-client)
  - System firewall Kill Switch (Windows Firewall + Task 'local.clash-guard' / macOS pf 'com.apple/clash-guard' + launchd 'local.clash-guard')

SAFETY GUARANTEES:
  - This script NEVER reads, writes, overwrites, or deletes any Clash Verge subscription files
    (`profiles/` directory or `profiles.yaml`).
  - `--action harden-client` only toggles UI flags (`enable_tun_mode`, `enable_dns_settings`,
    `profile_dns_settings.*.enabled` in `verge.yaml` and `ipv6` in `clash-verge.yaml`) and never touches any subscription.
"""

import argparse
import ctypes
import datetime
import json
import os
import platform
import re
import shutil
import subprocess
import sys

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

WINDOWS_GUARD_DIR = r"C:\ProgramData\clash-guard"
MACOS_GUARD_DIR = "/Library/Application Support/clash-guard"
MACOS_PLIST_PATH = "/Library/LaunchDaemons/local.clash-guard.plist"
GUARD_LABEL = "local.clash-guard"

LOOPBACK_CIDRS = "127.0.0.0/8,::1/128"
LAN_CIDRS = (
    "10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,"
    "100.64.0.0/10,169.254.0.0/16,224.0.0.0/4,255.255.255.255/32"
)
LAN_NON_DNS_PORTS = "1-52,54-852,854-65535"
# All IPv4 ranges outside Loopback, RFC1918 LAN, CGNAT (100.64/10), Link-Local, Multicast
# plus all non-loopback IPv6 addresses
WAN_BLOCK_RANGES = (
    "0.0.0.0-9.255.255.255,"
    "11.0.0.0-100.63.255.255,"
    "100.128.0.0-126.255.255.255,"
    "128.0.0.0-169.253.255.255,"
    "169.255.0.0-172.15.255.255,"
    "172.32.0.0-192.167.255.255,"
    "192.169.0.0-223.255.255.255,"
    "::2-ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff"
)
IPV6_NON_LOOPBACK_RANGE = "::2-ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff"


def is_admin():
    if sys.platform == "win32":
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False
    return hasattr(os, "geteuid") and os.geteuid() == 0


def run_cmd(cmd, timeout=15):
    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            shell=isinstance(cmd, str),
        )
        return res.returncode, res.stdout.strip(), res.stderr.strip()
    except Exception as e:
        return -1, "", str(e)


def run_ps(script_text, timeout=20):
    return run_cmd(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script_text],
        timeout=timeout,
    )


def detect_client_dirs():
    system = platform.system()
    candidates = []
    if system == "Windows":
        appdata = os.environ.get("APPDATA", "")
        names = [
            ("Clash Verge Rev", "io.github.clash-verge-rev.clash-verge-rev"),
            ("Clash Verge", "clash-verge"),
            ("Mihomo Party", "mihomo-party"),
            ("FlClash", "FlClash"),
            ("Clash for Windows", "clash_win"),
        ]
        for label, folder in names:
            p = os.path.join(appdata, folder)
            if os.path.isdir(p):
                candidates.append({"name": label, "path": p})
    elif system == "Darwin":
        support = os.path.expanduser("~/Library/Application Support")
        names = [
            ("Clash Verge Rev", "io.github.clash-verge-rev.clash-verge-rev"),
            ("Clash Verge", "clash-verge"),
            ("Mihomo Party", "mihomo-party"),
            ("FlClash", "FlClash"),
        ]
        for label, folder in names:
            p = os.path.join(support, folder)
            if os.path.isdir(p):
                candidates.append({"name": label, "path": p})
    return candidates


def read_simple_yaml_flags(yaml_path, keys):
    found = {}
    if not os.path.exists(yaml_path):
        return found
    try:
        with open(yaml_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                for k in keys:
                    m = re.match(rf"^{re.escape(k)}\s*:\s*(.+?)\s*$", stripped)
                    if m:
                        found[k] = m.group(1).strip().strip("'\"")
    except Exception:
        pass
    return found


def check_profile_dns_overrides(verge_yaml_path):
    enabled_profiles = []
    if not os.path.exists(verge_yaml_path):
        return enabled_profiles
    try:
        with open(verge_yaml_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        in_block = False
        current_id = None
        for line in lines:
            if re.match(r"^profile_dns_settings\s*:", line):
                in_block = True
                continue
            if in_block:
                if line and not line[0].isspace():
                    break
                m_id = re.match(r"^\s{2}([A-Za-z0-9_-]+)\s*:\s*$", line)
                if m_id:
                    current_id = m_id.group(1)
                    continue
                m_en = re.match(r"^\s{4}enabled\s*:\s*(true|false)\s*$", line, re.I)
                if m_en and current_id and m_en.group(1).lower() == "true":
                    enabled_profiles.append(current_id)
    except Exception:
        pass
    return enabled_profiles


def detect_tun_active():
    system = platform.system()
    if system == "Windows":
        rc, out, _ = run_ps(
            "Get-NetAdapter -ErrorAction SilentlyContinue | Where-Object { $_.Status -eq 'Up' -and ($_.Name -match 'Mihomo|Clash|utun|Meta' -or $_.InterfaceDescription -match 'Meta Tunnel|Wintun') } | Select-Object -ExpandProperty Name"
        )
        if rc == 0 and out.strip():
            return True, [line.strip() for line in out.splitlines() if line.strip()]
        rc2, out2, _ = run_cmd(["netsh", "interface", "ip", "show", "addresses"])
        if rc2 == 0 and "198.18.0." in out2:
            return True, ["198.18.0.x"]
        return False, []
    elif system == "Darwin":
        rc, out, _ = run_cmd(["ifconfig"])
        if rc == 0:
            ifaces = []
            cur = None
            for line in out.splitlines():
                m = re.match(r"^(utun\d+):", line)
                if m:
                    cur = m.group(1)
                elif cur and "198.18." in line:
                    ifaces.append(cur)
            if ifaces:
                return True, ifaces
        return False, []
    return False, []


def detect_clash_verge_paths():
    system = platform.system()
    exe_path = None
    core_paths = []
    if system == "Windows":
        rc, out, _ = run_ps(
            "Get-Process -Name 'clash-verge' -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty Path"
        )
        if rc == 0 and out.strip() and os.path.exists(out.strip()):
            exe_path = out.strip()
        if not exe_path:
            search_dirs = [
                r"C:\Program Files\Clash Verge",
                r"C:\Program Files (x86)\Clash Verge",
                os.path.expandvars(r"%LOCALAPPDATA%\Programs\Clash Verge"),
                os.path.expandvars(r"%LOCALAPPDATA%\Clash Verge"),
            ]
            for d in search_dirs:
                cand = os.path.join(d, "clash-verge.exe")
                if os.path.exists(cand):
                    exe_path = cand
                    break
        if not exe_path:
            try:
                import winreg

                uninstall_roots = [
                    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
                    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
                    (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
                ]
                for root_hive, sub_path in uninstall_roots:
                    try:
                        with winreg.OpenKey(root_hive, sub_path) as key:
                            for idx in range(winreg.QueryInfoKey(key)[0]):
                                sub_name = winreg.EnumKey(key, idx)
                                with winreg.OpenKey(key, sub_name) as sk:
                                    disp = ""
                                    try:
                                        disp = str(winreg.QueryValueEx(sk, "DisplayName")[0])
                                    except OSError:
                                        pass
                                    if "clash verge" not in disp.lower() and "clash verge" not in sub_name.lower():
                                        continue
                                    for val_name in ("InstallLocation", "DisplayIcon"):
                                        try:
                                            val = str(winreg.QueryValueEx(sk, val_name)[0]).split(",")[0].strip().strip('"')
                                            cand_dir = val if os.path.isdir(val) else os.path.dirname(val)
                                            cand_exe = os.path.join(cand_dir, "clash-verge.exe")
                                            if os.path.exists(cand_exe):
                                                exe_path = cand_exe
                                                break
                                        except OSError:
                                            continue
                                    if exe_path:
                                        break
                    except OSError:
                        continue
                    if exe_path:
                        break
            except Exception:
                pass
        if exe_path:
            install_dir = os.path.dirname(exe_path)
            # Allow only core tunnel/service binaries, never the frontend GUI shell (clash-verge.exe)
            for cname in ["verge-mihomo.exe", "verge-mihomo-alpha.exe", "clash-verge-service.exe"]:
                cp = os.path.join(install_dir, cname)
                if os.path.exists(cp):
                    core_paths.append(cp)
    elif system == "Darwin":
        for p in ["/Applications/Clash Verge.app", os.path.expanduser("~/Applications/Clash Verge.app")]:
            if os.path.exists(p):
                exe_path = p
                break
    return exe_path, core_paths


def detect_conflicts():
    system = platform.system()
    running_proxies = []
    tailscale_dns = False
    claude_autostart = []

    if system == "Windows":
        rc, out, _ = run_ps(
            "Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -match 'clash|verge|mihomo|sing-box|v2ray|nekoray|tailscale' } | Select-Object -ExpandProperty ProcessName -Unique"
        )
        if rc == 0 and out:
            running_proxies = [x.strip() for x in out.splitlines() if x.strip()]
        rc_dns, out_dns, _ = run_ps(
            "Get-DnsClientServerAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty ServerAddresses"
        )
        if rc_dns == 0 and "100.100.100.100" in out_dns:
            tailscale_dns = True
        rc_run, out_run, _ = run_ps(
            "(Get-ItemProperty 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run' -ErrorAction SilentlyContinue).PSObject.Properties | Where-Object { $_.Value -match 'Claude' } | ForEach-Object { $_.Name }"
        )
        if rc_run == 0 and out_run.strip():
            claude_autostart = [x.strip() for x in out_run.splitlines() if x.strip()]
    elif system == "Darwin":
        rc, out, _ = run_cmd(["ps", "-axo", "comm="])
        if rc == 0:
            for line in out.splitlines():
                name = os.path.basename(line.strip())
                if any(k in name.lower() for k in ["clash", "mihomo", "surge", "sing-box", "v2ray", "tailscale"]):
                    if name not in running_proxies:
                        running_proxies.append(name)
        rc_dns, out_dns, _ = run_cmd(["scutil", "--dns"])
        if rc_dns == 0 and "100.100.100.100" in out_dns:
            tailscale_dns = True
        launch_agents = os.path.expanduser("~/Library/LaunchAgents")
        if os.path.isdir(launch_agents):
            for fn in os.listdir(launch_agents):
                if "claude" in fn.lower():
                    claude_autostart.append(fn)

    return running_proxies, tailscale_dns, claude_autostart


def check_killswitch_status():
    system = platform.system()
    if system == "Windows":
        files_ok = os.path.exists(os.path.join(WINDOWS_GUARD_DIR, "guard.ps1"))
        rc_task, out_task, _ = run_cmd(["schtasks", "/Query", "/TN", GUARD_LABEL])
        task_ok = rc_task == 0
        rc_fw, out_fw, _ = run_ps(
            "Get-NetFirewallRule -DisplayName 'ClashGuard-*' -ErrorAction SilentlyContinue | Select-Object DisplayName, Enabled, Action | ConvertTo-Json -Compress"
        )
        fw_rules = out_fw.strip() if rc_fw == 0 and out_fw.strip() else "None"
        return files_ok, task_ok, fw_rules
    elif system == "Darwin":
        files_ok = os.path.exists(os.path.join(MACOS_GUARD_DIR, "off.sh"))
        rc_svc, _, _ = run_cmd(["launchctl", "print", f"system/{GUARD_LABEL}"])
        svc_ok = rc_svc == 0
        rc_pf, out_pf, _ = run_cmd(["pfctl", "-a", "com.apple/clash-guard", "-sr"])
        pf_info = out_pf.strip() if rc_pf == 0 and out_pf.strip() else "None / requires sudo to inspect"
        return files_ok, svc_ok, pf_info
    return False, False, "Unsupported OS"


def action_audit():
    system = platform.system()
    print(f"\n{BOLD}{BLUE}====================================================={RESET}")
    print(f"{BOLD}{BLUE} Clash-Guard 只读环境体检 ({system}) {RESET}")
    print(f"{BOLD}{BLUE}====================================================={RESET}")

    clients = detect_client_dirs()
    if not clients:
        print(f"[{YELLOW}WARN{RESET}] 未检测到常见 Clash Verge / Mihomo 客户端配置目录")
    for c in clients:
        print(f"[{GREEN}FOUND{RESET}] 客户端配置目录 ({c['name']}): {c['path']}")
        verge_yaml = os.path.join(c["path"], "verge.yaml")
        if os.path.exists(verge_yaml):
            flags = read_simple_yaml_flags(
                verge_yaml,
                [
                    "enable_tun_mode",
                    "enable_auto_launch",
                    "enable_dns_settings",
                    "enable_system_proxy",
                    "enable_external_controller",
                ],
            )
            tun_flag = flags.get("enable_tun_mode", "unknown")
            auto_flag = flags.get("enable_auto_launch", "unknown")
            dns_flag = flags.get("enable_dns_settings", "unknown")
            prof_dns = check_profile_dns_overrides(verge_yaml)

            tun_c = GREEN if tun_flag == "true" else RED
            dns_c = GREEN if dns_flag == "false" and not prof_dns else RED
            print(f"  - enable_tun_mode (虚拟网卡): {tun_c}{tun_flag}{RESET}")
            print(f"  - enable_auto_launch (开机自启，由用户自由控制): {BLUE}{auto_flag}{RESET}")
            print(f"  - enable_dns_settings (DNS 覆写，应关闭): {dns_c}{dns_flag}{RESET}")
            if prof_dns:
                print(f"  - {RED}profile_dns_settings 存在开启项{RESET}: {', '.join(prof_dns)}")

        cv_yaml = os.path.join(c["path"], "clash-verge.yaml")
        ipv6_val = "unknown"
        if os.path.exists(cv_yaml):
            cv_flags = read_simple_yaml_flags(cv_yaml, ["ipv6", "mode", "respect-rules"])
            ipv6_val = cv_flags.get("ipv6", "unknown")
            ipv6_c = GREEN if ipv6_val == "false" else RED
            print(f"  - clash-verge.yaml 运行态: mode={cv_flags.get('mode', '?')}, ipv6={ipv6_c}{ipv6_val}{RESET}, respect-rules={cv_flags.get('respect-rules', '?')}")

        if os.path.exists(verge_yaml) and (dns_flag == "true" or prof_dns or ipv6_val == "true"):
            print(f"  [{YELLOW}WARN{RESET}] 检测到 Clash Verge UI 存在 DNS 覆写或 IPv6 开启项，可能覆盖 YAML 防漏配置！可在客户端设置关闭，或运行: python \"{os.path.abspath(__file__)}\" --action harden-client --skip-backup")

    tun_up, tun_ifaces = detect_tun_active()
    if tun_up:
        print(f"[{GREEN}PASS{RESET}] TUN 虚拟网卡运行中: {', '.join(tun_ifaces)}")
    else:
        print(f"[{BLUE}INFO{RESET}] TUN 虚拟网卡当前未启动（若已安装断网开关，目前处于开机放行待命态；点开 TUN 后自动设防）")

    exe_path, core_paths = detect_clash_verge_paths()
    print(f"[{BLUE}INFO{RESET}] Clash Verge 可执行路径: {exe_path or '未自动探测到'}")
    if core_paths:
        print(f"[{BLUE}INFO{RESET}] 探测到核心组件: {', '.join(core_paths)}")

    proxies, ts_dns, claude_auto = detect_conflicts()
    if proxies:
        print(f"[{BLUE}INFO{RESET}] 运行中的代理/网络相关进程: {', '.join(proxies)}")
    if ts_dns:
        print(f"[{RED}WARN{RESET}] 检测到 Tailscale DNS (100.100.100.100) 接管系统 DNS，可能绕过代理！")
    else:
        print(f"[{GREEN}PASS{RESET}] 未检测到 Tailscale DNS (100.100.100.100) 冲突")
    if claude_auto:
        print(f"[{YELLOW}WARN{RESET}] 检测到 Claude 桌面端自启项 ({', '.join(claude_auto)})，建议关闭防止先于 TUN 抢跑直连")
    else:
        print(f"[{GREEN}PASS{RESET}] 未检测到 Claude 桌面端自启项")

    ks_files, ks_svc, ks_fw = check_killswitch_status()
    ks_status = f"{GREEN}已安装{RESET}" if (ks_files and ks_svc) else f"{YELLOW}未安装{RESET}"
    print(f"[{BLUE}INFO{RESET}] 系统级断网开关 (clash-guard): {ks_status}")
    print(f"       脚本目录就绪: {ks_files} | 系统守护服务 ({GUARD_LABEL}): {ks_svc}")
    if ks_fw != "None":
        print(f"       防火墙规则状态: {ks_fw[:240]}")
    print("=====================================================\n")


def copy_config_tree(src, dst):
    skip_dirs = {"Cache", "Code Cache", "DawnCache", "GPUCache", "EBWebView", "logs", "blob_storage", "Session Storage", "Local Storage", "Network"}
    skip_files = {"cache.db", "singleton-instance.lock"}
    os.makedirs(dst, exist_ok=True)
    copied = 0
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        rel = os.path.relpath(root, src)
        target_root = dst if rel == "." else os.path.join(dst, rel)
        os.makedirs(target_root, exist_ok=True)
        for fn in files:
            if fn in skip_files:
                continue
            sp = os.path.join(root, fn)
            dp = os.path.join(target_root, fn)
            try:
                shutil.copy2(sp, dp)
                copied += 1
            except Exception:
                pass
    return copied


def write_rescue_guide(system, backup_root, ts, restore_script=None):
    os.makedirs(backup_root, exist_ok=True)
    desktop_dir = os.path.join(os.path.expanduser("~"), "Desktop")
    os.makedirs(desktop_dir, exist_ok=True)
    rescue_path = os.path.join(desktop_dir, "断网急救.txt")
    self_script = os.path.abspath(__file__)

    if system == "Windows":
        restore_line = (
            f'   【一键完整还原到配置前的原始状态】：\n   powershell -NoProfile -ExecutionPolicy Bypass -File "{restore_script}"\n'
            if restore_script
            else ""
        )
        rescue_text = f"""================ Clash-Guard Windows 断网急救指南 ================
生成时间: {ts}
备份目录: {backup_root}

① 先尝试重新打开代理客户端（Clash Verge），选择对应订阅并启动 TUN 按钮，等待 1 分钟看虚拟网卡是否恢复。

② 如果需要临时解除断网防火墙（或用裸网排障），请用「管理员身份」打开 PowerShell 或终端，运行：

   【仅临时解除断网防火墙恢复直连上网】：
   powershell -NoProfile -ExecutionPolicy Bypass -File "{WINDOWS_GUARD_DIR}\\off.ps1"

   【修好代理且开启 TUN 后，重新开启断网防火墙】：
   python "{self_script}" --action install-killswitch --skip-backup

{restore_line}③ 如果上面文件还不存在，手工兜底急救命令（管理员 PowerShell）：
   schtasks /Delete /TN "{GUARD_LABEL}" /F
   Get-NetFirewallRule -DisplayName "ClashGuard-*" | Remove-NetFirewallRule
   Set-NetFirewallProfile -Profile Domain,Private,Public -DefaultOutboundAction Allow
   Set-ItemProperty -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings" -Name ProxyEnable -Value 0

④ 网络恢复后，回到对话说明「网断过，先查现状再继续」。
======================================================================
"""
    else:
        restore_line = (
            f'   【一键完整还原】：\n   sudo sh "{restore_script}"\n'
            if restore_script
            else ""
        )
        rescue_text = f"""================ Clash-Guard macOS 断网急救指南 ================
生成时间: {ts}
备份目录: {backup_root}

① 先打开 Clash Verge 等代理客户端，选择对应订阅并开启 TUN 模式，等待 1 分钟。

② 若需临时解除断网开关（或裸网排障），在「终端」里跑：
   【仅临时解除断网开关】：
   sudo sh "{MACOS_GUARD_DIR}/off.sh"

   【修好代理且开启 TUN 后，重新开启断网开关】：
   python3 "{self_script}" --action install-killswitch --skip-backup

{restore_line}③ 若上面文件不存在时的兜底命令：
   sudo launchctl bootout system/{GUARD_LABEL}
   sudo pfctl -a com.apple/clash-guard -F all
   networksetup -setwebproxystate "Wi-Fi" off
   networksetup -setsecurewebproxystate "Wi-Fi" off
   networksetup -setsocksfirewallproxystate "Wi-Fi" off

④ 网通后回到对话说「网断过，先查现状再继续」。
====================================================================
"""

    with open(rescue_path, "w", encoding="utf-8") as f:
        f.write(rescue_text)
    with open(os.path.join(backup_root, "断网急救.txt"), "w", encoding="utf-8") as f:
        f.write(rescue_text)
    return rescue_path


def action_backup():
    system = platform.system()
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_root = os.path.join(os.path.expanduser("~"), "clash-guard-backup", ts)
    os.makedirs(backup_root, exist_ok=True)

    clients = detect_client_dirs()
    copied_total = 0
    manifest = {"timestamp": ts, "os": system, "clients": []}

    for c in clients:
        folder_name = os.path.basename(c["path"])
        dest = os.path.join(backup_root, "client-config", folder_name)
        cnt = copy_config_tree(c["path"], dest)
        copied_total += cnt
        manifest["clients"].append({"name": c["name"], "src": c["path"], "backup": dest, "files": cnt})

    exe_path, _ = detect_clash_verge_paths()
    manifest["clash_verge_exe"] = exe_path

    with open(os.path.join(backup_root, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    restore_script = None
    if system == "Windows":
        restore_ps1 = os.path.join(backup_root, "restore.ps1")
        restore_bat = os.path.join(backup_root, "restore.bat")
        restore_entries = []
        for item in manifest["clients"]:
            b = item["backup"].replace("'", "''")
            s = item["src"].replace("'", "''")
            restore_entries.append(f"if (Test-Path '{b}') {{ Copy-Item -Path '{b}\\*' -Destination '{s}' -Recurse -Force -ErrorAction SilentlyContinue }}")
        restore_copy_block = "\n".join(restore_entries)
        launch_line = f"Start-Process '{exe_path}'" if exe_path else "# 请手动打开 Clash Verge"

        ps1_content = f"""# Clash-Guard 一键完整还原脚本 (Windows)
$ErrorActionPreference = 'SilentlyContinue'
Write-Host '[1/5] 停止断网开关任务与防护进程...'
Unregister-ScheduledTask -TaskName '{GUARD_LABEL}' -Confirm:$false -ErrorAction SilentlyContinue
Get-CimInstance Win32_Process -Filter "CommandLine LIKE '%clash-guard%guard.ps1%'" | ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force }}
Write-Host '[2/5] 清除 ClashGuard 防火墙规则并恢复默认出站放行及原放行规则...'
Get-NetFirewallRule -DisplayName 'ClashGuard-*' -ErrorAction SilentlyContinue | Remove-NetFirewallRule
$stateFile = '{WINDOWS_GUARD_DIR}\\state.json'
if (Test-Path $stateFile) {{
  $st = Get-Content $stateFile -Raw | ConvertFrom-Json
  foreach ($p in @('Domain','Private','Public')) {{
    $act = $st.$p
    if ($act -and $act -ne 'NotConfigured') {{ Set-NetFirewallProfile -Profile $p -DefaultOutboundAction $act }}
    else {{ Set-NetFirewallProfile -Profile $p -DefaultOutboundAction Allow }}
  }}
  if ($st.DisabledAllowRules) {{
    foreach ($rn in $st.DisabledAllowRules) {{
      if ($rn) {{ Enable-NetFirewallRule -Name $rn -ErrorAction SilentlyContinue }}
    }}
  }}
  Remove-Item $stateFile -Force -ErrorAction SilentlyContinue
}} else {{
  Set-NetFirewallProfile -Profile Domain,Private,Public -DefaultOutboundAction Allow
}}
Write-Host '[3/5] 关掉残留 Windows 系统代理...'
Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings' -Name ProxyEnable -Value 0
Write-Host '[4/5] 退出 Clash Verge 并还原备份配置...'
Get-Process -Name 'clash-verge','verge-mihomo','verge-mihomo-alpha' -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2
{restore_copy_block}
Write-Host '[5/5] 重启 Clash Verge...'
{launch_line}
Start-Sleep -Seconds 5
Write-Host '还原完成！如端口未通请等待 10 秒再试。'
"""
        with open(restore_ps1, "w", encoding="utf-8-sig") as f:
            f.write(ps1_content)
        with open(restore_bat, "w", encoding="utf-8") as f:
            f.write(f'@echo off\r\npowershell -NoProfile -ExecutionPolicy Bypass -File "{restore_ps1}"\r\npause\r\n')
        restore_script = restore_ps1

    elif system == "Darwin":
        restore_sh = os.path.join(backup_root, "restore.sh")
        copy_cmds = []
        for item in manifest["clients"]:
            copy_cmds.append(f'mkdir -p "{item["src"]}" && cp -Rf "{item["backup"]}/." "{item["src"]}/" || true')
        copy_block = "\n".join(copy_cmds)
        sh_content = f"""#!/bin/sh
echo "[1/5] 解除断网开关..."
launchctl bootout system/{GUARD_LABEL} 2>/dev/null || true
pfctl -a com.apple/clash-guard -F all 2>/dev/null || true

echo "[2/5] 关掉系统代理..."
for svc in $(networksetup -listallnetworkservices | tail -n +2 | sed 's/^\\*//'); do
  networksetup -setwebproxystate "$svc" off 2>/dev/null || true
  networksetup -setsecurewebproxystate "$svc" off 2>/dev/null || true
  networksetup -setsocksfirewallproxystate "$svc" off 2>/dev/null || true
done

echo "[3/5] 退出 Clash Verge 并还原配置..."
pkill -f "Clash Verge" 2>/dev/null || true
pkill -f "verge-mihomo" 2>/dev/null || true
sleep 2
{copy_block}

echo "[4/5] 重开 Clash Verge..."
open -a "Clash Verge" 2>/dev/null || true
sleep 4
echo "[5/5] 检查代理端口 7897..."
nc -z 127.0.0.1 7897 && echo "代理端口已通" || echo "端口暂未就绪，请等待客户端加载完成"
"""
        with open(restore_sh, "w", encoding="utf-8", newline="\n") as f:
            f.write(sh_content)
        os.chmod(restore_sh, 0o755)
        restore_script = restore_sh

    rescue_path = write_rescue_guide(system, backup_root, ts, restore_script=restore_script)
    print(f"[{GREEN}BACKUP OK{RESET}] 已备份 {copied_total} 个配置文件至: {backup_root}")
    print(f"[{GREEN}RESCUE OK{RESET}] 已生成桌面断网急救指南: {rescue_path}")
    return backup_root


def update_yaml_key(filepath, updates, disable_profile_dns=False):
    """Update only UI toggle keys in verge.yaml / clash-verge.yaml without touching any subscription files."""
    if not os.path.exists(filepath):
        return False
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    new_lines = []
    seen = set()
    in_profile_dns = False
    for line in lines:
        if disable_profile_dns and re.match(r"^profile_dns_settings\s*:", line):
            in_profile_dns = True
            new_lines.append(line)
            continue
        if in_profile_dns:
            if line and not line[0].isspace():
                in_profile_dns = False
            else:
                m_en = re.match(r"^(\s{4}enabled\s*:\s*)(true|false)(\s*)$", line, re.I)
                if m_en:
                    new_lines.append(f"{m_en.group(1)}false{m_en.group(3)}")
                    continue
                new_lines.append(line)
                continue

        replaced = False
        for k, v in updates.items():
            if re.match(rf"^{re.escape(k)}\s*:", line):
                new_lines.append(f"{k}: {v}\n")
                seen.add(k)
                replaced = True
                break
        if not replaced:
            new_lines.append(line)

    for k, v in updates.items():
        if k not in seen:
            new_lines.append(f"{k}: {v}\n")

    with open(filepath, "w", encoding="utf-8", newline="\n") as f:
        f.writelines(new_lines)
    return True


def action_harden_client(skip_backup=False):
    print(f"\n{BOLD}{BLUE}正在加固本机 Clash Verge 客户端 UI 开关（TUN/DNS覆写/IPv6，绝不修改任何订阅文件）...{RESET}")
    if not skip_backup:
        action_backup()
    clients = detect_client_dirs()
    verge_client = next((c for c in clients if "Clash Verge" in c["name"]), None)
    if not verge_client:
        print(f"[{RED}FAIL{RESET}] 未找到 Clash Verge 配置目录，跳过修改。")
        sys.exit(1)

    system = platform.system()
    exe_path, _ = detect_clash_verge_paths()
    was_running = False

    if system == "Windows":
        rc, out, _ = run_ps("Get-Process -Name 'clash-verge' -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty Id")
        was_running = rc == 0 and bool(out.strip())
        if was_running:
            print("[INFO] 先退出运行中的 Clash Verge，防止内存配置回写覆盖磁盘...")
            run_ps("Get-Process -Name 'clash-verge','verge-mihomo','verge-mihomo-alpha' -ErrorAction SilentlyContinue | Stop-Process -Force; Start-Sleep -Seconds 2")
    elif system == "Darwin":
        rc, _, _ = run_cmd(["pgrep", "-f", "Clash Verge"])
        was_running = rc == 0
        if was_running:
            print("[INFO] 先退出运行中的 Clash Verge，防止内存配置回写覆盖磁盘...")
            run_cmd(["pkill", "-f", "Clash Verge"])
            run_cmd(["pkill", "-f", "verge-mihomo"])
            run_cmd(["sleep", "2"])

    verge_yaml = os.path.join(verge_client["path"], "verge.yaml")
    update_yaml_key(
        verge_yaml,
        {
            "enable_tun_mode": "true",
            "enable_dns_settings": "false",
        },
        disable_profile_dns=True,
    )
    print(f"[{GREEN}OK{RESET}] 已更新 {verge_yaml} (TUN=true, 全局及单配置 DNS覆写=false; 开机自启保持用户原有设置)")

    cv_yaml = os.path.join(verge_client["path"], "clash-verge.yaml")
    if os.path.exists(cv_yaml):
        update_yaml_key(cv_yaml, {"ipv6": "false"})
        print(f"[{GREEN}OK{RESET}] 已更新 {cv_yaml} (ipv6=false)")

    if was_running and exe_path:
        print(f"[INFO] 正在重新拉起 Clash Verge: {exe_path}")
        if system == "Windows":
            subprocess.Popen([exe_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif system == "Darwin":
            subprocess.Popen(["open", exe_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif was_running:
        print(f"[{YELLOW}WARN{RESET}] 请手动重新打开 Clash Verge 客户端。")


def build_windows_killswitch_scripts(bundle_dir, core_paths):
    os.makedirs(bundle_dir, exist_ok=True)
    core_json = json.dumps(core_paths, ensure_ascii=False)
    guard_ps1 = os.path.join(bundle_dir, "guard.ps1")
    install_ps1 = os.path.join(bundle_dir, "install.ps1")
    off_ps1 = os.path.join(bundle_dir, "off.ps1")
    off_bat = os.path.join(bundle_dir, "off.bat")

    guard_code = f"""# Clash-Guard Windows Watchdog (Disarmed on Boot -> Auto-Arm on TUN -> Lock on Drop -> Reset on Reboot)
param([switch]$InitOnly)
$ErrorActionPreference = 'SilentlyContinue'
$GuardDir = '{WINDOWS_GUARD_DIR}'
$StatePath = Join-Path $GuardDir 'state.json'
$CorePaths = '{core_json}' | ConvertFrom-Json
$LoopbackCidrs = '{LOOPBACK_CIDRS}'.Split(',')
$LanCidrs = '{LAN_CIDRS}'.Split(',')
$LanNonDnsPorts = '{LAN_NON_DNS_PORTS}'.Split(',')
$WanRanges = '{WAN_BLOCK_RANGES}'.Split(',')
$Ipv6BlockRange = '{IPV6_NON_LOOPBACK_RANGE}'

function Test-TunHealthy {{
  $nic = Get-NetAdapter -Name 'Mihomo' -ErrorAction SilentlyContinue
  $proc = Get-Process -Name 'verge-mihomo','verge-mihomo-alpha' -ErrorAction SilentlyContinue
  return [bool]($nic -and $nic.Status -eq 'Up' -and $proc)
}}

function Snapshot-FirewallState {{
  $existingAllow = @(Get-NetFirewallRule -Direction Outbound -Action Allow -Enabled True -ErrorAction SilentlyContinue |
    Where-Object {{ $_.DisplayName -notlike 'ClashGuard-*' }} |
    Select-Object -ExpandProperty Name)
  if (-not (Test-Path $StatePath)) {{
    $state = @{{
      Domain  = (Get-NetFirewallProfile -Profile Domain).DefaultOutboundAction.ToString()
      Private = (Get-NetFirewallProfile -Profile Private).DefaultOutboundAction.ToString()
      Public  = (Get-NetFirewallProfile -Profile Public).DefaultOutboundAction.ToString()
      DisabledAllowRules = $existingAllow
    }}
    $state | ConvertTo-Json -Depth 4 | Set-Content -Path $StatePath -Encoding UTF8
  }} elseif ($existingAllow.Count -gt 0) {{
    $st = Get-Content $StatePath -Raw | ConvertFrom-Json
    $merged = New-Object System.Collections.Generic.HashSet[string]
    if ($st.DisabledAllowRules) {{
      foreach ($r in $st.DisabledAllowRules) {{ if ($r) {{ [void]$merged.Add($r) }} }}
    }}
    foreach ($r in $existingAllow) {{ if ($r) {{ [void]$merged.Add($r) }} }}
    $st | Add-Member -NotePropertyName DisabledAllowRules -NotePropertyValue @($merged) -Force
    $st | ConvertTo-Json -Depth 4 | Set-Content -Path $StatePath -Encoding UTF8
  }}
}}

function Disable-NonGuardOutboundAllowRules {{
  $extraAllow = @(Get-NetFirewallRule -Direction Outbound -Action Allow -Enabled True -ErrorAction SilentlyContinue |
    Where-Object {{ $_.DisplayName -notlike 'ClashGuard-*' }} |
    Select-Object -ExpandProperty Name)
  if ($extraAllow.Count -gt 0) {{
    Snapshot-FirewallState
    foreach ($r in $extraAllow) {{
      Disable-NetFirewallRule -Name $r -ErrorAction SilentlyContinue
    }}
  }}
}}

function Get-ActiveCorePaths {{
  $set = New-Object System.Collections.Generic.HashSet[string] ([StringComparer]::OrdinalIgnoreCase)
  foreach ($p in $CorePaths) {{
    if ($p -and (Test-Path $p)) {{ [void]$set.Add($p) }}
  }}
  $procs = Get-CimInstance Win32_Process -Filter "Name='verge-mihomo.exe' OR Name='verge-mihomo-alpha.exe' OR Name='clash-verge-service.exe' OR Name='clash-verge.exe'" -ErrorAction SilentlyContinue
  foreach ($pr in $procs) {{
    if ($pr.ExecutablePath -and (Test-Path $pr.ExecutablePath)) {{
      $dir = Split-Path -Parent $pr.ExecutablePath
      foreach ($cname in @('verge-mihomo.exe','verge-mihomo-alpha.exe','clash-verge-service.exe')) {{
        $cand = Join-Path $dir $cname
        if (Test-Path $cand) {{ [void]$set.Add($cand) }}
      }}
    }}
  }}
  return @($set)
}}

function Ensure-GuardBaseRules {{
  foreach ($prof in @('Domain','Private','Public')) {{
    $cur = (Get-NetFirewallProfile -Profile $prof).DefaultOutboundAction
    if ($cur -ne 'Block') {{
      Set-NetFirewallProfile -Profile $prof -DefaultOutboundAction Block
    }}
  }}
  if (-not (Get-NetFirewallRule -DisplayName 'ClashGuard-Block-IPv6' -ErrorAction SilentlyContinue)) {{
    New-NetFirewallRule -DisplayName 'ClashGuard-Block-IPv6' -Direction Outbound -Action Block -RemoteAddress $Ipv6BlockRange -Profile Any | Out-Null
  }}
  if (-not (Get-NetFirewallRule -DisplayName 'ClashGuard-Allow-Loopback' -ErrorAction SilentlyContinue)) {{
    New-NetFirewallRule -DisplayName 'ClashGuard-Allow-Loopback' -Direction Outbound -Action Allow -RemoteAddress $LoopbackCidrs -Profile Any | Out-Null
  }}
  if (-not (Get-NetFirewallRule -DisplayName 'ClashGuard-Allow-LAN-TCP' -ErrorAction SilentlyContinue)) {{
    New-NetFirewallRule -DisplayName 'ClashGuard-Allow-LAN-TCP' -Direction Outbound -Action Allow -Protocol TCP -RemoteAddress $LanCidrs -RemotePort $LanNonDnsPorts -Profile Any | Out-Null
  }}
  if (-not (Get-NetFirewallRule -DisplayName 'ClashGuard-Allow-LAN-UDP' -ErrorAction SilentlyContinue)) {{
    New-NetFirewallRule -DisplayName 'ClashGuard-Allow-LAN-UDP' -Direction Outbound -Action Allow -Protocol UDP -RemoteAddress $LanCidrs -RemotePort $LanNonDnsPorts -Profile Any | Out-Null
  }}
  if (-not (Get-NetFirewallRule -DisplayName 'ClashGuard-Allow-LAN-ICMP' -ErrorAction SilentlyContinue)) {{
    New-NetFirewallRule -DisplayName 'ClashGuard-Allow-LAN-ICMP' -Direction Outbound -Action Allow -Protocol ICMPv4 -RemoteAddress $LanCidrs -Profile Any | Out-Null
  }}
  if (-not (Get-NetFirewallRule -DisplayName 'ClashGuard-Allow-DHCP' -ErrorAction SilentlyContinue)) {{
    New-NetFirewallRule -DisplayName 'ClashGuard-Allow-DHCP' -Direction Outbound -Action Allow -Protocol UDP -RemotePort 67,68 -Profile Any | Out-Null
  }}
  if (-not (Get-NetFirewallRule -DisplayName 'ClashGuard-Allow-TUN-Subnet' -ErrorAction SilentlyContinue)) {{
    New-NetFirewallRule -DisplayName 'ClashGuard-Allow-TUN-Subnet' -Direction Outbound -Action Allow -LocalAddress '198.18.0.0/16' -Profile Any | Out-Null
  }}
  $mihomoNic = Get-NetAdapter -Name 'Mihomo' -ErrorAction SilentlyContinue
  if ($mihomoNic -and -not (Get-NetFirewallRule -DisplayName 'ClashGuard-Allow-Mihomo-TUN' -ErrorAction SilentlyContinue)) {{
    New-NetFirewallRule -DisplayName 'ClashGuard-Allow-Mihomo-TUN' -Direction Outbound -Action Allow -InterfaceAlias 'Mihomo' -Profile Any | Out-Null
  }}
  $activeCores = Get-ActiveCorePaths
  for ($idx = 0; $idx -lt $activeCores.Count; $idx++) {{
    $cp = $activeCores[$idx]
    $rname = "ClashGuard-Allow-Core-$idx"
    $existingRule = Get-NetFirewallRule -DisplayName $rname -ErrorAction SilentlyContinue
    if (-not $existingRule) {{
      New-NetFirewallRule -DisplayName $rname -Direction Outbound -Action Allow -Program $cp -Profile Any | Out-Null
    }} else {{
      $af = $existingRule | Get-NetFirewallApplicationFilter -ErrorAction SilentlyContinue
      if ($af.Program -ne $cp) {{
        Remove-NetFirewallRule -DisplayName $rname -ErrorAction SilentlyContinue
        New-NetFirewallRule -DisplayName $rname -Direction Outbound -Action Allow -Program $cp -Profile Any | Out-Null
      }}
    }}
  }}
  Disable-NonGuardOutboundAllowRules
}}

function Set-ExplicitKillSwitchBlock([bool]$Enable) {{
  $blockWan = Get-NetFirewallRule -DisplayName 'ClashGuard-KillSwitch-Block-WAN' -ErrorAction SilentlyContinue
  $blockDnsTcp = Get-NetFirewallRule -DisplayName 'ClashGuard-KillSwitch-Block-DNS-TCP' -ErrorAction SilentlyContinue
  $blockDnsUdp = Get-NetFirewallRule -DisplayName 'ClashGuard-KillSwitch-Block-DNS-UDP' -ErrorAction SilentlyContinue
  if ($Enable) {{
    if (-not $blockWan) {{
      New-NetFirewallRule -DisplayName 'ClashGuard-KillSwitch-Block-WAN' -Direction Outbound -Action Block -RemoteAddress $WanRanges -Profile Any | Out-Null
    }} elseif ($blockWan.Enabled -ne 'True') {{
      Enable-NetFirewallRule -DisplayName 'ClashGuard-KillSwitch-Block-WAN' | Out-Null
    }}
    if (-not $blockDnsTcp) {{
      New-NetFirewallRule -DisplayName 'ClashGuard-KillSwitch-Block-DNS-TCP' -Direction Outbound -Action Block -Protocol TCP -RemotePort 53,853 -RemoteAddress $LanCidrs -Profile Any | Out-Null
    }} elseif ($blockDnsTcp.Enabled -ne 'True') {{
      Enable-NetFirewallRule -DisplayName 'ClashGuard-KillSwitch-Block-DNS-TCP' | Out-Null
    }}
    if (-not $blockDnsUdp) {{
      New-NetFirewallRule -DisplayName 'ClashGuard-KillSwitch-Block-DNS-UDP' -Direction Outbound -Action Block -Protocol UDP -RemotePort 53,853 -RemoteAddress $LanCidrs -Profile Any | Out-Null
    }} elseif ($blockDnsUdp.Enabled -ne 'True') {{
      Enable-NetFirewallRule -DisplayName 'ClashGuard-KillSwitch-Block-DNS-UDP' | Out-Null
    }}
  }} else {{
    if ($blockWan -and $blockWan.Enabled -eq 'True') {{ Disable-NetFirewallRule -DisplayName 'ClashGuard-KillSwitch-Block-WAN' | Out-Null }}
    if ($blockDnsTcp -and $blockDnsTcp.Enabled -eq 'True') {{ Disable-NetFirewallRule -DisplayName 'ClashGuard-KillSwitch-Block-DNS-TCP' | Out-Null }}
    if ($blockDnsUdp -and $blockDnsUdp.Enabled -eq 'True') {{ Disable-NetFirewallRule -DisplayName 'ClashGuard-KillSwitch-Block-DNS-UDP' | Out-Null }}
  }}
}}

function Reset-FirewallToNormal {{
  Get-NetFirewallRule -DisplayName 'ClashGuard-*' -ErrorAction SilentlyContinue | Remove-NetFirewallRule
  if (Test-Path $StatePath) {{
    $st = Get-Content $StatePath -Raw | ConvertFrom-Json
    foreach ($p in @('Domain','Private','Public')) {{
      $act = $st.$p
      if ($act -and $act -ne 'NotConfigured') {{ Set-NetFirewallProfile -Profile $p -DefaultOutboundAction $act }}
      else {{ Set-NetFirewallProfile -Profile $p -DefaultOutboundAction Allow }}
    }}
    if ($st.DisabledAllowRules) {{
      foreach ($rn in $st.DisabledAllowRules) {{
        if ($rn) {{ Enable-NetFirewallRule -Name $rn -ErrorAction SilentlyContinue }}
      }}
    }}
    Remove-Item $StatePath -Force -ErrorAction SilentlyContinue
  }} else {{
    foreach ($prof in @('Domain','Private','Public')) {{
      if ((Get-NetFirewallProfile -Profile $prof).DefaultOutboundAction -eq 'Block') {{
        Set-NetFirewallProfile -Profile $prof -DefaultOutboundAction Allow
      }}
    }}
  }}
}}

# Startup / Reboot initialization: reset to normal unless TUN is already active
if (Test-TunHealthy) {{
  Snapshot-FirewallState
  Ensure-GuardBaseRules
  Set-ExplicitKillSwitchBlock $false
  $Armed = $true
  $lastHealthy = $true
}} else {{
  Reset-FirewallToNormal
  $Armed = $false
  $lastHealthy = $false
}}

if ($InitOnly) {{
  exit 0
}}

$tick = 0
while ($true) {{
  Start-Sleep -Seconds 1
  $tick++
  $healthy = Test-TunHealthy
  if (-not $Armed) {{
    if ($healthy) {{
      Snapshot-FirewallState
      Ensure-GuardBaseRules
      Set-ExplicitKillSwitchBlock $false
      $Armed = $true
      $lastHealthy = $true
      $tick = 0
    }}
  }} else {{
    $stateChanged = ($healthy -ne $lastHealthy)
    if ($stateChanged -or ($tick -ge 30)) {{
      Ensure-GuardBaseRules
      $tick = 0
    }}
    if ($stateChanged) {{
      Set-ExplicitKillSwitchBlock (-not $healthy)
      $lastHealthy = $healthy
    }}
  }}
}}
"""

    install_code = f"""# Clash-Guard Windows Installer (Requires Administrator)
$ErrorActionPreference = 'Stop'
$GuardDir = '{WINDOWS_GUARD_DIR}'
New-Item -ItemType Directory -Path $GuardDir -Force | Out-Null

# Stop any previous daemon before updating files
Unregister-ScheduledTask -TaskName '{GUARD_LABEL}' -Confirm:$false -ErrorAction SilentlyContinue
Get-CimInstance Win32_Process -Filter "CommandLine LIKE '%clash-guard%guard.ps1%'" -ErrorAction SilentlyContinue | ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }}

Copy-Item -Path (Join-Path $PSScriptRoot '*') -Destination $GuardDir -Force

# Synchronously initialize current state (Arms immediately if TUN is Up, or Disarmed standby if TUN is Down)
& (Join-Path $GuardDir 'guard.ps1') -InitOnly

# Register Scheduled Task local.clash-guard (Boot + Logon watchdog; resets firewall on reboot)
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$GuardDir\\guard.ps1`""
$t1 = New-ScheduledTaskTrigger -AtStartup
$t2 = New-ScheduledTaskTrigger -AtLogOn
$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Days 3650) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName '{GUARD_LABEL}' -Action $action -Trigger @($t1,$t2) -Principal $principal -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName '{GUARD_LABEL}'
Write-Host '[SUCCESS] Windows Auto-Arm Kill Switch (local.clash-guard) installed & running!'
"""

    off_code = f"""# Clash-Guard Windows Emergency Off Script
$ErrorActionPreference = 'SilentlyContinue'
Unregister-ScheduledTask -TaskName '{GUARD_LABEL}' -Confirm:$false -ErrorAction SilentlyContinue
Get-CimInstance Win32_Process -Filter "CommandLine LIKE '%clash-guard%guard.ps1%'" | ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force }}
Get-NetFirewallRule -DisplayName 'ClashGuard-*' -ErrorAction SilentlyContinue | Remove-NetFirewallRule
$stateFile = '{WINDOWS_GUARD_DIR}\\state.json'
if (Test-Path $stateFile) {{
  $st = Get-Content $stateFile -Raw | ConvertFrom-Json
  foreach ($p in @('Domain','Private','Public')) {{
    $act = $st.$p
    if ($act -and $act -ne 'NotConfigured') {{ Set-NetFirewallProfile -Profile $p -DefaultOutboundAction $act }}
    else {{ Set-NetFirewallProfile -Profile $p -DefaultOutboundAction Allow }}
  }}
  if ($st.DisabledAllowRules) {{
    foreach ($rn in $st.DisabledAllowRules) {{
      if ($rn) {{ Enable-NetFirewallRule -Name $rn -ErrorAction SilentlyContinue }}
    }}
  }}
  Remove-Item $stateFile -Force -ErrorAction SilentlyContinue
}} else {{
  Set-NetFirewallProfile -Profile Domain,Private,Public -DefaultOutboundAction Allow
}}
Write-Host '[SUCCESS] Clash-Guard Kill Switch disabled and original firewall rules restored.'
"""

    with open(guard_ps1, "w", encoding="utf-8-sig") as f:
        f.write(guard_code)
    with open(install_ps1, "w", encoding="utf-8-sig") as f:
        f.write(install_code)
    with open(off_ps1, "w", encoding="utf-8-sig") as f:
        f.write(off_code)
    with open(off_bat, "w", encoding="utf-8") as f:
        f.write(f'@echo off\r\npowershell -NoProfile -ExecutionPolicy Bypass -File "{WINDOWS_GUARD_DIR}\\off.ps1"\r\n')

    return install_ps1, off_ps1


def build_macos_killswitch_scripts(bundle_dir):
    os.makedirs(bundle_dir, exist_ok=True)
    pf_rules = os.path.join(bundle_dir, "pf.conf")
    guard_sh = os.path.join(bundle_dir, "guard.sh")
    off_sh = os.path.join(bundle_dir, "off.sh")
    install_sh = os.path.join(bundle_dir, "install.sh")
    plist_file = os.path.join(bundle_dir, f"{GUARD_LABEL}.plist")

    pf_content = """# com.apple/clash-guard anchor rules
# 1. Allow loopback
pass quick on lo0 all
# 2. Drop all non-loopback IPv6 immediately
block drop quick inet6 all
# 3. Allow proxy core (running as root) and TUN interfaces (including DNS hijacked into utun)
pass out quick user root all keep state
pass out quick on utun all keep state
# 4. Block any non-root/non-utun outbound DNS/DoT (e.g. direct to LAN router port 53/853)
block drop out quick inet proto { tcp udp } from any to any port { 53, 853 }
# 5. Allow non-DNS LAN / CGNAT traffic
pass quick inet proto { tcp udp } to { 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 100.64.0.0/10, 169.254.0.0/16, 224.0.0.0/4 } keep state
# 6. Drop all other outbound WAN traffic bypassing TUN
block drop out quick all
"""
    guard_content = f"""#!/bin/sh
# Three-state machine using volatile /tmp/clash-guard.armed (cleared automatically on macOS reboot):
#   - Boot / Disarmed (no 198.18. & no armed flag): keep pf anchor cleared so normal internet works
#   - Armed (198.18. up): touch armed flag & enforce pf anchor
#   - Locked (no 198.18. & armed flag exists): keep pf anchor enforced until TUN returns or reboot
if ifconfig | grep -q "198.18."; then
  touch /tmp/clash-guard.armed
  pfctl -e 2>/dev/null || true
  if ! pfctl -a com.apple/clash-guard -sr 2>/dev/null | grep -q "block drop out"; then
    pfctl -a com.apple/clash-guard -f "{MACOS_GUARD_DIR}/pf.conf"
  fi
else
  if [ -f /tmp/clash-guard.armed ]; then
    pfctl -e 2>/dev/null || true
    if ! pfctl -a com.apple/clash-guard -sr 2>/dev/null | grep -q "block drop out"; then
      pfctl -a com.apple/clash-guard -f "{MACOS_GUARD_DIR}/pf.conf"
    fi
  else
    pfctl -a com.apple/clash-guard -F all 2>/dev/null || true
  fi
fi
"""
    off_content = f"""#!/bin/sh
rm -f /tmp/clash-guard.armed
launchctl bootout system/{GUARD_LABEL} 2>/dev/null || true
pfctl -a com.apple/clash-guard -F all 2>/dev/null || true
echo "[SUCCESS] clash-guard disabled."
"""
    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>{GUARD_LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/sh</string>
    <string>{MACOS_GUARD_DIR}/guard.sh</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>StartInterval</key>
  <integer>2</integer>
  <key>StandardOutPath</key>
  <string>/var/log/clash-guard.log</string>
  <key>StandardErrorPath</key>
  <string>/var/log/clash-guard.err</string>
</dict>
</plist>
"""
    install_content = f"""#!/bin/sh
set -e
pfctl -n -f "{os.path.join(bundle_dir, 'pf.conf')}"
mkdir -p "{MACOS_GUARD_DIR}"
cp "{os.path.join(bundle_dir, 'pf.conf')}" "{MACOS_GUARD_DIR}/pf.conf"
cp "{os.path.join(bundle_dir, 'guard.sh')}" "{MACOS_GUARD_DIR}/guard.sh"
cp "{os.path.join(bundle_dir, 'off.sh')}" "{MACOS_GUARD_DIR}/off.sh"
chmod +x "{MACOS_GUARD_DIR}/guard.sh" "{MACOS_GUARD_DIR}/off.sh"
cp "{os.path.join(bundle_dir, f'{GUARD_LABEL}.plist')}" "{MACOS_PLIST_PATH}"
chown root:wheel "{MACOS_PLIST_PATH}"
chmod 644 "{MACOS_PLIST_PATH}"
rm -f /tmp/clash-guard.armed
sh "{MACOS_GUARD_DIR}/guard.sh"
launchctl bootout system/{GUARD_LABEL} 2>/dev/null || true
launchctl bootstrap system "{MACOS_PLIST_PATH}"
echo "[SUCCESS] macOS Auto-Arm Kill Switch (com.apple/clash-guard + {GUARD_LABEL}) installed!"
"""

    for path, txt, mode in [
        (pf_rules, pf_content, 0o644),
        (guard_sh, guard_content, 0o755),
        (off_sh, off_content, 0o755),
        (plist_file, plist_content, 0o644),
        (install_sh, install_content, 0o755),
    ]:
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(txt)
        os.chmod(path, mode)

    return install_sh, off_sh, pf_rules


def action_install_killswitch(skip_backup=False):
    system = platform.system()
    tun_up, _ = detect_tun_active()
    if tun_up:
        print(f"[{GREEN}INFO{RESET}] 检测到 TUN 虚拟网卡已开启，安装后将立即激活断网防火墙保护。")
    else:
        print(f"[{BLUE}INFO{RESET}] 当前未开启 TUN 虚拟网卡：将安装「按需激活」断网防火墙待命（开机/当前正常直连上网，待您打开 TUN 后自动设防，异常掉线保持锁死，重启归零）。")

    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    if skip_backup:
        backup_root = os.path.join(os.path.expanduser("~"), "clash-guard-backup", ts)
        rescue_path = write_rescue_guide(system, backup_root, ts, restore_script=None)
        print(f"[{GREEN}RESCUE OK{RESET}] 已生成桌面断网急救指南（跳过客户端订阅读取）: {rescue_path}")
    else:
        backup_root = action_backup()

    bundle_dir = os.path.join(backup_root, "killswitch-bundle")

    if system == "Windows":
        _, core_paths = detect_clash_verge_paths()
        if not core_paths:
            print(f"[{YELLOW}WARN{RESET}] 未自动探测到 verge-mihomo.exe 路径，请确保 core_paths 已包含客户端程序。")
        install_ps1, off_ps1 = build_windows_killswitch_scripts(bundle_dir, core_paths)
        print(f"[{GREEN}GENERATED{RESET}] 已生成 Windows 断网开关安装脚本包: {bundle_dir}")
        if is_admin():
            rc, out, err = run_ps(f"& '{install_ps1}'")
            if rc == 0:
                print(out)
                print(f"[{GREEN}OK{RESET}] 解除命令: powershell -NoProfile -ExecutionPolicy Bypass -File \"{WINDOWS_GUARD_DIR}\\off.ps1\"")
            else:
                print(f"[{RED}FAIL{RESET}] 安装失败: {err or out}")
                sys.exit(1)
        else:
            print(f"[{BLUE}ELEVATE{RESET}] 当前非管理员权限，正在拉起系统 UAC 提权安装 Windows 断网防火墙...")
            safe_install = install_ps1.replace("'", "''")
            uac_cmd = (
                "Start-Process -FilePath 'powershell.exe' -Verb RunAs "
                f"-ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File','{safe_install}') -Wait"
            )
            run_ps(uac_cmd, timeout=120)
            files_ok, task_ok, _ = check_killswitch_status()
            if files_ok and task_ok:
                print(f"[{GREEN}SUCCESS{RESET}] Windows 按需断网防火墙 (local.clash-guard) 已提权安装并运行！（开机默认放行，开启 TUN 自动设防，掉线保持锁死，重启归零）")
                print(f"[{GREEN}OK{RESET}] 解除命令: powershell -NoProfile -ExecutionPolicy Bypass -File \"{WINDOWS_GUARD_DIR}\\off.ps1\"")
            else:
                print(f"[{YELLOW}ACTION REQUIRED{RESET}] 自动提权未完成（可能已取消 UAC 弹窗）。请以管理员身份在 PowerShell 中运行：")
                print(f'  powershell -NoProfile -ExecutionPolicy Bypass -File "{install_ps1}"')
                print(f"解除断网开关命令：")
                print(f'  powershell -NoProfile -ExecutionPolicy Bypass -File "{WINDOWS_GUARD_DIR}\\off.ps1"')
                sys.exit(1)

    elif system == "Darwin":
        install_sh, _, pf_rules = build_macos_killswitch_scripts(bundle_dir)
        rc_chk, _, err_chk = run_cmd(["pfctl", "-n", "-f", pf_rules])
        if rc_chk != 0:
            print(f"[{RED}FAIL{RESET}] pfctl 语法预检未通过: {err_chk}")
            sys.exit(1)
        print(f"[{GREEN}PASS{RESET}] pfctl -n 语法预检通过，脚本包已生成: {bundle_dir}")
        if is_admin():
            rc, out, err = run_cmd(["sh", install_sh])
            if rc == 0:
                print(out)
            else:
                print(f"[{RED}FAIL{RESET}] 安装失败: {err or out}")
                sys.exit(1)
        else:
            print(f"[{YELLOW}ACTION REQUIRED{RESET}] 需要 sudo 权限，请在「终端」运行：")
            print(f'  sudo sh "{install_sh}"')
            print(f"解除断网开关命令：")
            print(f'  sudo sh "{MACOS_GUARD_DIR}/off.sh"')
    else:
        print(f"[{RED}FAIL{RESET}] 不支持的本地系统: {system}")
        sys.exit(1)


def action_remove_killswitch():
    system = platform.system()
    if system == "Windows":
        off_ps1 = os.path.join(WINDOWS_GUARD_DIR, "off.ps1")
        if is_admin():
            if os.path.exists(off_ps1):
                rc, out, err = run_ps(f"& '{off_ps1}'")
            else:
                rc, out, err = run_ps(
                    f"Unregister-ScheduledTask -TaskName '{GUARD_LABEL}' -Confirm:$false -ErrorAction SilentlyContinue; "
                    "Get-NetFirewallRule -DisplayName 'ClashGuard-*' -ErrorAction SilentlyContinue | Remove-NetFirewallRule; "
                    "Set-NetFirewallProfile -Profile Domain,Private,Public -DefaultOutboundAction Allow"
                )
            if rc == 0:
                print(f"[{GREEN}OK{RESET}] 已解除 Windows 断网开关并恢复默认出站放行。")
            else:
                print(f"[{RED}FAIL{RESET}] 解除失败: {err or out}")
                sys.exit(1)
        else:
            print(f"[{YELLOW}ACTION REQUIRED{RESET}] 请以管理员身份在 PowerShell 中运行：")
            if os.path.exists(off_ps1):
                print(f'  powershell -NoProfile -ExecutionPolicy Bypass -File "{off_ps1}"')
            else:
                print(f'  schtasks /Delete /TN "{GUARD_LABEL}" /F; Get-NetFirewallRule -DisplayName "ClashGuard-*" | Remove-NetFirewallRule; Set-NetFirewallProfile -Profile Domain,Private,Public -DefaultOutboundAction Allow')
    elif system == "Darwin":
        off_sh = os.path.join(MACOS_GUARD_DIR, "off.sh")
        if is_admin():
            run_cmd(["launchctl", "bootout", f"system/{GUARD_LABEL}"])
            run_cmd(["pfctl", "-a", "com.apple/clash-guard", "-F", "all"])
            print(f"[{GREEN}OK{RESET}] 已解除 macOS 断网开关。")
        else:
            print(f"[{YELLOW}ACTION REQUIRED{RESET}] 请在终端运行：")
            if os.path.exists(off_sh):
                print(f'  sudo sh "{off_sh}"')
            else:
                print(f"  sudo launchctl bootout system/{GUARD_LABEL} && sudo pfctl -a com.apple/clash-guard -F all")


def main():
    parser = argparse.ArgumentParser(
        description="Local Clash-Guard Hardening, Backup, and Cross-Platform Kill Switch"
    )
    parser.add_argument(
        "--action",
        type=lambda s: s.lower(),
        choices=["audit", "backup", "harden-client", "install-killswitch", "remove-killswitch"],
        default="audit",
        help="Action to perform (default: audit)",
    )
    parser.add_argument(
        "--skip-backup",
        action="store_true",
        help="Skip creating a fresh backup before install-killswitch",
    )
    args = parser.parse_args()

    if args.action == "audit":
        action_audit()
    elif args.action == "backup":
        action_backup()
    elif args.action == "harden-client":
        action_harden_client(skip_backup=args.skip_backup)
    elif args.action == "install-killswitch":
        action_install_killswitch(skip_backup=args.skip_backup)
    elif args.action == "remove-killswitch":
        action_remove_killswitch()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Manage Windows SMHNR (Smart Multi-Homed Name Resolution) to prevent Windows
from blasting parallel DNS queries out of physical adapters (Wi-Fi/Ethernet)
while Clash Verge / Mihomo TUN is active.

On non-Windows platforms (e.g., macOS/Linux), this script is a safe no-op.
"""

import argparse
import os
import subprocess
import sys
import time

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

REG_SUBKEY = r"SOFTWARE\Policies\Microsoft\Windows NT\DNSClient"
REG_PATH_CLI = r"HKLM\SOFTWARE\Policies\Microsoft\Windows NT\DNSClient"
REG_VALUE = "DisableSmartNameResolution"

RESTORE_BAT_TEMPLATE = """@echo off
chcp 65001 >nul
setlocal

net session >nul 2>&1
if %errorlevel% neq 0 (
    echo 正在请求管理员权限以复原 Windows SMHNR 设置...
    set "SELF=%~f0"
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath $env:SELF -Verb RunAs"
    exit /b
)

echo ==================================================
echo   复原 Windows SMHNR (智能多宿主名称解析)
echo ==================================================
echo.

set "REG_KEY=HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows NT\\DNSClient"
set "REG_VAL=DisableSmartNameResolution"

reg query "%REG_KEY%" /v "%REG_VAL%" >nul 2>&1
if %errorlevel% neq 0 (
    echo [提示] 未检测到 DisableSmartNameResolution 策略项，系统已处于 Windows 默认 SMHNR 状态。
) else (
    reg delete "%REG_KEY%" /v "%REG_VAL%" /f
    if %errorlevel% equ 0 (
        echo [成功] 已删除 DisableSmartNameResolution，Windows SMHNR 已复原为默认开启状态。
    ) else (
        echo [错误] 删除注册表项失败，请确认已授予管理员权限。
        echo.
        pause
        exit /b 1
    )
)

echo.
echo 正在刷新系统 DNS 缓存...
ipconfig /flushdns

echo.
pause
"""


def is_windows():
    return sys.platform == "win32"


def is_admin():
    if not is_windows():
        return False
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def get_smhnr_disabled():
    """Return True if DisableSmartNameResolution == 1, False otherwise."""
    if not is_windows():
        return None
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, REG_SUBKEY, 0, winreg.KEY_READ) as key:
            val, reg_type = winreg.QueryValueEx(key, REG_VALUE)
            return val == 1
    except FileNotFoundError:
        return False
    except OSError:
        return False


def write_restore_bat(target_path):
    """Write a UTF-8 (no BOM) + CRLF restore .bat script."""
    abs_path = os.path.abspath(target_path)
    os.makedirs(os.path.dirname(abs_path) or ".", exist_ok=True)
    content = RESTORE_BAT_TEMPLATE.replace("\r\n", "\n").replace("\n", "\r\n")
    with open(abs_path, "wb") as f:
        f.write(content.encode("utf-8"))
    return abs_path


def _run_elevated_cmd(cmd_args):
    """Launch an elevated cmd.exe via PowerShell Start-Process -Verb RunAs -Wait."""
    ps_cmd = (
        f'Start-Process -FilePath "cmd.exe" '
        f'-ArgumentList "/c {cmd_args}" '
        f'-Verb RunAs -Wait'
    )
    subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
        check=False
    )


def disable_smhnr(restore_bat_path=None):
    if not is_windows():
        print("[INFO] Non-Windows OS detected; SMHNR only applies to Windows. Skipping.")
        return True

    if get_smhnr_disabled():
        print("[OK] Windows SMHNR is already disabled (DisableSmartNameResolution = 1).")
        if restore_bat_path:
            saved = write_restore_bat(restore_bat_path)
            print(f"[INFO] Restore script ready: {saved}")
        return True

    print("[ACTION] Disabling Windows SMHNR (DisableSmartNameResolution = 1)...")
    if is_admin():
        import winreg
        with winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, REG_SUBKEY) as key:
            winreg.SetValueEx(key, REG_VALUE, 0, winreg.REG_DWORD, 1)
        subprocess.run(["ipconfig", "/flushdns"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        print("[INFO] Administrator privileges required — please approve the UAC prompt...")
        _run_elevated_cmd(
            f'reg add "{REG_PATH_CLI}" /v {REG_VALUE} /t REG_DWORD /d 1 /f && ipconfig /flushdns'
        )
        time.sleep(0.5)

    if get_smhnr_disabled():
        print("[OK] Windows SMHNR disabled successfully (DisableSmartNameResolution = 1).")
        if restore_bat_path:
            saved = write_restore_bat(restore_bat_path)
            print(f"[OK] Generated one-click restore script: {saved}")
        return True

    print("[WARN] Failed to disable Windows SMHNR (UAC cancelled or insufficient permissions).")
    print("       You can run this manually in an Administrator PowerShell:")
    print(
        '       New-Item -Path "HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows NT\\DNSClient" -Force | Out-Null; '
        'New-ItemProperty -Path "HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows NT\\DNSClient" '
        '-Name "DisableSmartNameResolution" -PropertyType DWord -Value 1 -Force | Out-Null; ipconfig /flushdns'
    )
    return False


def restore_smhnr():
    if not is_windows():
        print("[INFO] Non-Windows OS detected; nothing to restore.")
        return True

    if not get_smhnr_disabled():
        print("[OK] Windows SMHNR is already at system default.")
        return True

    print("[ACTION] Restoring Windows SMHNR to system default...")
    if is_admin():
        subprocess.run(["reg", "delete", REG_PATH_CLI, "/v", REG_VALUE, "/f"], check=False)
        subprocess.run(["ipconfig", "/flushdns"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        print("[INFO] Administrator privileges required — please approve the UAC prompt...")
        _run_elevated_cmd(
            f'reg delete "{REG_PATH_CLI}" /v {REG_VALUE} /f && ipconfig /flushdns'
        )
        time.sleep(0.5)

    if not get_smhnr_disabled():
        print("[OK] Windows SMHNR restored to system default.")
        return True

    print("[WARN] Failed to restore Windows SMHNR.")
    return False


def main():
    parser = argparse.ArgumentParser(description="Manage Windows SMHNR DNS leak protection")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--status", action="store_true", help="Check current SMHNR status")
    group.add_argument("--disable", action="store_true", help="Disable Windows SMHNR (recommended for Clash TUN)")
    group.add_argument("--restore", action="store_true", help="Restore Windows SMHNR to default")
    parser.add_argument("--restore-bat", help="Optional path to generate a one-click restore .bat script")
    args = parser.parse_args()

    if args.status:
        if not is_windows():
            print("[INFO] Non-Windows platform: SMHNR does not apply.")
            sys.exit(0)
        disabled = get_smhnr_disabled()
        if disabled:
            print("[PASS] Windows SMHNR is DISABLED (DisableSmartNameResolution = 1).")
            sys.exit(0)
        else:
            print("[WARN] Windows SMHNR is ENABLED (default). Parallel DNS queries may leak on Windows.")
            sys.exit(1)

    if args.disable:
        ok = disable_smhnr(restore_bat_path=args.restore_bat)
        sys.exit(0 if ok else 1)

    if args.restore:
        ok = restore_smhnr()
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

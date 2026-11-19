#!/usr/bin/env python3
"""
Automated One-Click VPS Deployer for Claude Anti-Ban Network.
Connects to target VPS via SSH, uploads and runs vps_setup.sh, parses credentials,
and generates local Clash Verge YAML profiles and subscription links.
"""

import argparse
import json
import os
import re
import sys
import time

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

try:
    import paramiko
except ImportError:
    print("Error: paramiko is required. Install it via 'pip install paramiko'")
    sys.exit(1)

def run_remote_deployment(host, port, user, password=None, key_file=None, node_name="🇺🇸 独享-Claude-原生住宅9929", output_yaml=None, google_route="direct", skip_smhnr=False):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    setup_sh_path = os.path.join(script_dir, "vps_setup.sh")
    gen_config_path = os.path.join(script_dir, "generate_clash_config.py")
    smhnr_script_path = os.path.join(script_dir, "windows_smhnr.py")

    if not os.path.exists(setup_sh_path):
        print(f"Error: Setup script not found at {setup_sh_path}")
        sys.exit(1)

    print(f"\n=======================================================")
    print(f" Connecting to VPS {host}:{port} as {user}...")
    print(f"=======================================================")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        connect_kwargs = {
            "hostname": host,
            "port": port,
            "username": user,
            "timeout": 15
        }
        if key_file:
            connect_kwargs["key_filename"] = key_file
        if password:
            connect_kwargs["password"] = password

        ssh.connect(**connect_kwargs)
        print(" Connected successfully via SSH!\n")
    except Exception as e:
        print(f"SSH Connection Failed: {e}")
        sys.exit(1)

    # 1. Read vps_setup.sh and ensure LF line endings
    with open(setup_sh_path, "r", encoding="utf-8") as f:
        sh_content = f.read().replace("\r\n", "\n")

    # 2. Upload via SFTP
    print("[1/3] Uploading vps_setup.sh to remote /tmp/vps_setup.sh...")
    sftp = ssh.open_sftp()
    with sftp.file("/tmp/vps_setup.sh", "w") as remote_file:
        remote_file.write(sh_content)
    sftp.chmod("/tmp/vps_setup.sh", 0o755)
    sftp.close()

    # 3. Execute setup script and capture output
    print(f"[2/3] Executing setup on VPS (installing Xray v26.6.27, WARP standby, tuning kernel, Google route: {google_route})...")
    stdin, stdout, stderr = ssh.exec_command(f"GOOGLE_OUTBOUND={google_route} bash /tmp/vps_setup.sh")

    full_output = ""
    while True:
        line = stdout.readline()
        if not line:
            break
        print(line, end="")
        full_output += line

    err_output = stderr.read().decode('utf-8', errors='replace')
    if err_output:
        print("\n[REMOTE STDERR]:\n" + err_output.strip())

    ssh.close()

    # 4. Extract JSON metadata
    json_match = re.search(r'###JSON_OUTPUT_START###(.*?)###JSON_OUTPUT_END###', full_output, re.DOTALL)
    if not json_match:
        print("\nError: Could not find JSON output from setup script.")
        sys.exit(1)

    meta = json.loads(json_match.group(1).strip())
    print("\n[3/3] Parsed Node Deployment Metadata:")
    print(json.dumps(meta, indent=2, ensure_ascii=False))

    # 5. Generate local Clash profile
    if not output_yaml:
        output_yaml = f"{node_name.replace(' ', '_')}.yaml"

    cmd = (
        f'python "{gen_config_path}" '
        f'--ip "{meta["server_ip"]}" '
        f'--port {meta["port"]} '
        f'--uuid "{meta["uuid"]}" '
        f'--public-key "{meta["public_key"]}" '
        f'--short-id "{meta["short_id"]}" '
        f'--name "{node_name}" '
        f'--output "{output_yaml}"'
    )
    os.system(cmd)

    # 6. Platform-specific DNS / IPv6 anti-leak post-step
    if sys.platform == "win32" and not skip_smhnr and os.path.exists(smhnr_script_path):
        print("\n[Windows DNS Hardening] Checking Windows SMHNR status...")
        desktop_restore = os.path.join(os.path.expanduser("~"), "Desktop", "复原Windows-SMHNR.bat")
        os.system(f'python "{smhnr_script_path}" --disable --restore-bat "{desktop_restore}"')
    elif sys.platform == "darwin":
        print("\n[macOS Anti-Leak Advisory (No System Settings Modified Automatically)]")
        print("  1. macOS does NOT have Windows SMHNR — no SMHNR change is needed.")
        print("  2. Note: macOS has no Windows WFP; when top-level ipv6 is false, native Wi-Fi public IPv6")
        print("     may bypass utun. You may optionally set Wi-Fi IPv6 to 'Link-local only' in System Settings")
        print("     (may affect IPv6-only intranet sites; left to your own choice and NOT changed automatically).")
        print("  3. Run 'scutil --dns' after enabling TUN to verify resolver #1 points to 198.18.0.2")
        print("     (and is not overridden by Tailscale MagicDNS 100.100.100.100 or iCloud Private Relay).")
        print("  4. Keep 'DNS Override' and 'IPv6' turned OFF in Clash Verge Rev settings.")

    print("\n=======================================================")
    print(" ALL DEPLOYMENT STEPS COMPLETED!")
    print(f" Local Clash Verge Profile : {os.path.abspath(output_yaml)}")
    print(f" Local Shadowrocket Conf   : {os.path.splitext(os.path.abspath(output_yaml))[0]}.conf")
    print(f" iOS VLESS Share URL       : {meta.get('vless_url', '')}")
    print(f" iOS Shadowrocket Conf URL : {meta.get('shadowrocket_conf_url', '')}")
    print(f" Android Clash Sub URL     : {meta.get('subscription_url', '')}")
    print("=======================================================\n")

def main():
    parser = argparse.ArgumentParser(description="One-click Deployer for Claude Anti-Ban VPS")
    parser.add_argument("--host", required=True, help="Remote VPS IP address")
    parser.add_argument("--port", type=int, default=22, help="Remote SSH port (default: 22)")
    parser.add_argument("--user", default="root", help="Remote SSH user (default: root)")
    parser.add_argument("--password", help="Remote SSH password")
    parser.add_argument("--key-file", help="Path to SSH private key file")
    parser.add_argument("--node-name", default="🇺🇸 独享-Claude-原生住宅9929", help="Node display name in Clash Verge")
    parser.add_argument("--google-route", choices=["direct", "warp"], default="direct", help="Google & Gemini server outbound route (default: direct)")
    parser.add_argument("--output", help="Target output YAML filename")
    parser.add_argument("--skip-smhnr", action="store_true", help="Skip automatically disabling Windows SMHNR on Windows")

    args = parser.parse_args()

    if not args.password and not args.key_file:
        print("Error: Either --password or --key-file must be specified.", file=sys.stderr)
        sys.exit(1)

    run_remote_deployment(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        key_file=args.key_file,
        node_name=args.node_name,
        output_yaml=args.output,
        google_route=args.google_route,
        skip_smhnr=args.skip_smhnr
    )

if __name__ == "__main__":
    main()

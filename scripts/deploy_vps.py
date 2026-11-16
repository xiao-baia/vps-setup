#!/usr/bin/env python3
"""
Automated One-Click VPS Deployer for Claude Anti-Ban Network.
Connects to target VPS via SSH, uploads and runs vps_setup.sh, parses credentials,
and generates local Clash Verge YAML profiles, Shadowrocket anti-leak conf, and subscription links.
"""

import argparse
import json
import os
import re
import subprocess
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

try:
    import paramiko
except ImportError:
    print("Error: paramiko is required. Install it via 'pip install paramiko'")
    sys.exit(1)


def run_remote_deployment(
    host,
    port,
    user,
    password=None,
    key_file=None,
    node_name="🇺🇸 独享-Claude-原生住宅9929",
    output_yaml=None,
    google_route="direct",
    mode=None,
    socks5_server=None,
    socks5_port=None,
    socks5_user=None,
    socks5_pass=None,
    socks5_name="🏠 独享-静态住宅落地",
    shadowrocket_output=None,
    no_killswitch=False,
):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    setup_sh_path = os.path.join(script_dir, "vps_setup.sh")
    gen_config_path = os.path.join(script_dir, "generate_clash_config.py")
    killswitch_path = os.path.join(script_dir, "setup_killswitch.py")

    if not os.path.exists(setup_sh_path):
        print(f"Error: Setup script not found at {setup_sh_path}")
        sys.exit(1)

    print("\n=======================================================")
    print(f" Connecting to VPS {host}:{port} as {user}...")
    print("=======================================================")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        connect_kwargs = {
            "hostname": host,
            "port": port,
            "username": user,
            "timeout": 15,
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
    print(
        f"[2/3] Executing setup on VPS (installing Xray v26.6.27, WARP standby, tuning kernel, Google route: {google_route})..."
    )
    stdin, stdout, stderr = ssh.exec_command(
        f"GOOGLE_OUTBOUND={google_route} bash /tmp/vps_setup.sh"
    )

    full_output = ""
    while True:
        line = stdout.readline()
        if not line:
            break
        print(line, end="")
        full_output += line

    err_output = stderr.read().decode("utf-8", errors="replace")
    if err_output:
        print("\n[REMOTE STDERR]:\n" + err_output.strip())

    ssh.close()

    # 4. Extract JSON metadata
    json_match = re.search(
        r"###JSON_OUTPUT_START###(.*?)###JSON_OUTPUT_END###", full_output, re.DOTALL
    )
    if not json_match:
        print("\nError: Could not find JSON output from setup script.")
        sys.exit(1)

    meta = json.loads(json_match.group(1).strip())
    print("\n[3/3] Parsed Node Deployment Metadata:")
    print(json.dumps(meta, indent=2, ensure_ascii=False))

    # 5. Generate local Clash profile & Shadowrocket profile
    if not output_yaml:
        output_yaml = f"{node_name.replace(' ', '_')}.yaml"
    abs_yaml = os.path.abspath(output_yaml)
    abs_sr = os.path.abspath(
        shadowrocket_output or f"{os.path.splitext(abs_yaml)[0]}.shadowrocket.conf"
    )

    cmd = [
        sys.executable,
        gen_config_path,
        "--ip",
        str(meta["server_ip"]),
        "--port",
        str(meta["port"]),
        "--uuid",
        str(meta["uuid"]),
        "--public-key",
        str(meta["public_key"]),
        "--short-id",
        str(meta["short_id"]),
        "--name",
        node_name,
        "--output",
        abs_yaml,
        "--shadowrocket-output",
        abs_sr,
    ]
    if mode:
        cmd.extend(["--mode", mode])
    if socks5_server:
        cmd.extend(["--socks5-server", socks5_server])
    if socks5_port is not None:
        cmd.extend(["--socks5-port", str(socks5_port)])
    if socks5_user:
        cmd.extend(["--socks5-user", socks5_user])
    if socks5_pass:
        cmd.extend(["--socks5-pass", socks5_pass])
    if socks5_name:
        cmd.extend(["--socks5-name", socks5_name])

    subprocess.run(cmd, check=True)

    # 6. Run read-only local audit (detects Tailscale DNS, Claude autostart, Clash Verge UI DNS/IPv6 flags)
    if os.path.exists(killswitch_path):
        print("\n[4/5] Running Read-Only Environment & Client Audit (clash-guard)...")
        subprocess.run([sys.executable, killswitch_path, "--action", "audit"], check=False)

    # 7. Enable system-level Kill Switch firewall by default (without touching Clash Verge subscriptions)
    if not no_killswitch and os.path.exists(killswitch_path):
        print("\n[5/5] Enabling System-Level Kill Switch Firewall (clash-guard)...")
        ks_res = subprocess.run(
            [sys.executable, killswitch_path, "--action", "install-killswitch", "--skip-backup"]
        )
        if ks_res.returncode == 0:
            print("[OK] System-level Kill Switch (local.clash-guard) installed (disarmed on boot, auto-arms when TUN is enabled, stays locked on abnormal drops, resets on reboot)!")
        else:
            print(
                "[WARN] Kill Switch elevation was not completed (e.g. UAC prompt was cancelled or sudo is required).\n"
                f'       To install/enable it manually, run:\n       python "{killswitch_path}" --action install-killswitch --skip-backup'
            )

    print("\n=======================================================")
    print(" ALL DEPLOYMENT STEPS COMPLETED!")
    print(f" Local Clash Verge Profile : {abs_yaml}")
    print(f" Local Shadowrocket Conf   : {abs_sr}")
    print(f" iOS VLESS Share URL       : {meta.get('vless_url', '')}")
    print(f" iOS Shadowrocket Conf URL : {meta.get('shadowrocket_conf_url', '')}")
    print(f" Android Clash Sub URL     : {meta.get('subscription_url', '')}")
    print("=======================================================\n")


def main():
    parser = argparse.ArgumentParser(
        description="One-click Deployer for Claude Anti-Ban VPS"
    )
    parser.add_argument("--host", required=True, help="Remote VPS IP address")
    parser.add_argument("--port", type=int, default=22, help="Remote SSH port (default: 22)")
    parser.add_argument("--user", default="root", help="Remote SSH user (default: root)")
    parser.add_argument("--password", help="Remote SSH password")
    parser.add_argument("--key-file", help="Path to SSH private key file")
    parser.add_argument(
        "--node-name",
        default="🇺🇸 独享-Claude-原生住宅9929",
        help="Node display name in Clash Verge",
    )
    parser.add_argument(
        "--google-route",
        choices=["direct", "warp"],
        default="direct",
        help="Google & Gemini server outbound route (default: direct)",
    )
    parser.add_argument("--output", help="Target output YAML filename")
    parser.add_argument("--shadowrocket-output", help="Target output Shadowrocket .conf filename")
    parser.add_argument(
        "--mode",
        choices=["A", "B"],
        default=None,
        help="Egress mode: A=VPS direct (default), B=VPS jump -> static residential SOCKS5",
    )
    parser.add_argument("--socks5-server", help="Static residential SOCKS5 IP/host (Mode B)")
    parser.add_argument("--socks5-port", type=int, help="Static residential SOCKS5 port (Mode B)")
    parser.add_argument("--socks5-user", help="Static residential SOCKS5 username (Mode B)")
    parser.add_argument("--socks5-pass", help="Static residential SOCKS5 password (Mode B)")
    parser.add_argument(
        "--socks5-name",
        default="🏠 独享-静态住宅落地",
        help="Display name for Mode B SOCKS5 proxy",
    )
    parser.add_argument(
        "--no-killswitch",
        action="store_true",
        help="Skip automatic local Kill Switch firewall setup after deployment",
    )

    args = parser.parse_args()

    if not args.password and not args.key_file:
        print(
            "Error: Either --password or --key-file must be specified.",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.mode == "B" and (not args.socks5_server or not args.socks5_port):
        print(
            "Error: Mode B requires both '--socks5-server' and '--socks5-port'.",
            file=sys.stderr,
        )
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
        mode=args.mode,
        socks5_server=args.socks5_server,
        socks5_port=args.socks5_port,
        socks5_user=args.socks5_user,
        socks5_pass=args.socks5_pass,
        socks5_name=args.socks5_name,
        shadowrocket_output=args.shadowrocket_output,
        no_killswitch=args.no_killswitch,
    )


if __name__ == "__main__":
    main()

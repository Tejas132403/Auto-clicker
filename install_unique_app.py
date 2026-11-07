#!/usr/bin/env python3
"""
install_unique_app.py
=====================
Standalone shortcut script to generate and install a 100% unique dummy app
for Ad/Quiz/Video install tasks on connected Android devices.

Every execution creates:
  - Unique Package Name (from trillions of possible permutations)
  - Unique App Label / Title
  - Unique APK Signature & Build ID
  - Unique Android OS UID upon installation
"""

import os
import sys
import time
import json
import random
import string
import shutil
import zipfile
import argparse
import subprocess
from datetime import datetime

# Ensure UTF-8 output even in Windows legacy console
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DUMMY_SOURCE_APK = os.path.join(BASE_DIR, "in.binarybox.blackscreen for ad installation.apk")
BUILD_DIR = os.path.join(BASE_DIR, "tmp_build")
HISTORY_FILE = os.path.join(BUILD_DIR, "installed_dummy_apps.json")

ORIGINAL_PKG = "in.binarybox.blackscreen"  # 24 chars
ORIGINAL_LBL = "Black Screen"               # 12 chars

PKG_PREFIXES = [
    "com.clean.app_",
    "com.boost.app_",
    "com.turbo.app_",
    "com.speed.app_",
    "com.hyper.app_",
    "com.smart.app_",
    "com.quick.app_",
    "com.power.app_",
    "com.ultra.app_",
    "com.super.app_",
    "com.flash.app_",
    "com.space.app_",
    "com.elite.app_",
    "com.games.app_",
    "com.tools.app_",
    "com.store.app_",
    "com.swift.app_",
    "com.nova.app_",
    "com.alpha.app_",
    "com.prime.app_",
]

APP_LABELS = [
    "Game Booster", "Clean Master", "Fast Cleaner", "Power Boost ",
    "Turbo Clean ", "Super Saver ", "Speed Boost ", "Phone Cooler",
    "Ultra Clean ", "Smart Saver ", "Quick Charge", "RAM Booster ",
    "Battery Pro ", "Hyper Boost ", "Flash Clean ", "Nova Cleaner",
    "Easy Booster", "Magic Clean ", "Pro Booster ", "Super Turbo ",
    "Rocket Boost", "Max Cleaner ", "Swift Speed ", "Fast Booster",
    "Device Clean", "Speed Master", "Power Master", "Elite Cleaner",
]


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def run_cmd(cmd, timeout=30):
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return res.returncode, res.stdout, res.stderr
    except Exception as e:
        return -1, "", str(e)


def get_connected_device():
    """Returns connected ADB serial or None."""
    rc, stdout, _ = run_cmd(["adb", "devices"])
    if rc != 0:
        return None
    for line in stdout.splitlines()[1:]:
        parts = line.strip().split()
        if len(parts) >= 2 and parts[1] == "device":
            return parts[0]
    return None


def get_device_model(serial=None):
    cmd = ["adb"]
    if serial:
        cmd.extend(["-s", serial])
    cmd.extend(["shell", "getprop", "ro.product.model"])
    rc, stdout, _ = run_cmd(cmd)
    return stdout.strip() if rc == 0 and stdout.strip() else "Android Device"


def find_apksigner_and_keystore():
    """Finds apksigner executable and Android debug keystore."""
    sdk_root = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    if not sdk_root:
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        cand = os.path.join(local_app_data, "Android", "Sdk")
        if os.path.exists(cand):
            sdk_root = cand

    apksigner = None
    if sdk_root:
        bt_dir = os.path.join(sdk_root, "build-tools")
        if os.path.isdir(bt_dir):
            versions = sorted(os.listdir(bt_dir), reverse=True)
            for v in versions:
                cand = os.path.join(bt_dir, v, "apksigner.bat" if os.name == "nt" else "apksigner")
                if os.path.exists(cand):
                    apksigner = cand
                    break

    userprofile = os.environ.get("USERPROFILE") or os.path.expanduser("~")
    keystore = os.path.join(userprofile, ".android", "debug.keystore")
    return apksigner, keystore


def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_history(entry):
    os.makedirs(BUILD_DIR, exist_ok=True)
    history = load_history()
    history.append(entry)
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        log(f"Warning: Failed to save history: {e}")


def generate_unique_apk():
    """Generates a newly patched and signed APK with completely unique pkg name & label."""
    if not os.path.exists(DUMMY_SOURCE_APK):
        raise FileNotFoundError(f"Source APK not found: {DUMMY_SOURCE_APK}")

    apksigner, keystore = find_apksigner_and_keystore()
    if not apksigner or not os.path.exists(apksigner):
        raise RuntimeError("apksigner executable not found in Android SDK build-tools.")
    if not keystore or not os.path.exists(keystore):
        raise RuntimeError(f"Debug keystore not found at {keystore}.")

    # Generate random package name with exact 24-character length
    pfx = random.choice(PKG_PREFIXES)
    needed_len = len(ORIGINAL_PKG) - len(pfx)
    rand_chars = "".join(random.choices(string.ascii_lowercase + string.digits, k=needed_len))
    new_pkg = f"{pfx}{rand_chars}"
    assert len(new_pkg) == len(ORIGINAL_PKG), f"Pkg length mismatch: {len(new_pkg)} != {len(ORIGINAL_PKG)}"

    # Generate random label with exact 12-character length
    new_label = random.choice(APP_LABELS)
    assert len(new_label) == len(ORIGINAL_LBL), f"Label length mismatch: {len(new_label)} != {len(ORIGINAL_LBL)}"

    build_id = "".join(random.choices(string.hexdigits.lower(), k=12))

    os.makedirs(BUILD_DIR, exist_ok=True)
    out_apk = os.path.join(BUILD_DIR, f"{new_pkg}.apk")
    if os.path.exists(out_apk):
        try:
            os.remove(out_apk)
        except Exception:
            pass

    old_pkg_bytes = ORIGINAL_PKG.encode("utf-16le")
    new_pkg_bytes = new_pkg.encode("utf-16le")
    old_lbl_bytes = ORIGINAL_LBL.encode("utf-8")
    new_lbl_bytes = new_label.encode("utf-8")

    with zipfile.ZipFile(DUMMY_SOURCE_APK, "r") as zin:
        manifest = zin.read("AndroidManifest.xml")
        pos_pkg = manifest.find(old_pkg_bytes)
        if pos_pkg != -1:
            new_manifest = manifest[:pos_pkg] + new_pkg_bytes + manifest[pos_pkg + len(old_pkg_bytes):]
        else:
            new_manifest = manifest

        arsc = zin.read("resources.arsc")
        pos_lbl = arsc.find(old_lbl_bytes)
        if pos_lbl != -1:
            new_arsc = arsc[:pos_lbl] + new_lbl_bytes + arsc[pos_lbl + len(old_lbl_bytes):]
        else:
            new_arsc = arsc

        with zipfile.ZipFile(out_apk, "w", compression=zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                if item.filename.startswith("META-INF/"):
                    continue  # Strip existing signature
                if item.filename == "AndroidManifest.xml":
                    zout.writestr(item, new_manifest)
                elif item.filename == "resources.arsc":
                    zout.writestr(item, new_arsc)
                else:
                    zout.writestr(item, zin.read(item.filename))

    # Re-sign APK
    cmd_sign = [
        apksigner, "sign",
        "--ks", keystore,
        "--ks-pass", "pass:android",
        "--key-pass", "pass:android",
        "--ks-key-alias", "androiddebugkey",
        out_apk
    ]
    rc, stdout, stderr = run_cmd(cmd_sign)
    if rc != 0:
        raise RuntimeError(f"apksigner failed: {stderr or stdout}")

    return out_apk, new_pkg, new_label, build_id


def install_apk_on_device(apk_path, serial=None):
    """Installs APK on mobile device via ADB."""
    cmd = ["adb"]
    if serial:
        cmd.extend(["-s", serial])
    cmd.extend(["install", "-r", "-g", apk_path])
    rc, stdout, stderr = run_cmd(cmd, timeout=45)
    output = f"{stdout}\n{stderr}".strip()
    return rc == 0 and "Success" in output, output


def launch_app_on_device(pkg_name, serial=None):
    """Launches the dummy app's main activity."""
    cmd = ["adb"]
    if serial:
        cmd.extend(["-s", serial])
    cmd.extend(["shell", "am", "start", "-n", f"{pkg_name}/in.binarybox.blackscreen.MainActivity"])
    rc, stdout, stderr = run_cmd(cmd)
    return rc == 0, f"{stdout}\n{stderr}".strip()


def uninstall_app_on_device(pkg_name, serial=None):
    """Uninstalls app via ADB."""
    cmd = ["adb"]
    if serial:
        cmd.extend(["-s", serial])
    cmd.extend(["uninstall", pkg_name])
    rc, stdout, stderr = run_cmd(cmd, timeout=30)
    return rc == 0 and "Success" in (stdout + stderr), f"{stdout}\n{stderr}".strip()


def list_installed_dummy_apps(serial=None):
    """Lists dummy apps installed on device matching com.*.app_* or history."""
    history = load_history()
    hist_pkgs = {h["package"] for h in history}

    cmd = ["adb"]
    if serial:
        cmd.extend(["-s", serial])
    cmd.extend(["shell", "pm", "list", "packages"])
    rc, stdout, _ = run_cmd(cmd)
    if rc != 0:
        return []

    installed = []
    for line in stdout.splitlines():
        if line.startswith("package:"):
            pkg = line.replace("package:", "").strip()
            if pkg in hist_pkgs or (pkg.startswith("com.") and ".app_" in pkg) or pkg == ORIGINAL_PKG:
                installed.append(pkg)
    return installed


def clean_all_dummy_apps(serial=None):
    """Uninstalls all dummy apps created by this utility from the device."""
    apps = list_installed_dummy_apps(serial)
    if not apps:
        log("No dummy apps found installed on device.")
        return
    log(f"Found {len(apps)} dummy app(s) to remove...")
    for pkg in apps:
        ok, out = uninstall_app_on_device(pkg, serial)
        status = "✅ Removed" if ok else f"❌ Failed ({out})"
        log(f" - {pkg}: {status}")
    log("Cleanup complete.")


def main():
    parser = argparse.ArgumentParser(
        description="Generate & Install unique dummy app for install tasks on Android."
    )
    parser.add_argument("-s", "--serial", help="Specific ADB device serial")
    parser.add_argument("-l", "--launch", action="store_true", help="Launch the app immediately after installation")
    parser.add_argument("-u", "--uninstall-after", type=int, default=0,
                        help="Auto-uninstall the app after N seconds (e.g. -u 60)")
    parser.add_argument("--clean", action="store_true", help="Uninstall all dummy apps from device and exit")
    parser.add_argument("--list", action="store_true", help="List all dummy apps currently installed on device and exit")
    parser.add_argument("--non-interactive", action="store_true", help="Do not prompt for interactive menu")

    args = parser.parse_args()

    serial = args.serial or get_connected_device()
    if not serial:
        print("\n❌ Error: No Android device connected via ADB!")
        print("Please connect your phone with USB debugging enabled, then retry.\n")
        sys.exit(1)

    model = get_device_model(serial)

    # 1. Handle --clean
    if args.clean:
        print(f"\n[CLEAN] Removing all dummy apps from {model} ({serial})...")
        clean_all_dummy_apps(serial)
        sys.exit(0)

    # 2. Handle --list
    if args.list:
        print(f"\n[LIST] Installed dummy apps on {model} ({serial}):")
        apps = list_installed_dummy_apps(serial)
        if not apps:
            print("  (None found)")
        else:
            for i, p in enumerate(apps, 1):
                print(f"  {i}. {p}")
        print()
        sys.exit(0)

    # 3. Generate & Install Unique App
    print("=" * 68)
    print("  UNIQUE INSTALL TASK APP GENERATOR & INSTALLER")
    print("=" * 68)
    print(f"  Device:          {model} ({serial})")
    print("  Status:          Generating unique package identity...")

    try:
        out_apk, pkg_name, app_label, build_id = generate_unique_apk()
    except Exception as e:
        print(f"\n[ERROR] Generation failed: {e}\n")
        sys.exit(1)

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    apk_size_kb = os.path.getsize(out_apk) // 1024

    print(f"  Unique Package:  {pkg_name}")
    print(f"  App Title:       {app_label}")
    print(f"  Unique Build ID: {build_id}")
    print(f"  APK File Size:   {apk_size_kb} KB")
    print(f"  Timestamp:       {now_str}")
    print("  Action:          Installing onto mobile device via ADB...")

    ok, out = install_apk_on_device(out_apk, serial)
    if not ok:
        print(f"\n[ERROR] Installation failed: {out}\n")
        sys.exit(1)

    # Save to history
    save_history({
        "timestamp": now_str,
        "device": serial,
        "model": model,
        "package": pkg_name,
        "label": app_label,
        "build_id": build_id,
        "apk": out_apk
    })

    print("=" * 68)
    print("  [SUCCESS] Unique App INSTALLED on Mobile!")
    print("=" * 68)

    # If --launch specified
    if args.launch:
        print(f"  Launching {app_label} ({pkg_name})...")
        launch_app_on_device(pkg_name, serial)

    # If --uninstall-after specified
    if args.uninstall_after > 0:
        print(f"  Waiting {args.uninstall_after}s before auto-uninstall...")
        time.sleep(args.uninstall_after)
        print(f"  Auto-uninstalling {pkg_name}...")
        u_ok, u_out = uninstall_app_on_device(pkg_name, serial)
        if u_ok:
            print("  [OK] Uninstalled successfully!")
        else:
            print(f"  [FAIL] Uninstall failed: {u_out}")
        sys.exit(0)

    # If non-interactive CLI flag passed, exit here
    if args.non_interactive or args.launch:
        sys.exit(0)

    # Interactive menu for quick user control (useful when double-clicked)
    print("\nSelect an action:")
    print("  [1] Launch app on phone now")
    print("  [2] Auto-uninstall in 60 seconds (Install Task Simulation)")
    print("  [3] Uninstall this app now")
    print("  [4] Clean all dummy apps from device")
    print("  [Enter/5] Keep installed and exit")

    try:
        choice = input("\nEnter choice [1-5]: ").strip()
    except (KeyboardInterrupt, EOFError):
        choice = ""

    if choice == "1":
        print(f"\n  Launching {app_label} on mobile...")
        launch_app_on_device(pkg_name, serial)
        print("  Done! App is open on mobile.")
    elif choice == "2":
        print(f"\n  Launching app on mobile...")
        launch_app_on_device(pkg_name, serial)
        print(f"  App launched. Waiting 60 seconds before auto-uninstall...")
        time.sleep(60)
        print(f"  Auto-uninstalling {pkg_name}...")
        uninstall_app_on_device(pkg_name, serial)
        print("  Finished auto-uninstall!")
    elif choice == "3":
        print(f"\n  Uninstalling {pkg_name}...")
        uninstall_app_on_device(pkg_name, serial)
        print("  Uninstalled.")
    elif choice == "4":
        print("\n  Cleaning all dummy apps...")
        clean_all_dummy_apps(serial)
    else:
        print(f"\n  App '{app_label}' remains installed on your phone.")


if __name__ == "__main__":
    main()

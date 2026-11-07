import os
import sys
import time
import subprocess
import ctypes
from concurrent.futures import ThreadPoolExecutor

SDK_DIR = os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk")
EMULATOR_EXE = os.path.join(SDK_DIR, "emulator", "emulator.exe")
ADB_EXE = os.path.join(SDK_DIR, "platform-tools", "adb.exe")

PHONES = [
    {"name": "king1", "port": 5554, "serial": "emulator-5554"},
    {"name": "king2", "port": 5556, "serial": "emulator-5556"},
    {"name": "king3", "port": 5558, "serial": "emulator-5558"},
    {"name": "king4", "port": 5560, "serial": "emulator-5560"},
    {"name": "king5", "port": 5562, "serial": "emulator-5562"},
]

def run_adb(args):
    try:
        res = subprocess.run([ADB_EXE] + args, capture_output=True, text=True, timeout=10)
        return res.stdout.strip()
    except Exception as e:
        return f"Error: {e}"

def get_online_devices():
    output = run_adb(["devices"])
    online = {}
    for line in output.splitlines():
        line = line.strip()
        if not line or line.startswith("List of") or line.startswith("*"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            serial, state = parts[0], parts[1]
            if state == "device":
                online[serial] = True
    return online

def is_phone_booted(serial):
    try:
        res = subprocess.run(
            [ADB_EXE, "-s", serial, "shell", "getprop", "sys.boot_completed"],
            capture_output=True, text=True, timeout=5
        )
        return res.stdout.strip() == "1"
    except Exception:
        return False

def launch_phone(phone):
    name = phone["name"]
    port = phone["port"]
    serial = phone["serial"]

    # Check if already running
    online = get_online_devices()
    if serial in online and is_phone_booted(serial):
        print(f"[ALREADY RUNNING] {name} ({serial}) is already online.")
        return

    print(f"[LAUNCHING] Starting {name} on port {port} ({serial})...")

    cmd = f'start "" "{EMULATOR_EXE}" -avd {name} -port {port} -no-boot-anim -no-audio -gpu auto -cores 2 -memory 2048'
    subprocess.Popen(cmd, shell=True)

def tile_emulator_windows(target_phones=None):
    """Tiles emulator windows side by side across the screen"""
    if os.name != "nt":
        return

    phones_to_tile = target_phones if target_phones else PHONES
    count = max(1, len(phones_to_tile))

    try:
        user32 = ctypes.windll.user32
        user32.SetProcessDPIAware()
        screen_width = user32.GetSystemMetrics(0)
        screen_height = user32.GetSystemMetrics(1)

        if count == 1:
            win_w = 420
            win_h = min(screen_height - 80, 850)
        else:
            win_w = max(260, min(360, (screen_width - 40) // count))
            win_h = min(screen_height - 100, int(win_w * 1.85))

        titles_found = []

        def enum_windows_callback(hwnd, extra):
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    title = buff.value
                    title_lower = title.lower()
                    for p in phones_to_tile:
                        if p["name"] in title_lower or f"{p['port']}" in title_lower:
                            if not any(h == hwnd for h, _ in titles_found):
                                titles_found.append((hwnd, p["name"]))
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        user32.EnumWindows(WNDENUMPROC(enum_windows_callback), 0)

        # Sort by phone name king1..king5
        titles_found.sort(key=lambda x: x[1])

        print("\n[WINDOW ARRANGEMENT] Arranging emulator window(s)...")
        for i, (hwnd, name) in enumerate(titles_found[:count]):
            x = 20 + i * (win_w + 10)
            y = 40
            user32.MoveWindow(hwnd, x, y, win_w, win_h, True)
            print(f"  -> Positioned {name} at X={x}, Y={y}, Width={win_w}, Height={win_h}")

    except Exception as e:
        print(f"[!] Window tiling note: {e}")

def main():
    raw_args = [a.lower().strip() for a in sys.argv[1:] if not a.startswith("-")]
    if raw_args:
        selected_phones = [p for p in PHONES if p["name"].lower() in raw_args]
        if not selected_phones:
            print(f"[ERROR] No matching phone found for: {raw_args}")
            print(f"Available phones: {[p['name'] for p in PHONES]}")
            return
    else:
        selected_phones = PHONES

    phone_names_str = ", ".join(p["name"] for p in selected_phones)
    print("=" * 65)
    print(f"      KING PHONE LAUNCHER -> [{phone_names_str}]")
    print("=" * 65)

    # 1. Start selected phones with a slight stagger so disk I/O stays smooth
    for idx, phone in enumerate(selected_phones):
        launch_phone(phone)
        if idx < len(selected_phones) - 1:
            time.sleep(2.5)  # smooth staggered start

    print(f"\n[BOOT MONITOR] Waiting for {len(selected_phones)} phone(s) to become ONLINE and READY...")
    print("This usually takes ~15-40 seconds on first launch, or ~3-8s from snapshot.\n")

    max_wait = 180  # 3 minutes max
    start_time = time.time()

    ready_set = set()

    while time.time() - start_time < max_wait:
        for p in selected_phones:
            s = p["serial"]
            n = p["name"]
            if s not in ready_set:
                if is_phone_booted(s):
                    ready_set.add(s)
                    print(f"  [ONLINE] Phone '{n}' ({s}) is fully booted & READY!")

        if len(ready_set) == len(selected_phones):
            print("\n" + "=" * 65)
            print(f"  SELECTED PHONE(S) [{phone_names_str}] ARE ONLINE VIA ADB!")
            print("=" * 65)
            break

        time.sleep(3)

    if len(ready_set) < len(selected_phones):
        print(f"\n[INFO] {len(ready_set)}/{len(selected_phones)} devices ready. Remaining are still initializing in background.")

    # Arrange windows neatly
    time.sleep(2)
    tile_emulator_windows(selected_phones)

    print(f"\nPhone(s) ready: {phone_names_str}")
    print("To control via CLI: py king_multicontroller.py")
    print("Or open GUI: py king_sync_gui.py\n")

if __name__ == "__main__":
    main()

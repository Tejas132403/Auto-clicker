import os
import sys
import time
import shlex
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image

SDK_DIR = os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk")
ADB_EXE = os.path.join(SDK_DIR, "platform-tools", "adb.exe")

PHONES = [
    {"name": "king1", "port": 5554, "serial": "emulator-5554"},
    {"name": "king2", "port": 5556, "serial": "emulator-5556"},
    {"name": "king3", "port": 5558, "serial": "emulator-5558"},
    {"name": "king4", "port": 5560, "serial": "emulator-5560"},
    {"name": "king5", "port": 5562, "serial": "emulator-5562"},
]

KEY_ALIASES = {
    "home": 3,
    "back": 4,
    "recents": 187,
    "app_switch": 187,
    "power": 26,
    "enter": 66,
    "tab": 61,
    "space": 62,
    "delete": 67,
    "volume_up": 24,
    "volume_down": 25,
    "volup": 24,
    "voldown": 25,
    "mute": 164,
    "camera": 27,
}

class KingMultiController:
    def __init__(self):
        self.adb = ADB_EXE
        self.phones = {p["name"]: p["serial"] for p in PHONES}
        self.target_phones = list(self.phones.keys())  # Default: all 5

    def get_online_devices(self):
        try:
            res = subprocess.run([self.adb, "devices"], capture_output=True, text=True, timeout=5)
            lines = res.stdout.strip().splitlines()
            online_serials = set()
            for line in lines[1:]:
                parts = line.split()
                if len(parts) >= 2 and parts[1] == "device":
                    online_serials.add(parts[0])
            return {name: serial for name, serial in self.phones.items() if serial in online_serials}
        except Exception as e:
            print(f"[Error checking devices] {e}")
            return {}

    def get_active_serials(self):
        online = self.get_online_devices()
        active = []
        for name in self.target_phones:
            if name in online:
                active.append((name, online[name]))
        return active

    def execute_on_one(self, name, serial, args, capture=True):
        cmd = [self.adb, "-s", serial] + args
        try:
            res = subprocess.run(cmd, capture_output=capture, text=True, timeout=20)
            return name, True, res.stdout.strip() if capture else ""
        except Exception as e:
            return name, False, str(e)

    def broadcast(self, args, show_output=True):
        active = self.get_active_serials()
        if not active:
            print("[!] No targeted king devices are currently online!")
            print("    Run 'py king_launcher.py' to start them.")
            return {}

        results = {}
        with ThreadPoolExecutor(max_workers=len(active)) as executor:
            futures = [executor.submit(self.execute_on_one, name, serial, args) for name, serial in active]
            for f in as_completed(futures):
                name, success, out = f.result()
                results[name] = {"success": success, "output": out}

        if show_output:
            for name in sorted(results.keys()):
                info = results[name]
                status = "OK" if info["success"] else "FAIL"
                out_str = f" -> {info['output']}" if info['output'] else ""
                print(f"  [{name}] {status}{out_str}")

        return results

    # ================= COMMAND METHODS =================

    def tap(self, x, y):
        print(f"\n[BROADCAST TAP] Tapping at ({x}, {y}) on all phones simultaneously...")
        return self.broadcast(["shell", "input", "tap", str(x), str(y)])

    def swipe(self, x1, y1, x2, y2, duration=300):
        print(f"\n[BROADCAST SWIPE] Swiping from ({x1}, {y1}) to ({x2}, {y2}) [{duration}ms]...")
        return self.broadcast(["shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration)])

    def type_text(self, text):
        escaped = text.replace(" ", "%s")
        print(f"\n[BROADCAST TYPE] Typing: '{text}' on all phones...")
        return self.broadcast(["shell", "input", "text", escaped])

    def key(self, key_name):
        code = KEY_ALIASES.get(key_name.lower(), key_name)
        print(f"\n[BROADCAST KEY] Sending keyevent '{key_name}' ({code})...")
        return self.broadcast(["shell", "input", "keyevent", str(code)])

    def launch_app(self, package):
        print(f"\n[BROADCAST APP] Launching '{package}'...")
        return self.broadcast(["shell", "monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1"])

    def open_url(self, url):
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url
        print(f"\n[BROADCAST URL] Opening: {url}...")
        return self.broadcast(["shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", url])

    def shell(self, cmd):
        print(f"\n[BROADCAST SHELL] Executing: '{cmd}'...")
        return self.broadcast(["shell"] + shlex.split(cmd))

    def install_apk(self, apk_path):
        if not os.path.exists(apk_path):
            print(f"[!] APK file not found: {apk_path}")
            return
        print(f"\n[BROADCAST INSTALL] Installing APK on all phones: {apk_path}...")
        return self.broadcast(["install", "-r", apk_path])

    def capture_grid_screenshot(self, output_file="king_grid_preview.png"):
        active = self.get_active_serials()
        if not active:
            print("[!] No devices online.")
            return

        print(f"\n[SCREENSHOT] Capturing screens from {len(active)} phones...")
        shots = {}

        def grab_shot(name, serial):
            local_path = os.path.join(os.path.dirname(__file__), f"temp_{name}.png")
            remote_path = f"/sdcard/snap_{name}.png"
            subprocess.run([self.adb, "-s", serial, "shell", "screencap", "-p", remote_path], capture_output=True)
            subprocess.run([self.adb, "-s", serial, "pull", remote_path, local_path], capture_output=True)
            subprocess.run([self.adb, "-s", serial, "shell", "rm", remote_path], capture_output=True)
            return name, local_path

        with ThreadPoolExecutor(max_workers=len(active)) as executor:
            futures = [executor.submit(grab_shot, name, serial) for name, serial in active]
            for f in as_completed(futures):
                name, path = f.result()
                if os.path.exists(path):
                    shots[name] = path

        if not shots:
            print("[!] Failed to capture screenshots.")
            return

        # Tile them horizontally into a composite grid
        images = []
        for name, _ in sorted(active, key=lambda x: x[0]):
            if name in shots:
                try:
                    img = Image.open(shots[name])
                    img.thumbnail((360, 640))  # Scale for preview grid
                    images.append(img)
                except Exception:
                    pass

        if images:
            total_w = sum(im.width for im in images) + 10 * (len(images) - 1)
            max_h = max(im.height for im in images)
            grid = Image.new("RGB", (total_w, max_h), (25, 25, 25))

            cur_x = 0
            for im in images:
                grid.paste(im, (cur_x, 0))
                cur_x += im.width + 10

            save_dest = os.path.join(os.path.dirname(__file__), output_file)
            grid.save(save_dest)
            print(f"[OK] 5-Phone Combined Grid saved to: {save_dest}")

        # Cleanup temporary files
        for p in shots.values():
            try:
                os.remove(p)
            except Exception:
                pass

    def set_target(self, target_str):
        if target_str.lower() == "all":
            self.target_phones = list(self.phones.keys())
            print(f"[TARGET] Targeting ALL 5 phones: {', '.join(self.target_phones)}")
        else:
            selected = [t.strip() for t in target_str.split(",") if t.strip() in self.phones]
            if selected:
                self.target_phones = selected
                print(f"[TARGET] Targeting selected phones: {', '.join(self.target_phones)}")
            else:
                print(f"[!] Invalid target '{target_str}'. Options: all, king1, king2, king3, king4, king5")

    def show_status(self):
        online = self.get_online_devices()
        print("\n" + "=" * 50)
        print("          KING PHONES STATUS")
        print("=" * 50)
        for name, serial in self.phones.items():
            is_on = serial in online
            st = "ONLINE (Ready)" if is_on else "OFFLINE"
            targeted = " [TARGETED]" if name in self.target_phones else ""
            print(f"  {name.ljust(8)} | {serial.ljust(15)} | {st}{targeted}")
        print("=" * 50)

    # ================= INTERACTIVE CLI =================

    def run_cli(self):
        print("\n" + "=" * 65)
        print("       KING MULTI-PHONE SYNCHRONOUS CONTROLLER")
        print("=" * 65)
        print("All commands are sent simultaneously to online King phones!")
        print("Commands:")
        print("  tap <x> <y>                   -> Tap on all phones (e.g. tap 360 640)")
        print("  swipe <x1> <y1> <x2> <y2>     -> Swipe on all phones")
        print("  type <text>                   -> Type text into focused input")
        print("  home | back | recents | power -> Navigation buttons")
        print("  key <keycode>                 -> Send any keyevent")
        print("  open <package>                -> Launch app (e.g. open com.android.chrome)")
        print("  url <link>                    -> Open website in browser")
        print("  install <path/to/app.apk>     -> Install APK on all phones")
        print("  shell <cmd>                   -> Run shell command (e.g. shell ls /sdcard)")
        print("  screenshot                    -> Capture side-by-side composite grid")
        print("  target <all | king1,king2>    -> Switch target devices")
        print("  status                        -> View online state of all phones")
        print("  exit | quit                   -> Exit controller")
        print("=" * 65)

        self.show_status()

        while True:
            try:
                raw = input("\n[king-multi] > ").strip()
                if not raw:
                    continue

                parts = raw.split(maxsplit=1)
                cmd = parts[0].lower()
                arg = parts[1] if len(parts) > 1 else ""

                if cmd in ["exit", "quit", "q"]:
                    print("Exiting King Multi-Controller.")
                    break
                elif cmd == "status":
                    self.show_status()
                elif cmd == "target":
                    self.set_target(arg if arg else "all")
                elif cmd in ["home", "back", "recents", "power", "enter", "volup", "voldown"]:
                    self.key(cmd)
                elif cmd == "key":
                    if arg:
                        self.key(arg)
                    else:
                        print("Usage: key <home|back|recents|power|KEYCODE>")
                elif cmd == "tap":
                    coords = arg.split()
                    if len(coords) == 2:
                        self.tap(int(coords[0]), int(coords[1]))
                    else:
                        print("Usage: tap <x> <y>  (e.g. tap 360 640)")
                elif cmd == "swipe":
                    coords = arg.split()
                    if len(coords) >= 4:
                        dur = int(coords[4]) if len(coords) >= 5 else 300
                        self.swipe(int(coords[0]), int(coords[1]), int(coords[2]), int(coords[3]), dur)
                    else:
                        print("Usage: swipe <x1> <y1> <x2> <y2> [duration_ms]")
                elif cmd == "type":
                    if arg:
                        self.type_text(arg)
                    else:
                        print("Usage: type <text message>")
                elif cmd == "open":
                    if arg:
                        self.launch_app(arg)
                    else:
                        print("Usage: open <package_name> (e.g. open com.android.chrome)")
                elif cmd == "url":
                    if arg:
                        self.open_url(arg)
                    else:
                        print("Usage: url <https://example.com>")
                elif cmd == "install":
                    if arg:
                        self.install_apk(arg)
                    else:
                        print("Usage: install <path_to_apk>")
                elif cmd == "shell":
                    if arg:
                        self.shell(arg)
                    else:
                        print("Usage: shell <command>")
                elif cmd == "screenshot":
                    self.capture_grid_screenshot()
                else:
                    print(f"Unknown command '{cmd}'. Type 'status', 'tap', 'swipe', 'home', 'back', 'help'...")

            except KeyboardInterrupt:
                print("\nExiting.")
                break
            except Exception as e:
                print(f"[Error] {e}")

if __name__ == "__main__":
    controller = KingMultiController()
    controller.run_cli()

import os
import subprocess

SDK_DIR = os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk")
ADB_EXE = os.path.join(SDK_DIR, "platform-tools", "adb.exe")

PHONES = [
    {"name": "king1", "port": 5554, "serial": "emulator-5554"},
    {"name": "king2", "port": 5556, "serial": "emulator-5556"},
    {"name": "king3", "port": 5558, "serial": "emulator-5558"},
    {"name": "king4", "port": 5560, "serial": "emulator-5560"},
    {"name": "king5", "port": 5562, "serial": "emulator-5562"},
]

def stop_phones():
    print("=" * 60)
    print("STOPPING ALL 5 KING PHONES (Saving Quickboot Snapshots)")
    print("=" * 60)

    for p in PHONES:
        serial = p["serial"]
        name = p["name"]
        try:
            res = subprocess.run([ADB_EXE, "-s", serial, "emu", "kill"],
                                 capture_output=True, text=True, timeout=8)
            if "OK" in res.stdout:
                print(f"[SHUTDOWN] {name} ({serial}) shut down successfully.")
            else:
                print(f"[{name}] {serial}: Not running or already stopped.")
        except Exception:
            print(f"[{name}] {serial}: Not running.")

    print("\nAll king phones stopped cleanly.")

if __name__ == "__main__":
    stop_phones()

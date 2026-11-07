import subprocess
import xml.etree.ElementTree as ET
import sys
import os

# Set UTF-8 encoding for Hindi/Unicode characters
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

adb_path = r"C:\Users\tejas\AppData\Local\Android\Sdk\platform-tools\adb.exe"

# Dump UI hierarchy
subprocess.run([adb_path, "shell", "uiautomator", "dump", "/sdcard/live_dump.xml"], stdout=subprocess.DEVNULL)
xml_raw = subprocess.check_output([adb_path, "shell", "cat", "/sdcard/live_dump.xml"]).decode("utf-8", "replace")

print("=" * 65)
print("EXTRACTED MOBILE SCREEN TEXT (NO VISION / NO PHOTO)")
print("=" * 65)

if "<hierarchy" in xml_raw:
    root = ET.fromstring(xml_raw[xml_raw.find("<hierarchy"):])
    for n in root.iter("node"):
        text = n.get("text", "").strip()
        desc = n.get("content-desc", "").strip()
        pkg = n.get("package", "")
        rid = n.get("resource-id", "").split("/")[-1]
        bounds = n.get("bounds", "")
        clickable = n.get("clickable", "false")
        
        val = text if text else desc
        if val:
            print(f"[{rid or 'no-id':<25}] '{val}' (Clickable: {clickable}, Bounds: {bounds})")
else:
    print("Could not dump UI hierarchy (screen might be off or secure window).")


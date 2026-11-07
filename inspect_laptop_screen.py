import os
import sys
import subprocess
import json
import ctypes
from ctypes import wintypes

# Setup directories
script_dir = os.path.dirname(os.path.abspath(__file__))
screenshot_path = os.path.join(script_dir, "current_screen.png")

# 1. Capture primary screen screenshot using PowerShell + .NET (zero extra pip packages needed)
ps_code = f"""
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$screen = [System.Windows.Forms.Screen]::PrimaryScreen
$bounds = $screen.Bounds
$bitmap = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
$bitmap.Save('{screenshot_path.replace('\\', '\\\\')}', [System.Drawing.Imaging.ImageFormat]::Png)
$graphics.Dispose()
$bitmap.Dispose()
"""

try:
    subprocess.run(["powershell", "-NoProfile", "-Command", ps_code], check=True, capture_output=True, text=True)
    print(f"SCREENSHOT_SAVED: {screenshot_path}")
except Exception as e:
    print(f"SCREENSHOT_ERROR: {e}")

# 2. Get Foreground Window & Open Windows using Win32 API
user32 = ctypes.windll.user32

# Get foreground window
fg_hwnd = user32.GetForegroundWindow()
length = user32.GetWindowTextLengthW(fg_hwnd)
fg_title = ctypes.create_unicode_buffer(length + 1)
user32.GetWindowTextW(fg_hwnd, fg_title, length + 1)

rect = wintypes.RECT()
user32.GetWindowRect(fg_hwnd, ctypes.byref(rect))

print(f"FOREGROUND_WINDOW: '{fg_title.value}' (Rect: left={rect.left}, top={rect.top}, right={rect.right}, bottom={rect.bottom})")

# Enumerate visible top-level windows
windows = []
def enum_proc(hwnd, lParam):
    if user32.IsWindowVisible(hwnd):
        l = user32.GetWindowTextLengthW(hwnd)
        if l > 0:
            buff = ctypes.create_unicode_buffer(l + 1)
            user32.GetWindowTextW(hwnd, buff, l + 1)
            r = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(r))
            w = r.right - r.left
            h = r.bottom - r.top
            if w > 100 and h > 100:
                windows.append({
                    "hwnd": hwnd,
                    "title": buff.value,
                    "rect": [r.left, r.top, r.right, r.bottom],
                    "size": [w, h]
                })
    return True

WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
user32.EnumWindows(WNDENUMPROC(enum_proc), 0)

print("VISIBLE_WINDOWS:")
for w in windows:
    print(f" - [{w['size'][0]}x{w['size'][1]}] {w['title']}")

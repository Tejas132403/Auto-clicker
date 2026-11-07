import sys
import os
import time
import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

def attach_input_desktop():
    hdesk = user32.OpenInputDesktop(0, False, 0x01FF)
    if hdesk:
        user32.SetThreadDesktop(hdesk)
    return hdesk

def get_screen_size():
    attach_input_desktop()
    w = user32.GetSystemMetrics(0)
    h = user32.GetSystemMetrics(1)
    return w, h

def capture_screen(save_path="laptop_screen.png"):
    attach_input_desktop()
    from PIL import ImageGrab
    img = ImageGrab.grab()
    img.save(save_path)
    print(f"[OK] Screen captured to: {os.path.abspath(save_path)} (Size: {img.size[0]}x{img.size[1]})")
    return img

def list_windows():
    attach_input_desktop()
    windows = []
    def enum_proc(hwnd, lParam):
        if user32.IsWindowVisible(hwnd):
            l = user32.GetWindowTextLengthW(hwnd)
            if l > 0:
                buff = ctypes.create_unicode_buffer(l + 1)
                user32.GetWindowTextW(hwnd, buff, l + 1)
                rect = wintypes.RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(rect))
                w = rect.right - rect.left
                h = rect.bottom - rect.top
                if w > 50 and h > 50:
                    windows.append({
                        "hwnd": hwnd,
                        "title": buff.value,
                        "rect": (rect.left, rect.top, rect.right, rect.bottom),
                        "width": w,
                        "height": h
                    })
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows(WNDENUMPROC(enum_proc), 0)
    return windows

def focus_window(title_keyword):
    attach_input_desktop()
    wins = list_windows()
    for w in wins:
        if title_keyword.lower() in w["title"].lower():
            hwnd = w["hwnd"]
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            user32.SetForegroundWindow(hwnd)
            print(f"[OK] Focused window: '{w['title']}' (HWND: {hwnd})")
            return True
    print(f"[FAIL] No visible window found matching: '{title_keyword}'")
    return False

# Mouse Actions
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_ABSOLUTE = 0x8000

def move_cursor(x, y):
    attach_input_desktop()
    user32.SetCursorPos(int(x), int(y))

def click(x, y, button="left", double=False):
    attach_input_desktop()
    user32.SetCursorPos(int(x), int(y))
    time.sleep(0.05)
    
    if button == "left":
        down = MOUSEEVENTF_LEFTDOWN
        up = MOUSEEVENTF_LEFTUP
    elif button == "right":
        down = MOUSEEVENTF_RIGHTDOWN
        up = MOUSEEVENTF_RIGHTUP
    else:
        raise ValueError("button must be left or right")

    user32.mouse_event(down, 0, 0, 0, 0)
    time.sleep(0.05)
    user32.mouse_event(up, 0, 0, 0, 0)
    
    if double:
        time.sleep(0.1)
        user32.mouse_event(down, 0, 0, 0, 0)
        time.sleep(0.05)
        user32.mouse_event(up, 0, 0, 0, 0)
    print(f"[OK] Clicked at ({x}, {y}) [{button}]")

def type_text(text):
    attach_input_desktop()
    for char in text:
        vk = user32.VkKeyScanW(ord(char))
        shift = (vk >> 8) & 1
        code = vk & 0xFF
        if shift:
            user32.keybd_event(0x10, 0, 0, 0) # Shift down
        user32.keybd_event(code, 0, 0, 0)
        time.sleep(0.02)
        user32.keybd_event(code, 0, 2, 0) # Key up
        if shift:
            user32.keybd_event(0x10, 0, 2, 0) # Shift up
        time.sleep(0.02)
    print(f"[OK] Typed text: {text}")

def press_key(key_name):
    attach_input_desktop()
    KEY_MAP = {
        "enter": 0x0D,
        "esc": 0x1B,
        "space": 0x20,
        "tab": 0x09,
        "backspace": 0x08,
        "up": 0x26,
        "down": 0x28,
        "left": 0x25,
        "right": 0x27,
        "play_pause": 0xB3,
        "next_track": 0xB0,
        "prev_track": 0xB1,
        "volume_mute": 0xAD,
        "volume_down": 0xAE,
        "volume_up": 0xAF,
    }
    code = KEY_MAP.get(key_name.lower())
    if not code:
        print(f"[FAIL] Unknown key: {key_name}")
        return False
    user32.keybd_event(code, 0, 0, 0)
    time.sleep(0.05)
    user32.keybd_event(code, 0, 2, 0)
    print(f"[OK] Pressed key: {key_name}")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python laptop_clicker.py see               # Captures screen & lists windows")
        print("  python laptop_clicker.py click <x> <y>     # Click coordinates")
        print("  python laptop_clicker.py double <x> <y>    # Double click coordinates")
        print("  python laptop_clicker.py right <x> <y>     # Right click coordinates")
        print("  python laptop_clicker.py focus <keyword>   # Focus window")
        print("  python laptop_clicker.py type <string>     # Type text")
        print("  python laptop_clicker.py press <key>       # Press key (enter, space, play_pause, etc.)")
        sys.exit(0)

    cmd = sys.argv[1].lower()
    if cmd == "see":
        capture_screen("laptop_screen.png")
        print("\n--- OPEN WINDOWS ---")
        for w in list_windows():
            print(f" - [{w['width']}x{w['height']}] (at {w['rect'][0]},{w['rect'][1]}) \"{w['title']}\"")
    elif cmd == "click" and len(sys.argv) >= 4:
        click(sys.argv[2], sys.argv[3])
    elif cmd == "double" and len(sys.argv) >= 4:
        click(sys.argv[2], sys.argv[3], double=True)
    elif cmd == "right" and len(sys.argv) >= 4:
        click(sys.argv[2], sys.argv[3], button="right")
    elif cmd == "focus" and len(sys.argv) >= 3:
        focus_window(" ".join(sys.argv[2:]))
    elif cmd == "type" and len(sys.argv) >= 3:
        type_text(" ".join(sys.argv[2:]))
    elif cmd == "press" and len(sys.argv) >= 3:
        press_key(sys.argv[2])
    else:
        print(f"Invalid command or arguments: {sys.argv}")

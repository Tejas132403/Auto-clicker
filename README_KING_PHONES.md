# 👑 KING 5-Phone Multi-Device ADB System

Run and control **5 Android phones simultaneously** (`king1`, `king2`, `king3`, `king4`, `king5`) using Android Studio, ADB, and Python with zero latency.

---

## 📱 Device Mapping & Architecture

| Phone Name | Console Port | ADB Serial | Storage Location | Resolution / RAM |
| :--- | :--- | :--- | :--- | :--- |
| **`king1`** | `5554` | `emulator-5554` | `D:\Android_AVDs\king1.avd` | 720×1280 (320dpi) / 2GB |
| **`king2`** | `5556` | `emulator-5556` | `D:\Android_AVDs\king2.avd` | 720×1280 (320dpi) / 2GB |
| **`king3`** | `5558` | `emulator-5558` | `D:\Android_AVDs\king3.avd` | 720×1280 (320dpi) / 2GB |
| **`king4`** | `5560` | `emulator-5560` | `D:\Android_AVDs\king4.avd` | 720×1280 (320dpi) / 2GB |
| **`king5`** | `5562` | `emulator-5562` | `D:\Android_AVDs\king5.avd` | 720×1280 (320dpi) / 2GB |

> [!NOTE]
> All 5 devices are also directly visible in **Android Studio Device Manager**!
> The heavy storage images are kept on **Drive D:** to preserve free space on your C: drive.

---

## 🚀 Quick Start (1-Click Batch Files)

Located right in `D:\KING PROJECT\Auto clicker`:

1. **`1_SETUP_KING_PHONES.bat`**: Creates and configures `king1` to `king5` AVDs and SD cards.
2. **`2_START_KING_PHONES.bat`**: Launches all 5 phones, waits for ADB boot completion, and automatically tiles them side-by-side on your screen.
3. **`3_CONTROL_ALL_PHONES_GUI.bat`**: Opens the graphical desktop controller.
4. **`3_CONTROL_ALL_PHONES_CLI.bat`**: Opens the interactive command prompt controller.
5. **`4_STOP_ALL_PHONES.bat`**: Gracefully shuts down all 5 phones and saves quickboot snapshots.

---

## 🎮 Simultaneous Control Options

### Option A: Desktop GUI (`king_sync_gui.py`)
- Real-time online badges (`king1` to `king5`)
- Navigation buttons: `Home`, `Back`, `Recents`, `Power`, `Volume`
- Coordinate Tap: Enter `X` and `Y` and tap on all 5 phones at the same time
- Swipe: Enter start & end coordinates to scroll all 5 phones simultaneously
- Keyboard Typing: Type any text and send to the focused input on all phones
- App & URL Launcher: Launch Chrome, YouTube, or your custom APK across all phones
- 5-Phone Screenshot Grid: Grabs screens from all 5 phones and stitches them into a side-by-side preview (`king_grid_preview.png`)

### Option B: Interactive CLI (`king_multicontroller.py`)
Run `.\py.cmd king_multicontroller.py` in your terminal:
```text
[king-multi] > tap 360 640
[king-multi] > swipe 360 900 360 300
[king-multi] > type Hello World
[king-multi] > home
[king-multi] > back
[king-multi] > open com.android.chrome
[king-multi] > url https://www.google.com
[king-multi] > install my_app.apk
[king-multi] > shell getprop ro.product.model
[king-multi] > screenshot
[king-multi] > target king1,king2
[king-multi] > target all
```

---

## 💻 Python API (For Automation Scripts)

You can import the controller into your existing scripts (`mobile_controller.py`, `free_ai_bot.py`, etc.):

```python
from king_multicontroller import KingMultiController

ctl = KingMultiController()

# Simultaneous broadcast across all 5 phones in parallel threads
ctl.tap(360, 640)
ctl.swipe(360, 900, 360, 300, duration=250)
ctl.type_text("King Bot")
ctl.key("home")
ctl.launch_app("com.android.chrome")
ctl.open_url("https://example.com")
ctl.capture_grid_screenshot("grid.png")
```

---

## ⚡ Performance Optimizations Applied

Running 5 emulators on a laptop requires careful resource balancing:
1. **Resolution**: Scaled to 720×1280 (320 dpi) — reduces GPU pixel workload by 70% compared to 1080×2400 while remaining crisp.
2. **vCPUs**: Configured to 2 cores per emulator (10 total threads) leaving 6 CPU threads free for Windows and ADB.
3. **RAM**: Configured to 2GB per emulator. Total ~10GB RAM across all 5 devices, keeping total laptop memory within the 16GB limit.
4. **Hardware Acceleration**: Uses your discrete **NVIDIA GeForce RTX 3050 Laptop GPU**.
5. **No Bulky Window Borders**: `showDeviceFrame=no` removes the outer phone plastic mockups so the 5 screens tile neatly edge-to-edge.

import os
import sys
import subprocess
import shutil

SDK_DIR = os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk")
MKSDCARD = os.path.join(SDK_DIR, "emulator", "mksdcard.exe")
AVD_BASE_DIR = r"D:\Android_AVDs"
ANDROID_AVD_USER_DIR = os.path.expanduser(r"~\.android\avd")

PHONES = ["king1", "king2", "king3", "king4", "king5"]

CONFIG_TEMPLATE = """AvdId={name}
PlayStore.enabled=true
abi.type=x86_64
avd.ini.displayname={name}
avd.ini.encoding=UTF-8
disk.dataPartition.size=3G
fastboot.chosenSnapshotFile=
fastboot.forceChosenSnapshotBoot=no
fastboot.forceColdBoot=no
fastboot.forceFastBoot=yes
hw.accelerometer=yes
hw.arc=false
hw.audioInput=no
hw.battery=yes
hw.camera.back=none
hw.camera.front=none
hw.cpu.arch=x86_64
hw.cpu.ncore=2
hw.dPad=no
hw.device.hash2=MD5:2016577e1656e8e7c2adb0fac972beea
hw.device.manufacturer=Generic
hw.device.name=medium_phone
hw.gps=yes
hw.gpu.enabled=yes
hw.gpu.mode=auto
hw.gyroscope=yes
hw.initialOrientation=portrait
hw.keyboard=yes
hw.lcd.density=320
hw.lcd.height=1280
hw.lcd.width=720
hw.mainKeys=no
hw.ramSize=2048
hw.sdCard=yes
hw.sensors.light=yes
hw.sensors.magnetic_field=yes
hw.sensors.orientation=yes
hw.sensors.pressure=yes
hw.sensors.proximity=yes
hw.trackBall=no
image.sysdir.1=system-images\\android-36.1\\google_apis_playstore\\x86_64\\
runtime.network.latency=none
runtime.network.speed=full
sdcard.size=512M
showDeviceFrame=no
skin.dynamic=yes
skin.name=720x1280
skin.path=720x1280
tag.display=Google Play
tag.displaynames=Google Play
tag.id=google_apis_playstore
tag.ids=google_apis_playstore
target=android-36.1
vm.heapSize=336
"""

INI_TEMPLATE = """avd.ini.encoding=UTF-8
path={avd_dir}
target=android-36.1
"""

def setup_devices():
    os.makedirs(AVD_BASE_DIR, exist_ok=True)
    os.makedirs(ANDROID_AVD_USER_DIR, exist_ok=True)

    print("=" * 60)
    print("SETTING UP 5 ANDROID VIRTUAL PHONES (king1 to king5)")
    print(f"Base Directory: {AVD_BASE_DIR}")
    print(f"User AVD Registry: {ANDROID_AVD_USER_DIR}")
    print("=" * 60)

    for phone in PHONES:
        avd_dir = os.path.join(AVD_BASE_DIR, f"{phone}.avd")
        os.makedirs(avd_dir, exist_ok=True)

        # 1. Create sdcard.img if not exists
        sdcard_path = os.path.join(avd_dir, "sdcard.img")
        if not os.path.exists(sdcard_path):
            print(f"[{phone}] Creating sdcard.img (512MB)...")
            res = subprocess.run([MKSDCARD, "512M", sdcard_path], capture_output=True)
            if res.returncode != 0:
                print(f"  Warning: mksdcard exited with code {res.returncode}")

        # 2. Write config.ini in avd directory
        config_path = os.path.join(avd_dir, "config.ini")
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(CONFIG_TEMPLATE.format(name=phone))
        print(f"[{phone}] Written {config_path}")

        # 3. Write registry .ini in ~/.android/avd/
        ini_path = os.path.join(ANDROID_AVD_USER_DIR, f"{phone}.ini")
        with open(ini_path, "w", encoding="utf-8") as f:
            f.write(INI_TEMPLATE.format(avd_dir=avd_dir))
        print(f"[{phone}] Registered in Android Studio: {ini_path}")

    print("\n" + "=" * 60)
    print("SUCCESS: All 5 devices (king1 - king5) created & registered!")
    print("=" * 60)

if __name__ == "__main__":
    setup_devices()

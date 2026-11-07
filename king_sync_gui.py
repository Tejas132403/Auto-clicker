import os
import sys
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from king_multicontroller import KingMultiController, PHONES

class KingMultiGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("KING 5-PHONE MULTI-CONTROLLER (Simultaneous ADB Control)")
        self.root.geometry("820x760")
        self.root.minsize(700, 650)

        self.controller = KingMultiController()
        self.phone_status_vars = {}

        self._build_ui()
        self.refresh_status()

    def _build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")

        # Top Header
        header_frame = tk.Frame(self.root, bg="#1a1a2e", padx=15, pady=12)
        header_frame.pack(fill=tk.X)

        title_lbl = tk.Label(header_frame, text="KING MULTI-PHONE CONTROL CENTER", font=("Segoe UI", 16, "bold"), fg="#e94560", bg="#1a1a2e")
        title_lbl.pack(side=tk.LEFT)

        btn_tile = tk.Button(header_frame, text="📐 Tile Windows", font=("Segoe UI", 9, "bold"), bg="#0f3460", fg="white", relief=tk.FLAT, padx=8, pady=4, command=self.tile_windows)
        btn_tile.pack(side=tk.RIGHT, padx=5)

        btn_refresh = tk.Button(header_frame, text="🔄 Refresh", font=("Segoe UI", 9, "bold"), bg="#16213e", fg="white", relief=tk.FLAT, padx=8, pady=4, command=self.refresh_status)
        btn_refresh.pack(side=tk.RIGHT, padx=5)

        # Device Status Bar
        status_frame = tk.LabelFrame(self.root, text="Connected Devices (king1 - king5)", font=("Segoe UI", 10, "bold"), padx=10, pady=8)
        status_frame.pack(fill=tk.X, padx=15, pady=10)

        dev_grid = tk.Frame(status_frame)
        dev_grid.pack(fill=tk.X)

        for p in PHONES:
            name = p["name"]
            card = tk.Frame(dev_grid, bd=1, relief=tk.SOLID, padx=8, pady=6, bg="#f5f5f5")
            card.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=4)

            lbl_name = tk.Label(card, text=name.upper(), font=("Segoe UI", 11, "bold"), bg="#f5f5f5")
            lbl_name.pack()

            lbl_serial = tk.Label(card, text=p["serial"], font=("Segoe UI", 8), fg="#666", bg="#f5f5f5")
            lbl_serial.pack()

            var_status = tk.StringVar(value="Checking...")
            self.phone_status_vars[name] = var_status
            lbl_st = tk.Label(card, textvariable=var_status, font=("Segoe UI", 9, "bold"), fg="#888", bg="#f5f5f5")
            lbl_st.pack(pady=2)

        # Launcher & Stopper Controls
        ctl_frame = tk.Frame(self.root, padx=15)
        ctl_frame.pack(fill=tk.X, pady=4)

        btn_start_all = tk.Button(ctl_frame, text="▶ Start All 5 King Phones", font=("Segoe UI", 10, "bold"), bg="#28a745", fg="white", padx=12, pady=6, relief=tk.FLAT, command=self.start_all_phones)
        btn_start_all.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=4)

        btn_stop_all = tk.Button(ctl_frame, text="⏹ Stop All Phones (Save Snapshots)", font=("Segoe UI", 10, "bold"), bg="#dc3545", fg="white", padx=12, pady=6, relief=tk.FLAT, command=self.stop_all_phones)
        btn_stop_all.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=4)

        # Main Broadcast Control Tabs/Sections
        actions_frame = tk.LabelFrame(self.root, text="Simultaneous Broadcast Controls (All Devices)", font=("Segoe UI", 10, "bold"), padx=12, pady=10)
        actions_frame.pack(fill=tk.X, padx=15, pady=8)

        # 1. Navigation Key Bar
        nav_frame = tk.Frame(actions_frame)
        nav_frame.pack(fill=tk.X, pady=4)

        nav_btns = [
            ("🏠 Home", "home", "#34495e"),
            ("◀ Back", "back", "#34495e"),
            ("⬜ Recents", "recents", "#34495e"),
            ("⚡ Power", "power", "#7f8c8d"),
            ("🔊 Vol +", "volup", "#2c3e50"),
            ("🔉 Vol -", "voldown", "#2c3e50"),
            ("⏎ Enter", "enter", "#2c3e50"),
        ]

        for text, key_id, col in nav_btns:
            btn = tk.Button(nav_frame, text=text, font=("Segoe UI", 9, "bold"), bg=col, fg="white", relief=tk.FLAT, padx=6, pady=5, command=lambda k=key_id: self.send_key(k))
            btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        # 2. Tap & Swipe Inputs
        input_grid = tk.Frame(actions_frame)
        input_grid.pack(fill=tk.X, pady=8)

        # Tap
        tap_box = tk.LabelFrame(input_grid, text="Tap (X, Y)", padx=8, pady=4)
        tap_box.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=4)
        tk.Label(tap_box, text="X:").pack(side=tk.LEFT)
        self.entry_tap_x = tk.Entry(tap_box, width=6)
        self.entry_tap_x.insert(0, "360")
        self.entry_tap_x.pack(side=tk.LEFT, padx=3)
        tk.Label(tap_box, text="Y:").pack(side=tk.LEFT)
        self.entry_tap_y = tk.Entry(tap_box, width=6)
        self.entry_tap_y.insert(0, "640")
        self.entry_tap_y.pack(side=tk.LEFT, padx=3)
        btn_tap = tk.Button(tap_box, text="👉 Tap All", font=("Segoe UI", 9, "bold"), bg="#2980b9", fg="white", relief=tk.FLAT, padx=6, command=self.send_tap)
        btn_tap.pack(side=tk.RIGHT, padx=4)

        # Swipe
        swipe_box = tk.LabelFrame(input_grid, text="Swipe (X1, Y1 -> X2, Y2)", padx=8, pady=4)
        swipe_box.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=4)
        self.entry_sx1 = tk.Entry(swipe_box, width=5)
        self.entry_sx1.insert(0, "360")
        self.entry_sx1.pack(side=tk.LEFT, padx=1)
        self.entry_sy1 = tk.Entry(swipe_box, width=5)
        self.entry_sy1.insert(0, "900")
        self.entry_sy1.pack(side=tk.LEFT, padx=1)
        tk.Label(swipe_box, text="➔").pack(side=tk.LEFT)
        self.entry_sx2 = tk.Entry(swipe_box, width=5)
        self.entry_sx2.insert(0, "360")
        self.entry_sx2.pack(side=tk.LEFT, padx=1)
        self.entry_sy2 = tk.Entry(swipe_box, width=5)
        self.entry_sy2.insert(0, "300")
        self.entry_sy2.pack(side=tk.LEFT, padx=1)
        btn_swipe = tk.Button(swipe_box, text="👆 Swipe All", font=("Segoe UI", 9, "bold"), bg="#16a085", fg="white", relief=tk.FLAT, padx=6, command=self.send_swipe)
        btn_swipe.pack(side=tk.RIGHT, padx=4)

        # 3. Type Text
        type_frame = tk.Frame(actions_frame)
        type_frame.pack(fill=tk.X, pady=4)
        tk.Label(type_frame, text="Type Text:", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=4)
        self.entry_text = tk.Entry(type_frame)
        self.entry_text.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=4)
        self.entry_text.bind("<Return>", lambda e: self.send_text())
        btn_send_text = tk.Button(type_frame, text="⌨ Send to All", font=("Segoe UI", 9, "bold"), bg="#8e44ad", fg="white", relief=tk.FLAT, padx=10, command=self.send_text)
        btn_send_text.pack(side=tk.RIGHT, padx=4)

        # 4. Open App / URL / Shell
        misc_frame = tk.Frame(actions_frame)
        misc_frame.pack(fill=tk.X, pady=4)

        # App launcher
        tk.Label(misc_frame, text="App/URL:").pack(side=tk.LEFT, padx=2)
        self.entry_app = tk.Entry(misc_frame, width=24)
        self.entry_app.insert(0, "com.android.chrome")
        self.entry_app.pack(side=tk.LEFT, padx=4)
        btn_open = tk.Button(misc_frame, text="🚀 Open", font=("Segoe UI", 9, "bold"), bg="#d35400", fg="white", relief=tk.FLAT, padx=6, command=self.send_open)
        btn_open.pack(side=tk.LEFT, padx=2)

        # Shell command
        tk.Label(misc_frame, text="ADB Shell:").pack(side=tk.LEFT, padx=4)
        self.entry_shell = tk.Entry(misc_frame)
        self.entry_shell.insert(0, "getprop ro.product.model")
        self.entry_shell.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=4)
        self.entry_shell.bind("<Return>", lambda e: self.send_shell())
        btn_shell = tk.Button(misc_frame, text="▶ Run", font=("Segoe UI", 9, "bold"), bg="#2c3e50", fg="white", relief=tk.FLAT, padx=8, command=self.send_shell)
        btn_shell.pack(side=tk.RIGHT, padx=2)

        # Screenshot & APK install buttons row
        row_tools = tk.Frame(actions_frame)
        row_tools.pack(fill=tk.X, pady=6)

        btn_shot = tk.Button(row_tools, text="📸 Capture 5-Phone Screenshot Grid", font=("Segoe UI", 9, "bold"), bg="#27ae60", fg="white", relief=tk.FLAT, padx=10, pady=4, command=self.capture_grid)
        btn_shot.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=4)

        btn_apk = tk.Button(row_tools, text="📦 Install APK on All Phones", font=("Segoe UI", 9, "bold"), bg="#34495e", fg="white", relief=tk.FLAT, padx=10, pady=4, command=self.install_apk_dialog)
        btn_apk.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=4)

        # Output / Log Section
        log_frame = tk.LabelFrame(self.root, text="Simultaneous Execution Logs", font=("Segoe UI", 10, "bold"), padx=10, pady=6)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=8)

        self.txt_log = tk.Text(log_frame, font=("Consolas", 9), bg="#1e1e1e", fg="#d4d4d4", wrap=tk.WORD)
        self.txt_log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.txt_log.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt_log.config(yscrollcommand=scrollbar.set)

    def log(self, msg):
        self.txt_log.insert(tk.END, msg + "\n")
        self.txt_log.see(tk.END)

    def refresh_status(self):
        def worker():
            online = self.controller.get_online_devices()
            for p in PHONES:
                name = p["name"]
                serial = p["serial"]
                if serial in online:
                    self.phone_status_vars[name].set("🟢 ONLINE")
                else:
                    self.phone_status_vars[name].set("🔴 OFFLINE")
            self.root.after(0, lambda: self.log(f"[Status Checked] {len(online)}/5 phones online."))

        threading.Thread(target=worker, daemon=True).start()

    def send_key(self, key_name):
        threading.Thread(target=lambda: self._exec_and_log(lambda: self.controller.key(key_name)), daemon=True).start()

    def send_tap(self):
        try:
            x = int(self.entry_tap_x.get().strip())
            y = int(self.entry_tap_y.get().strip())
            threading.Thread(target=lambda: self._exec_and_log(lambda: self.controller.tap(x, y)), daemon=True).start()
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter valid numeric coordinates for X and Y.")

    def send_swipe(self):
        try:
            x1 = int(self.entry_sx1.get().strip())
            y1 = int(self.entry_sy1.get().strip())
            x2 = int(self.entry_sx2.get().strip())
            y2 = int(self.entry_sy2.get().strip())
            threading.Thread(target=lambda: self._exec_and_log(lambda: self.controller.swipe(x1, y1, x2, y2)), daemon=True).start()
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter valid numeric coordinates for swipe.")

    def send_text(self):
        txt = self.entry_text.get().strip()
        if txt:
            threading.Thread(target=lambda: self._exec_and_log(lambda: self.controller.type_text(txt)), daemon=True).start()
            self.entry_text.delete(0, tk.END)

    def send_open(self):
        target = self.entry_app.get().strip()
        if not target:
            return
        if target.startswith("http://") or target.startswith("https://"):
            threading.Thread(target=lambda: self._exec_and_log(lambda: self.controller.open_url(target)), daemon=True).start()
        else:
            threading.Thread(target=lambda: self._exec_and_log(lambda: self.controller.launch_app(target)), daemon=True).start()

    def send_shell(self):
        cmd = self.entry_shell.get().strip()
        if cmd:
            threading.Thread(target=lambda: self._exec_and_log(lambda: self.controller.shell(cmd)), daemon=True).start()

    def capture_grid(self):
        def worker():
            self.log("[Screenshot] Capturing 5-phone grid...")
            self.controller.capture_grid_screenshot("king_grid_preview.png")
            out_path = os.path.join(os.path.dirname(__file__), "king_grid_preview.png")
            if os.path.exists(out_path):
                self.log(f"[Screenshot Ready] Saved to: {out_path}")
                os.startfile(out_path)

        threading.Thread(target=worker, daemon=True).start()

    def install_apk_dialog(self):
        path = filedialog.askopenfilename(title="Select APK to install on all 5 phones", filetypes=[("APK Files", "*.apk")])
        if path:
            threading.Thread(target=lambda: self._exec_and_log(lambda: self.controller.install_apk(path)), daemon=True).start()

    def start_all_phones(self):
        script = os.path.join(os.path.dirname(__file__), "king_launcher.py")
        subprocess.Popen([sys.executable, script], creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0)
        self.log("[Launched] Started king_launcher.py in a separate console window.")

    def stop_all_phones(self):
        script = os.path.join(os.path.dirname(__file__), "king_stop.py")
        threading.Thread(target=lambda: self._exec_process(script), daemon=True).start()

    def tile_windows(self):
        from king_launcher import tile_emulator_windows
        threading.Thread(target=tile_emulator_windows, daemon=True).start()
        self.log("[Window Tiling] Arranging phone windows side-by-side.")

    def _exec_and_log(self, fn):
        res = fn()
        if isinstance(res, dict):
            for name, info in sorted(res.items()):
                st = "SUCCESS" if info["success"] else "FAIL"
                out = f" | {info['output']}" if info['output'] else ""
                self.log(f"  [{name}] {st}{out}")

    def _exec_process(self, script_path):
        res = subprocess.run([sys.executable, script_path], capture_output=True, text=True)
        self.log(res.stdout)
        self.refresh_status()

if __name__ == "__main__":
    root = tk.Tk()
    app = KingMultiGUI(root)
    root.mainloop()

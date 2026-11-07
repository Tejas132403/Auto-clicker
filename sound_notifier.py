import sys
import time
import atexit
import threading
import ctypes

# Ensure UTF-8 console output on Windows
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def safe_print(msg):
    try:
        print(msg, flush=True)
    except Exception:
        try:
            print(msg.encode('ascii', errors='replace').decode('ascii'), flush=True)
        except Exception:
            pass

_SOUND_PLAYED = False
_POPUP_TITLE = "Auto Clicker Bot Notification"

def _play_pattern(sound_type="complete"):
    """Plays a single melody or alert tone sequence."""
    try:
        import winsound
        if sound_type == "complete":
            try:
                winsound.MessageBeep(winsound.MB_OK)
            except Exception:
                pass
            tones = [(523, 140), (659, 140), (784, 140), (1046, 380)]
        elif sound_type == "pause":
            try:
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            except Exception:
                pass
            tones = [(988, 180), (988, 180), (1318, 320)]
        elif sound_type == "error":
            try:
                winsound.MessageBeep(winsound.MB_ICONHAND)
            except Exception:
                pass
            tones = [(440, 250), (330, 400)]
        else: # "stop"
            try:
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
            except Exception:
                pass
            tones = [(1000, 180), (800, 180), (600, 320)]

        for freq, dur in tones:
            winsound.Beep(freq, dur)
            time.sleep(0.04)
    except Exception:
        try:
            print("\a", flush=True)
        except Exception:
            pass

def play_until_stopped(sound_type="complete", message="Script has stopped."):
    """
    Plays the notification sound continuously in a loop UNTIL the user stops it.
    Can be stopped by:
      - Pressing ENTER, SPACE, or ANY KEY in the terminal window
      - Pressing Ctrl+C
      - Clicking [OK] on the on-screen popup alert box
    """
    global _SOUND_PLAYED
    _SOUND_PLAYED = True

    safe_print("\n" + "=" * 65)
    safe_print(f"🔔 [SOUND ALARM ACTIVE] {message}")
    safe_print("👉 Press [ENTER] or ANY KEY in this terminal (or click OK on the popup) to STOP the sound.")
    safe_print("=" * 65 + "\n")

    stop_event = threading.Event()

    # 1. Thread for terminal keyboard input (Enter / Any key)
    def terminal_listener():
        try:
            import msvcrt
            while not stop_event.is_set():
                if msvcrt.kbhit():
                    try:
                        msvcrt.getch()
                    except Exception:
                        pass
                    stop_event.set()
                    return
                time.sleep(0.05)
        except Exception:
            try:
                sys.stdin.readline()
                stop_event.set()
            except Exception:
                pass

    t_term = threading.Thread(target=terminal_listener, daemon=True)
    t_term.start()

    # 2. Thread for on-screen Windows Dialog Popup
    def popup_listener():
        try:
            user32 = ctypes.windll.user32
            popup_text = f"Bot Notification:\n\n{message}\n\nClick [OK] to stop the sound."
            # MB_OK (0x0) | MB_ICONINFORMATION (0x40) | MB_TOPMOST (0x40000)
            user32.MessageBoxW(0, popup_text, _POPUP_TITLE, 0x0 | 0x40 | 0x40000)
            stop_event.set()
        except Exception:
            pass

    t_popup = threading.Thread(target=popup_listener, daemon=True)
    t_popup.start()

    # 3. Sound loop - repeats until user silences it
    try:
        while not stop_event.is_set():
            _play_pattern(sound_type)
            # Pause between sound repetitions (1.2 seconds, checking for stop)
            for _ in range(12):
                if stop_event.is_set():
                    break
                time.sleep(0.1)
    except KeyboardInterrupt:
        stop_event.set()
    finally:
        stop_event.set()
        # Automatically close popup window if terminal key was pressed instead
        try:
            user32 = ctypes.windll.user32
            hwnd = user32.FindWindowW(None, _POPUP_TITLE)
            if hwnd:
                user32.PostMessageW(hwnd, 0x0010, 0, 0) # WM_CLOSE
        except Exception:
            pass
        safe_print("🔇 Sound stopped by user.\n")

def prompt_task_complete(message="Daily limit reached or current task completed!", auto_continue=False):
    """
    Alerts the user that a task has completed or daily limit was reached,
    and provides an interactive option to:
      1) CONTINUE running so other tasks can also complete
      2) STOP the script

    Options:
      - Windows Dialog: [Yes] to Continue, [No] to Stop
      - Terminal Key:   [C] or [ENTER] to Continue, [Q] or [S] to Stop
      - Config flag:    If auto_continue=True, chimes and returns True immediately.

    Returns:
      True  -> Continue running (script does NOT stop)
      False -> Stop script
    """
    global _SOUND_PLAYED
    _SOUND_PLAYED = True

    if auto_continue:
        safe_print("\n" + "=" * 65)
        safe_print(f"🔔 [TASK COMPLETE - AUTO-CONTINUE] {message}")
        safe_print("⏩ auto_continue_on_limit enabled -> Continuing so other tasks can complete...")
        safe_print("=" * 65 + "\n")
        _play_pattern("complete")
        return True

    safe_print("\n" + "=" * 65)
    safe_print(f"🔔 [TASK COMPLETE / DAILY LIMIT REACHED]")
    safe_print(f"   {message}")
    safe_print("👉 OPTION 1: Press [C] or [ENTER] (or click [Yes]) to CONTINUE for other tasks")
    safe_print("👉 OPTION 2: Press [Q] or [S]     (or click [No])  to STOP the script")
    safe_print("=" * 65 + "\n")

    stop_event = threading.Event()
    user_choice = {"continue": True}  # Default to continue if unassigned

    # 1. Thread for terminal keyboard input
    def terminal_listener():
        try:
            import msvcrt
            while not stop_event.is_set():
                if msvcrt.kbhit():
                    try:
                        ch = msvcrt.getch()
                        if isinstance(ch, bytes):
                            char_str = ch.decode('latin1', errors='ignore').lower()
                        else:
                            char_str = str(ch).lower()

                        if char_str in ['\r', '\n', 'c', ' ']:
                            user_choice["continue"] = True
                            stop_event.set()
                            return
                        elif char_str in ['q', 's', '\x1b']:
                            user_choice["continue"] = False
                            stop_event.set()
                            return
                    except Exception:
                        pass
                time.sleep(0.05)
        except Exception:
            pass

    t_term = threading.Thread(target=terminal_listener, daemon=True)
    t_term.start()

    # 2. Thread for on-screen Windows Dialog Popup with [Yes] and [No]
    def popup_listener():
        try:
            user32 = ctypes.windll.user32
            popup_text = (
                f"{message}\n\n"
                f"Do you want to CONTINUE running so other tasks can also complete?\n\n"
                f"👉 Click [Yes] = CONTINUE running (switch to other tasks on phone)\n"
                f"👉 Click [No]  = STOP the script"
            )
            # MB_YESNO (0x4) | MB_ICONQUESTION (0x20) | MB_TOPMOST (0x40000) | MB_SETFOREGROUND (0x10000)
            res = user32.MessageBoxW(0, popup_text, _POPUP_TITLE, 0x00000004 | 0x00000020 | 0x00040000 | 0x00010000)
            # IDYES = 6, IDNO = 7
            if res == 6:
                user_choice["continue"] = True
            else:
                user_choice["continue"] = False
            stop_event.set()
        except Exception:
            pass

    t_popup = threading.Thread(target=popup_listener, daemon=True)
    t_popup.start()

    # 3. Sound loop - repeats until user makes a selection
    try:
        while not stop_event.is_set():
            _play_pattern("complete")
            for _ in range(15):
                if stop_event.is_set():
                    break
                time.sleep(0.1)
    except KeyboardInterrupt:
        user_choice["continue"] = False
        stop_event.set()
    finally:
        stop_event.set()
        # Automatically close popup window if terminal key was used
        try:
            user32 = ctypes.windll.user32
            hwnd = user32.FindWindowW(None, _POPUP_TITLE)
            if hwnd:
                user32.PostMessageW(hwnd, 0x0010, 0, 0) # WM_CLOSE
        except Exception:
            pass

    should_continue = bool(user_choice["continue"])
    if should_continue:
        safe_print("⏩ Option selected: CONTINUE running for other tasks.\n")
    else:
        safe_print("🛑 Option selected: STOP script.\n")

    return should_continue

def notify_task_complete(message="All tasks completed successfully!", allow_continue=True, auto_continue=False):
    """
    Notifies that a task is complete. If allow_continue=True, prompts user
    with an option to continue so other tasks can also complete.
    """
    if allow_continue:
        return prompt_task_complete(message, auto_continue=auto_continue)
    else:
        play_until_stopped("complete", message)
        return False

def notify_script_stopped(message="Script has stopped."):
    play_until_stopped("stop", message)

def notify_script_paused(message="Script paused for user action."):
    play_until_stopped("pause", message)

def notify_error(message="Script stopped due to error."):
    play_until_stopped("error", message)

def play_sound(sound_type="complete"):
    """Plays sound continuously until stopped (for backwards compatibility)."""
    play_until_stopped(sound_type, "Script finished or stopped.")

def _on_exit_cleanup():
    global _SOUND_PLAYED
    if not _SOUND_PLAYED:
        play_until_stopped("stop", "Script has exited.")

def register_exit_sound():
    """Ensures a notification sound plays in a loop until stopped whenever the script terminates."""
    atexit.register(_on_exit_cleanup)

if __name__ == "__main__":
    print("Testing Sound Notifier Loop Mode...")
    print("Starting sound alarm. Press ENTER, any key, or click OK on the popup to test stopping it.")
    notify_task_complete("Testing continuous sound alarm until stopped.")

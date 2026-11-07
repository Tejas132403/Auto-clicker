# This file contains the stay-in-app guard code as a raw string
# It will be read as bytes and inserted into free_ai_bot.py

guard_code = r'''
    # [STAY-IN-APP GUARD] If we left the quiz app (Play Store, Home, etc.), force return.
    _cur_pkg = get_current_app_package()
    _tgt_pkg = QUIZ_STATE.get("target_app_package") or "com.shake.master"
    if _cur_pkg and _cur_pkg != _tgt_pkg:
        msg = f"\n??? [STAY-IN-APP] Currently in '{_cur_pkg}' (target: '{_tgt_pkg}'). Forcing return to quiz app..."
        print(msg, flush=True)
        for _bi in range(8):
            run_adb(["shell", "input", "keyevent", "4"])
            time.sleep(0.4)
            _cp = get_current_app_package()
            if _cp == _tgt_pkg:
                print(f"??? [STAY-IN-APP] Returned to target after {_bi+1} back presses.", flush=True)
                break
        _cp2 = get_current_app_package()
        if _cp2 != _tgt_pkg:
            print(f"??? [STAY-IN-APP] Still not in target ('{_cp2}'). Home + launch...", flush=True)
            run_adb(["shell", "input", "keyevent", "3"])
            time.sleep(1.0)
            run_adb(["shell", "monkey", "-p", _tgt_pkg, "-c", "android.intent.category.LAUNCHER", "1"])
            time.sleep(3.0)
            _cp3 = get_current_app_package()
            if _cp3 == _tgt_pkg:
                print("??? [STAY-IN-APP] Launched target app.", flush=True)
            else:
                print(f"??? [STAY-IN-APP] WARNING: still not in target ('{_cp3}'). Retrying...", flush=True)
                for _ri in range(3):
                    run_adb(["shell", "input", "keyevent", "3"])
                    time.sleep(0.5)
                    run_adb(["shell", "monkey", "-p", _tgt_pkg, "-c", "android.intent.category.LAUNCHER", "1"])
                    time.sleep(3.0)
                    _cp4 = get_current_app_package()
                    if _cp4 == _tgt_pkg:
                        print(f"??? [STAY-IN-APP] Retry {_ri+1}: Returned to target.", flush=True)
                        break
        elements = get_ui_elements()
        all_text = " ".join([e["text"].lower() for e in elements])
'''

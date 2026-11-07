# 💻 Mobile Automation Controller from Laptop 📱

Automate and control your Android mobile app directly from your laptop.
All customization, scripts, AI web searching, and logic run on your laptop — sending rapid touch events to your phone via ADB!

---

## 🚀 Quick Setup & Status

Your phone (`10BE5D10X50007U`) is **connected and authorized**!

To check status anytime:
```powershell
uv run python mobile_controller.py status
```

---

## 🛠️ How to Use

### 1. See Mobile Screen & Elements
Captures a screenshot of your phone (`mobile_screen.png`) and lists every text and button with exact coordinates:
```powershell
uv run python mobile_controller.py see
```

### 2. Click Anywhere by Coordinates
Taps at specific (X, Y) pixel coordinates on your phone:
```powershell
uv run python mobile_controller.py click 539 1761
```

### 3. Click Any Button or App by Name
Automatically finds the text/button anywhere on your phone screen and clicks its center:
```powershell
uv run python mobile_controller.py click-text "Autox.js v6"
uv run python mobile_controller.py click-text "Submit"
uv run python mobile_controller.py click-text "Add"
```

### 4. Start Full Auto Watcher (Quiz Solver + Buttons)
Continuously monitors your phone screen:
- **Auto Quiz Solver**: Detects `?` or `quiz`, grabs the question + options (A, B, C, D), searches Google/DuckDuckGo from your laptop in <1s, and clicks the correct answer on your phone!
- **Auto Button Clicker**: Clicks action buttons (`Submit`, `Add`, `Next`, `Claim`, etc.) the instant they appear.
```powershell
uv run python mobile_controller.py run
```

---

## 🤖 5. Free Autonomous AI Vision Bot (`free_ai_bot.py`)
Uses your Gemini API Key (`AQ.Ab8RN...`) to visually inspect your phone screen, reason, and click:
- **Zero Dependencies**: No extra pip packages or `--with pillow` required! Runs 100% out of the box using Windows native image processing.
- **Cost**: **$0.00 (100% Free)**.

To start:
```powershell
uv run python free_ai_bot.py
```

### 🔔 6. Complete 1-Quiz Cycle & Stalled Task Detection
The bot follows the complete quiz task flow:
1. **Choose Answer**: Finds the correct answer and taps the option (A, B, C, or D).
2. **Tap Add Bonus**: When the bonus coins popup appears, clicks **"Add Bonus"**.
3. **Wait 25 Seconds for Ad**: Waits full 25 seconds for the reward advertisement or timer to finish.
4. **Dismiss Ad Overlay**: Closes any remaining ad overlay (`X` button).
5. **Read Screen & Verify Counter**:
   - If counter advanced (`16/20` ➔ `17/20`): Full quiz cycle complete! Proceeds smoothly to the next question.
   - If counter is **STILL the same** (e.g. still `16/20` after the full 25s cycle) or stuck > 35s:
     - 📱 **Mobile Phone**: Max volume + phone vibration + loud alarm ringtone!
     - 💻 **Laptop**: Repeated alert beeps (`winsound`).
     - 🛑 **Bot Pauses**: Leaves the phone completely free for you to do any required manual app install.
### 🎬 7. Watch Video Task Flow (Auto 'Play Video' + 25s Wait + Repeat Alert)
For the Watch Video task (e.g. `0/15`, `1/15` ... `15/15`):
1. **Detect & Tap 'Play Video'**: Automatically records current counter (e.g. `1/15`) and clicks **"Play Video"**.
2. **Click & Wait 25 Seconds**: Waits the full **25 seconds** for the video ad to finish.
3. **Dismiss Ad Overlay**: Automatically closes any ad cross (`X`) or dismiss button.
4. **Auto Claim Bonus**: Automatically clicks any "Add Bonus" or "Claim" popup after the video.
5. **Screen Read & Verification**:
   - If counter advanced (`1/15` ➔ `2/15`): Plays the next video in loop!
   - If counter **REPEATS / STUCK** (still `1/15` after watching 25s video):
     - 📱 **Mobile Phone**: Rings loud alarm sound + vibrates + sets volume to max.
     - 💻 **Laptop**: Continuous beep alerts (`winsound`).
     - 🛑 **Bot Pauses**: Lets you perform any required manual task or app installation. Restart anytime with `uv run python free_ai_bot.py`.

### 🔄 8. Option to Continue on Task Complete / Daily Limit
When a task reaches its daily limit or finishes (e.g. `20/20` quiz complete or "Daily limit reached"):
- 🪟 **Interactive Popup**: A dialog pops up asking:
  - **Click [Yes]**: **CONTINUE** running so you can switch to other tasks (Spin, Scratch, Video, etc.) and complete them without restarting the script!
  - **Click [No]**: **STOP** the script cleanly.
- 💻 **Terminal Controls**:
  - Press **[C]** or **[ENTER]**: Continue running for other tasks.
  - Press **[Q]** or **[S]**: Stop script.
- ⚡ **Auto-Continue Mode**: If you want the bot to **always keep running automatically** without popping up or waiting for input, set `"auto_continue_on_limit": true` in [`ai_config.json`](file:///d:/KING%20PROJECT/Auto%20clicker/ai_config.json).

---

## ⚙️ Easy Customization (`mobile_config.json`)

Edit [mobile_config.json](file:///d:/KING%20PROJECT/Auto%20clicker/mobile_config.json) to tweak settings without touching any code:

```json
{
  "triggerKeywords": ["?", "quiz", "quize", "Question"],
  "actionButtons": ["Submit", "Add", "Next", "Continue", "Confirm", "Claim"],
  "pollIntervalSeconds": 1.0,
  "autoAnswerQuiz": true,
  "optionsPrefixes": ["A", "B", "C", "D"],
  "searchBackend": "duckduckgo"
}
```

---

## 🪟 Optional: Mirror Phone Screen on Laptop (`scrcpy`)
You have `scrcpy` installed at `D:\mirzapur\scrcpy-win64-v3.2\scrcpy-win64-v3.2\scrcpy.exe`.
To see your live phone screen on your laptop in high-definition:
```powershell
& "D:\mirzapur\scrcpy-win64-v3.2\scrcpy-win64-v3.2\scrcpy.exe"
```

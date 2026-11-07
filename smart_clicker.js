/**
 * =========================================================================
 * AUTOX.JS SMART AI CLICKER & SCREEN WATCHER
 * =========================================================================
 * - Works completely standalone on Android (NO PC, NO Developer Options)
 * - Uses Accessibility Service + On-Device AI OCR (PaddleOCR)
 * - Includes a Floating On-Screen Controller (Start, Pause, Exit, Live Status)
 * - Supports Reactive Keyword Triggers and Multi-Step Task Sequences
 * =========================================================================
 */

// Load or define configuration
var Config = (typeof AppConfig !== 'undefined') ? AppConfig : {
    settings: {
        scanIntervalMs: 600,
        defaultCooldownMs: 2500,
        useOcr: true,
        ocrConfidenceThreshold: 0.6
    },
    reactiveTriggers: [
        { text: "Next", action: "click", cooldownMs: 2000, exactMatch: false },
        { text: "Continue", action: "click", cooldownMs: 2000, exactMatch: false },
        { text: "Submit", action: "click", cooldownMs: 3000, exactMatch: false },
        { text: "Claim", action: "click", cooldownMs: 4000, exactMatch: false },
        { text: "Confirm", action: "click", cooldownMs: 2500, exactMatch: false },
        { text: "Start", action: "click", cooldownMs: 3000, exactMatch: false },
        { text: "Accept", action: "click", cooldownMs: 3000, exactMatch: false }
    ],
    sequentialWorkflow: {
        enabled: false,
        loopWorkflow: true,
        steps: []
    }
};

// State variables
var isRunning = false;
var isPaused = true;
var workerThread = null;
var cooldownMap = {}; // Tracks last clicked timestamp for each keyword
var currentWorkflowStep = 0;

// Initialize permissions and floating window
main();

function main() {
    toastLog("Initializing Smart Watcher...");

    // 1. Check & request Accessibility Service (Official Android feature, no Dev Options needed)
    ensureAccessibility();

    // 2. Request Screen Capture permission if OCR is enabled
    if (Config.settings.useOcr) {
        requestScreenCapturePermission();
    }

    // 3. Create Floating Control Window
    setupFloatingUI();

    toastLog("Smart Clicker is Ready! Use the floating widget.");
}

/**
 * Ensures Accessibility Service is enabled
 */
function ensureAccessibility() {
    if (auto.service == null) {
        toast("Please enable Accessibility Service for AutoX.js");
        app.startActivity({
            action: "android.settings.ACCESSIBILITY_SETTINGS"
        });
        auto.waitFor();
        toastLog("Accessibility Service Enabled!");
    }
}

/**
 * Requests Screen Projection permission for on-device OCR
 */
function requestScreenCapturePermission() {
    threads.start(function () {
        if (!requestScreenCapture(false)) {
            toastLog("Screen capture permission was not granted. Native UI text only.");
            Config.settings.useOcr = false;
        } else {
            toastLog("Screen capture granted for AI OCR!");
        }
    });
}

/**
 * Creates a movable floating overlay with controls and status indicator
 */
function setupFloatingUI() {
    var window = floaty.window(
        <frame id="mainFrame" bg="#CC1E1E2E" padding="8" cornerRadius="16">
            <vertical gravity="center">
                <text id="title" text="🤖 AI Clicker" textSize="14sp" textColor="#FFFFFF" textStyle="bold" gravity="center" />
                <text id="status" text="Status: PAUSED" textSize="11sp" textColor="#FFA500" gravity="center" marginTop="2" />
                <text id="lastAction" text="Idle" textSize="10sp" textColor="#A0A0A0" gravity="center" marginTop="1" />
                
                <horizontal gravity="center" marginTop="6">
                    <button id="btnToggle" text="START" textSize="11sp" w="58" h="32" bg="#10B981" textColor="#FFFFFF" margin="2" />
                    <button id="btnClose" text="✕" textSize="11sp" w="32" h="32" bg="#EF4444" textColor="#FFFFFF" margin="2" />
                </horizontal>
            </vertical>
        </frame>
    );

    // Make floating window draggable
    var x = 0, y = 0;
    var windowX, windowY;
    var downTime;

    window.mainFrame.setOnTouchListener(function (view, event) {
        switch (event.getAction()) {
            case event.ACTION_DOWN:
                x = event.getRawX();
                y = event.getRawY();
                windowX = window.getX();
                windowY = window.getY();
                downTime = new Date().getTime();
                return true;
            case event.ACTION_MOVE:
                window.setPosition(windowX + (event.getRawX() - x), windowY + (event.getRawY() - y));
                return true;
            case event.ACTION_UP:
                return true;
        }
        return false;
    });

    // Toggle Start / Pause
    window.btnToggle.setOnClickListener(function () {
        if (isPaused) {
            startEngine(window);
        } else {
            pauseEngine(window);
        }
    });

    // Close script
    window.btnClose.setOnClickListener(function () {
        stopEngine();
        window.close();
        toastLog("Smart Clicker Stopped.");
        exit();
    });
}

function startEngine(uiWindow) {
    isPaused = false;
    ui.run(function () {
        uiWindow.status.setText("Status: ACTIVE");
        uiWindow.status.setTextColor(colors.parseColor("#10B981"));
        uiWindow.btnToggle.setText("PAUSE");
        uiWindow.btnToggle.attr("bg", "#F59E0B");
    });

    toast("Watcher Started");

    if (workerThread == null || !workerThread.isAlive()) {
        workerThread = threads.start(function () {
            engineLoop(uiWindow);
        });
    }
}

function pauseEngine(uiWindow) {
    isPaused = true;
    ui.run(function () {
        uiWindow.status.setText("Status: PAUSED");
        uiWindow.status.setTextColor(colors.parseColor("#FFA500"));
        uiWindow.btnToggle.setText("START");
        uiWindow.btnToggle.attr("bg", "#10B981");
    });
    toast("Watcher Paused");
}

function stopEngine() {
    isPaused = true;
    if (workerThread != null && workerThread.isAlive()) {
        workerThread.interrupt();
    }
}

/**
 * Core scanning loop
 */
function engineLoop(uiWindow) {
    while (true) {
        if (!isPaused) {
            try {
                if (Config.sequentialWorkflow && Config.sequentialWorkflow.enabled) {
                    processSequentialWorkflow(uiWindow);
                } else {
                    processReactiveTriggers(uiWindow);
                }
            } catch (e) {
                log("Error in scanner loop: " + e);
            }
        }
        sleep(Config.settings.scanIntervalMs);
    }
}

/**
 * Mode 1: Reactive Trigger Scanner
 * Continuously checks for any instructed text appearing on screen
 */
function processReactiveTriggers(uiWindow) {
    var triggers = Config.reactiveTriggers;
    var now = new Date().getTime();

    for (var i = 0; i < triggers.length; i++) {
        var item = triggers[i];
        var keyword = item.text;
        var cooldown = item.cooldownMs || Config.settings.defaultCooldownMs;

        // Check if item is in cooldown
        if (cooldownMap[keyword] && (now - cooldownMap[keyword] < cooldown)) {
            continue;
        }

        // Try detecting and clicking target
        var clicked = attemptFindAndClick(item, uiWindow);
        if (clicked) {
            cooldownMap[keyword] = now;
            break; // Pause briefly after a click
        }
    }
}

/**
 * Mode 2: Sequential Step-by-Step Task Workflow
 */
function processSequentialWorkflow(uiWindow) {
    var steps = Config.sequentialWorkflow.steps;
    if (!steps || steps.length === 0) return;

    if (currentWorkflowStep >= steps.length) {
        if (Config.sequentialWorkflow.loopWorkflow) {
            currentWorkflowStep = 0;
        } else {
            pauseEngine(uiWindow);
            return;
        }
    }

    var step = steps[currentWorkflowStep];
    ui.run(function () {
        uiWindow.lastAction.setText("Waiting: " + step.waitForText);
    });

    var dummyTrigger = {
        text: step.waitForText,
        action: step.action || "click",
        exactMatch: false
    };

    var clicked = attemptFindAndClick(dummyTrigger, uiWindow);
    if (clicked) {
        currentWorkflowStep++;
        if (step.delayAfterMs) {
            sleep(step.delayAfterMs);
        }
    }
}

/**
 * Dual Detection Engine:
 * Level 1: Native Accessibility Nodes (instantaneous)
 * Level 2: On-Device AI OCR on screen capture
 */
function attemptFindAndClick(trigger, uiWindow) {
    var keyword = trigger.text;

    // --- LEVEL 1: Check Native Accessibility Tree ---
    var nativeNode = findNativeNode(keyword, trigger.exactMatch);
    if (nativeNode != null) {
        var bounds = nativeNode.bounds();
        var cx = bounds.centerX();
        var cy = bounds.centerY();

        executeTap(cx, cy, keyword, "Native UI", uiWindow);
        return true;
    }

    // --- LEVEL 2: On-Device AI OCR Fallback (for Canvas / Games) ---
    if (Config.settings.useOcr) {
        var ocrMatch = findByOcr(keyword);
        if (ocrMatch != null) {
            executeTap(ocrMatch.x, ocrMatch.y, keyword, "AI OCR", uiWindow);
            return true;
        }
    }

    return false;
}

/**
 * Searches native Android UI Accessibility Hierarchy
 */
function findNativeNode(keyword, exactMatch) {
    try {
        var selector = exactMatch ? text(keyword) : textContains(keyword);
        if (selector.exists()) {
            return selector.findOnce();
        }

        // Also check content descriptions (common on icon buttons)
        var descSelector = exactMatch ? desc(keyword) : descContains(keyword);
        if (descSelector.exists()) {
            return descSelector.findOnce();
        }
    } catch (e) {
        // Ignored
    }
    return null;
}

/**
 * Captures screen and runs local AI OCR (PaddleOCR in AutoX.js)
 */
function findByOcr(keyword) {
    try {
        var img = captureScreen();
        if (!img) return null;

        // AutoX.js v6 supports paddle.ocr or ocr.detect
        var ocrResults = null;
        if (typeof paddle !== 'undefined' && paddle.ocr) {
            ocrResults = paddle.ocr(img);
        } else if (typeof ocr !== 'undefined' && ocr.detect) {
            ocrResults = ocr.detect(img);
        }

        if (!ocrResults || ocrResults.length === 0) {
            return null;
        }

        var lowerKey = keyword.toLowerCase();

        for (var i = 0; i < ocrResults.length; i++) {
            var item = ocrResults[i];
            var detectedText = (item.text || "").toLowerCase();

            if (detectedText.indexOf(lowerKey) !== -1) {
                var bounds = item.bounds;
                if (bounds) {
                    return {
                        x: bounds.centerX ? bounds.centerX() : (bounds.left + bounds.right) / 2,
                        y: bounds.centerY ? bounds.centerY() : (bounds.top + bounds.bottom) / 2
                    };
                }
            }
        }
    } catch (err) {
        // OCR fallback error
    }
    return null;
}

/**
 * Performs click and updates floating status
 */
function executeTap(x, y, keyword, source, uiWindow) {
    // Perform standard accessibility tap
    click(x, y);

    ui.run(function () {
        uiWindow.lastAction.setText("Clicked: " + keyword + " (" + source + ")");
    });

    log("[Clicked] " + keyword + " at (" + Math.round(x) + ", " + Math.round(y) + ") via " + source);
}

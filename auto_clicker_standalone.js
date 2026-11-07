/**
 * =========================================================================
 * ALL-IN-ONE SMART AI CLICKER & SCREEN WATCHER (AUTOX.JS)
 * =========================================================================
 * Copy and paste this ENTIRE code into a new script in AutoX.js on your phone.
 * No PC required. Developer options & USB debugging stay completely OFF.
 * =========================================================================
 */

// ==========================================
// 1. CONFIGURATION: EDIT YOUR KEYWORDS HERE
// ==========================================
var AppConfig = {
    settings: {
        scanIntervalMs: 600,       // Time between screen scans in ms (600ms = smooth & battery friendly)
        defaultCooldownMs: 2500,   // Delay before re-clicking the same text (prevents double taps)
        useOcr: true,              // Use On-Device AI OCR for canvas, Unity, or graphic text
        ocrConfidenceThreshold: 0.6
    },

    // A. Reactive Triggers: If ANY of these appear, click immediately
    reactiveTriggers: [
        { text: "Next", action: "click", cooldownMs: 2000, exactMatch: false },
        { text: "Continue", action: "click", cooldownMs: 2000, exactMatch: false },
        { text: "Submit", action: "click", cooldownMs: 3000, exactMatch: false },
        { text: "Claim", action: "click", cooldownMs: 4000, exactMatch: false },
        { text: "Confirm", action: "click", cooldownMs: 2500, exactMatch: false },
        { text: "Start", action: "click", cooldownMs: 3000, exactMatch: false },
        { text: "Accept", action: "click", cooldownMs: 3000, exactMatch: false }
    ],

    // B. Sequential Workflow: (Optional) Step-by-step task
    // Set enabled: true if you want step 1 -> step 2 -> step 3
    sequentialWorkflow: {
        enabled: false,
        loopWorkflow: true,
        steps: [
            { stepName: "Step 1", waitForText: "Start", action: "click", delayAfterMs: 1500 },
            { stepName: "Step 2", waitForText: "Option A", action: "click", delayAfterMs: 1000 },
            { stepName: "Step 3", waitForText: "Submit", action: "click", delayAfterMs: 2000 }
        ]
    }
};

// ==========================================
// 2. ENGINE & CORE STATE
// ==========================================
var isPaused = true;
var workerThread = null;
var cooldownMap = {};
var currentWorkflowStep = 0;

main();

function main() {
    toastLog("Initializing Smart Watcher...");

    // Check accessibility
    ensureAccessibility();

    // Request screen capture if OCR is active
    if (AppConfig.settings.useOcr) {
        requestScreenCapturePermission();
    }

    // Launch floating UI
    setupFloatingUI();

    toastLog("Smart Clicker Ready! Use the floating controller.");
}

function ensureAccessibility() {
    if (auto.service == null) {
        toast("Please enable Accessibility Service for AutoX.js");
        app.startActivity({ action: "android.settings.ACCESSIBILITY_SETTINGS" });
        auto.waitFor();
        toastLog("Accessibility Service Enabled!");
    }
}

function requestScreenCapturePermission() {
    threads.start(function () {
        if (!requestScreenCapture(false)) {
            toastLog("Screen capture permission not granted. Native UI text only.");
            AppConfig.settings.useOcr = false;
        } else {
            toastLog("Screen capture granted for AI OCR!");
        }
    });
}

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

    // Draggable window logic
    var x = 0, y = 0, windowX, windowY;
    window.mainFrame.setOnTouchListener(function (view, event) {
        switch (event.getAction()) {
            case event.ACTION_DOWN:
                x = event.getRawX();
                y = event.getRawY();
                windowX = window.getX();
                windowY = window.getY();
                return true;
            case event.ACTION_MOVE:
                window.setPosition(windowX + (event.getRawX() - x), windowY + (event.getRawY() - y));
                return true;
            case event.ACTION_UP:
                return true;
        }
        return false;
    });

    window.btnToggle.setOnClickListener(function () {
        if (isPaused) {
            startEngine(window);
        } else {
            pauseEngine(window);
        }
    });

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

function engineLoop(uiWindow) {
    while (true) {
        if (!isPaused) {
            try {
                if (AppConfig.sequentialWorkflow && AppConfig.sequentialWorkflow.enabled) {
                    processSequentialWorkflow(uiWindow);
                } else {
                    processReactiveTriggers(uiWindow);
                }
            } catch (e) {
                log("Scanner error: " + e);
            }
        }
        sleep(AppConfig.settings.scanIntervalMs);
    }
}

function processReactiveTriggers(uiWindow) {
    var triggers = AppConfig.reactiveTriggers;
    var now = new Date().getTime();

    for (var i = 0; i < triggers.length; i++) {
        var item = triggers[i];
        var keyword = item.text;
        var cooldown = item.cooldownMs || AppConfig.settings.defaultCooldownMs;

        if (cooldownMap[keyword] && (now - cooldownMap[keyword] < cooldown)) {
            continue;
        }

        var clicked = attemptFindAndClick(item, uiWindow);
        if (clicked) {
            cooldownMap[keyword] = now;
            break;
        }
    }
}

function processSequentialWorkflow(uiWindow) {
    var steps = AppConfig.sequentialWorkflow.steps;
    if (!steps || steps.length === 0) return;

    if (currentWorkflowStep >= steps.length) {
        if (AppConfig.sequentialWorkflow.loopWorkflow) {
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

    var dummyTrigger = { text: step.waitForText, action: step.action || "click", exactMatch: false };
    var clicked = attemptFindAndClick(dummyTrigger, uiWindow);
    if (clicked) {
        currentWorkflowStep++;
        if (step.delayAfterMs) {
            sleep(step.delayAfterMs);
        }
    }
}

function attemptFindAndClick(trigger, uiWindow) {
    var keyword = trigger.text;

    // 1. Native Accessibility Node (0ms instant match)
    var nativeNode = findNativeNode(keyword, trigger.exactMatch);
    if (nativeNode != null) {
        var bounds = nativeNode.bounds();
        executeTap(bounds.centerX(), bounds.centerY(), keyword, "Native UI", uiWindow);
        return true;
    }

    // 2. On-Device AI OCR (PaddleOCR for graphics / games)
    if (AppConfig.settings.useOcr) {
        var ocrMatch = findByOcr(keyword);
        if (ocrMatch != null) {
            executeTap(ocrMatch.x, ocrMatch.y, keyword, "AI OCR", uiWindow);
            return true;
        }
    }

    return false;
}

function findNativeNode(keyword, exactMatch) {
    try {
        var s = exactMatch ? text(keyword) : textContains(keyword);
        if (s.exists()) return s.findOnce();

        var d = exactMatch ? desc(keyword) : descContains(keyword);
        if (d.exists()) return d.findOnce();
    } catch (e) {}
    return null;
}

function findByOcr(keyword) {
    try {
        var img = captureScreen();
        if (!img) return null;

        var ocrResults = null;
        if (typeof paddle !== 'undefined' && paddle.ocr) {
            ocrResults = paddle.ocr(img);
        } else if (typeof ocr !== 'undefined' && ocr.detect) {
            ocrResults = ocr.detect(img);
        }

        if (!ocrResults || ocrResults.length === 0) return null;

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
    } catch (err) {}
    return null;
}

function executeTap(x, y, keyword, source, uiWindow) {
    click(x, y);

    ui.run(function () {
        uiWindow.lastAction.setText("Clicked: " + keyword);
    });

    log("[Clicked] " + keyword + " at (" + Math.round(x) + ", " + Math.round(y) + ") via " + source);
}

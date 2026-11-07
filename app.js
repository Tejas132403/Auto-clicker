"ui";

/**
 * =========================================================================
 * SMART AI AUTO-CLICKER AND AI QUIZ SOLVER APP
 * =========================================================================
 * Full Android application with interactive UI:
 * - 1. "Anytime (Reactive)" Mode: Clicks any instructed text when it appears
 * - 2. "Line-by-Line (Sequential)" Mode: Executes step 1 -> step 2 -> step 3
 * - 3. "AI Quiz Solver" Mode: Reads changing quiz questions, asks AI, and auto-clicks the correct option!
 * - Dual Engine: Instant Native UI detection + On-Device AI OCR (for games and canvas)
 * - Draggable Floating Widget overlay with live status and "SOLVE" button
 * - Persistent storage: Your rules and API settings are saved automatically
 * - Works with Developer Options and USB Debugging OFF!
 * =========================================================================
 */

// Persistent Storage
var storage = storages.create("SMART_CLICKER_CONFIG_V3");

// Default initial data
var defaultReactive = [
    { id: 1, text: "Next", cooldown: 2, exact: false },
    { id: 2, text: "Submit", cooldown: 2, exact: false },
    { id: 3, text: "Add", cooldown: 2, exact: false },
    { id: 4, text: "Continue", cooldown: 2, exact: false },
    { id: 5, text: "Start", cooldown: 3, exact: false },
    { id: 6, text: "Claim", cooldown: 3, exact: false }
];

var defaultSteps = [
    { id: 1, stepNum: 1, text: "Start", delay: 1.5 },
    { id: 2, stepNum: 2, text: "Option A", delay: 1.0 },
    { id: 3, stepNum: 3, text: "Submit", delay: 2.0 }
];

// Load saved data or defaults
var reactiveList = storage.get("reactiveList", defaultReactive);
var sequentialList = storage.get("sequentialList", defaultSteps);
var currentMode = storage.get("currentMode", "reactive"); // "reactive", "sequential", or "ai_quiz"
var ocrEnabled = storage.get("ocrEnabled", true);
var scanInterval = storage.get("scanInterval", 600);

// Quiz Solver Settings
var solverMethod = storage.get("solverMethod", "web"); // "web" (default zero-setup) or "ai"
var aiApiKey = storage.get("aiApiKey", "");
var aiProvider = storage.get("aiProvider", "gemini"); // "gemini" or "groq"
var aiAutoSubmit = storage.get("aiAutoSubmit", true);
var aiSubmitKeyword = storage.get("aiSubmitKeyword", "Next");
var quizKeywords = storage.get("quizKeywords", "?, Question, Choose, Select, Q.");
var alsoClickButtonsInQuiz = storage.get("alsoClickButtonsInQuiz", true);

// App Theme and UI Layout
ui.layout(
    <drawer id="drawer">
        <vertical bg="#121218">
            {/* Top App Bar */}
            <appbar bg="#1E1E2E">
                <toolbar id="toolbar" title="🤖 Smart AI Auto-Clicker" titleTextColor="#FFFFFF" />
                <tabs id="tabs" bg="#1E1E2E" indicatorColor="#6366F1" textColor="#9CA3AF" selectedTextColor="#6366F1" />
            </appbar>

            {/* ViewPager for Tabs */}
            <viewpager id="viewpager" layout_weight="1">
                
                {/* TAB 1: REACTIVE MODE (Anytime Text Appears) */}
                <vertical padding="12">
                    <card bg="#1E1E2E" cardCornerRadius="12dp" cardElevation="3dp" padding="12" marginBottom="10">
                        <vertical>
                            <text text="⚡ Anytime (Reactive) Mode" textStyle="bold" textSize="16sp" textColor="#6366F1" />
                            <text text="Whenever ANY of these words appear on screen, the bot will automatically tap it." textSize="12sp" textColor="#9CA3AF" marginTop="2" />
                            <horizontal marginTop="8" gravity="center_vertical">
                                <radiogroup orientation="horizontal">
                                    <radio id="radioReactive" text="Use This Mode" textColor="#FFFFFF" checked="true" />
                                </radiogroup>
                            </horizontal>
                        </vertical>
                    </card>

                    {/* Add Item Bar */}
                    <horizontal gravity="center_vertical" marginBottom="8">
                        <input id="inputReactiveText" hint="Enter text to click (e.g. Next)" textColor="#FFFFFF" hintTextColor="#6B7280" bg="#1E1E2E" padding="10" w="0" layout_weight="1" singleLine="true" />
                        <input id="inputReactiveCooldown" hint="Cooldown (s)" text="2" textColor="#FFFFFF" hintTextColor="#6B7280" bg="#1E1E2E" padding="10" w="70dp" inputType="number" singleLine="true" marginLeft="6" />
                        <button id="btnAddReactive" text="＋ ADD" bg="#6366F1" textColor="#FFFFFF" textStyle="bold" w="65dp" marginLeft="6" />
                    </horizontal>

                    {/* List of Targets */}
                    <list id="listReactive" layout_weight="1">
                        <card bg="#1E1E2E" cardCornerRadius="8dp" margin="0 4 0 4" padding="10">
                            <horizontal gravity="center_vertical">
                                <vertical layout_weight="1">
                                    <text text="{{text}}" textColor="#FFFFFF" textStyle="bold" textSize="15sp" />
                                    <text text="Cooldown: {{cooldown}}s" textColor="#9CA3AF" textSize="12sp" />
                                </vertical>
                                <button id="btnDeleteReactive" text="Delete" textColor="#EF4444" bg="#282838" w="65dp" h="35dp" textSize="11sp" />
                            </horizontal>
                        </card>
                    </list>
                </vertical>

                {/* TAB 2: LINE-BY-LINE (Sequential Workflow) */}
                <vertical padding="12">
                    <card bg="#1E1E2E" cardCornerRadius="12dp" cardElevation="3dp" padding="12" marginBottom="10">
                        <vertical>
                            <text text="📋 Line-by-Line (Step-by-Step) Mode" textStyle="bold" textSize="16sp" textColor="#10B981" />
                            <text text="Executes strict sequence: Step 1 → Step 2 → Step 3. Waits until text appears before advancing." textSize="12sp" textColor="#9CA3AF" marginTop="2" />
                            <horizontal marginTop="8" gravity="center_vertical">
                                <radiogroup orientation="horizontal">
                                    <radio id="radioSequential" text="Use This Mode" textColor="#FFFFFF" />
                                </radiogroup>
                            </horizontal>
                        </vertical>
                    </card>

                    {/* Add Step Bar */}
                    <horizontal gravity="center_vertical" marginBottom="8">
                        <input id="inputStepText" hint="Step text (e.g. Option A)" textColor="#FFFFFF" hintTextColor="#6B7280" bg="#1E1E2E" padding="10" w="0" layout_weight="1" singleLine="true" />
                        <input id="inputStepDelay" hint="Delay (s)" text="1" textColor="#FFFFFF" hintTextColor="#6B7280" bg="#1E1E2E" padding="10" w="70dp" inputType="numberDecimal" singleLine="true" marginLeft="6" />
                        <button id="btnAddStep" text="＋ STEP" bg="#10B981" textColor="#FFFFFF" textStyle="bold" w="70dp" marginLeft="6" />
                    </horizontal>

                    {/* List of Steps */}
                    <list id="listSequential" layout_weight="1">
                        <card bg="#1E1E2E" cardCornerRadius="8dp" margin="0 4 0 4" padding="10">
                            <horizontal gravity="center_vertical">
                                <text text="Step {{stepNum}}:" textColor="#10B981" textStyle="bold" textSize="13sp" w="60dp" />
                                <vertical layout_weight="1">
                                    <text text="{{text}}" textColor="#FFFFFF" textStyle="bold" textSize="15sp" />
                                    <text text="Wait after click: {{delay}}s" textColor="#9CA3AF" textSize="12sp" />
                                </vertical>
                                <button id="btnDeleteStep" text="Delete" textColor="#EF4444" bg="#282838" w="65dp" h="35dp" textSize="11sp" />
                            </horizontal>
                        </card>
                    </list>
                </vertical>

                {/* TAB 3: AI QUIZ SOLVER (NEW!) */}
                {/* TAB 3: QUIZ AUTO-SOLVER */}
                <vertical padding="12">
                    <card bg="#1E1E2E" cardCornerRadius="12dp" cardElevation="3dp" padding="12" marginBottom="10">
                        <vertical>
                            <text text="🧠 Quiz Auto-Solver" textStyle="bold" textSize="16sp" textColor="#EC4899" />
                            <text text="Reads changing quiz questions on your screen, finds the answer automatically, and taps the correct option!" textSize="12sp" textColor="#9CA3AF" marginTop="2" />
                            <horizontal marginTop="8" gravity="center_vertical">
                                <radiogroup orientation="horizontal">
                                    <radio id="radioAiQuiz" text="Use Quiz Solver Mode" textColor="#FFFFFF" />
                                </radiogroup>
                            </horizontal>
                        </vertical>
                    </card>

                    {/* Method Selector */}
                    <card bg="#1E1E2E" cardCornerRadius="12dp" padding="12" marginBottom="10">
                        <vertical>
                            <text text="How to Solve Questions:" textStyle="bold" textSize="14sp" textColor="#FFFFFF" />
                            <radiogroup id="rgSolverMethod" orientation="vertical" marginTop="6">
                                <radio id="radioMethodWeb" text="🌐 Mobile Web Search (NO API KEY - Zero Setup)" textColor="#10B981" checked="true" />
                                <radio id="radioMethodAI" text="🤖 AI Model (Gemini / Groq with API Key)" textColor="#9CA3AF" marginTop="4" />
                            </radiogroup>
                        </vertical>
                    </card>

                    {/* AI Configuration Box (Optional) */}
                    <card id="cardAiSettings" bg="#1E1E2E" cardCornerRadius="12dp" padding="12" marginBottom="10">
                        <vertical>
                            <text text="AI API Key (Only needed for AI mode):" textStyle="bold" textSize="13sp" textColor="#FFFFFF" />
                            <input id="inputApiKey" hint="Paste Gemini or Groq API Key here" textColor="#FFFFFF" hintTextColor="#6B7280" bg="#121218" padding="10" singleLine="true" marginTop="6" />

                            <horizontal marginTop="8" gravity="center_vertical">
                                <text text="Provider: " textColor="#D1D5DB" textSize="13sp" />
                                <radiogroup id="rgProvider" orientation="horizontal">
                                    <radio id="radioGemini" text="Google Gemini" textColor="#FFFFFF" checked="true" />
                                    <radio id="radioGroq" text="Groq (Ultra-Fast 0.2s)" textColor="#FFFFFF" marginLeft="8" />
                                </radiogroup>
                            </horizontal>
                        </vertical>
                    </card>

                    {/* Common Quiz Settings */}
                    <card bg="#1E1E2E" cardCornerRadius="12dp" padding="12" marginBottom="10">
                        <vertical>
                            <checkbox id="checkAutoSubmit" text="Auto-Click Next after answering" textColor="#FFFFFF" checked="true" />
                            <horizontal gravity="center_vertical" marginTop="4">
                                <text text="Next button text: " textColor="#9CA3AF" textSize="12sp" />
                                <input id="inputSubmitKeyword" hint="e.g. Next, Submit" text="Next" textColor="#FFFFFF" hintTextColor="#6B7280" bg="#121218" padding="6" w="100dp" singleLine="true" marginLeft="4" />
                            </horizontal>

                            <text text="Quiz Detection Trigger Keywords:" textColor="#FFFFFF" textStyle="bold" textSize="13sp" marginTop="10" />
                            <text text="Words or symbols that mean a quiz is on screen (comma-separated):" textSize="11sp" textColor="#9CA3AF" marginTop="1" />
                            <input id="inputQuizKeywords" hint="e.g. ?, Question, Choose, Select, Q." textColor="#FFFFFF" hintTextColor="#6B7280" bg="#121218" padding="8" singleLine="true" marginTop="4" />

                            <checkbox id="checkAlsoClickButtons" text="Also Auto-Click Anytime Buttons (Tab 1)" textColor="#FFFFFF" checked="true" marginTop="8" />
                            <text text="When active, the bot simultaneously solves quiz questions AND auto-clicks buttons like Start, Next, Continue, Claim Reward!" textSize="11sp" textColor="#9CA3AF" marginTop="1" />

                            <horizontal marginTop="10">
                                <button id="btnSaveAiConfig" text="💾 SAVE SETTINGS" bg="#EC4899" textColor="#FFFFFF" textStyle="bold" w="0" layout_weight="1" h="40dp" />
                                <button id="btnTestAiConnection" text="🧪 TEST SOLVER" bg="#6366F1" textColor="#FFFFFF" textStyle="bold" w="110dp" h="40dp" marginLeft="8" />
                            </horizontal>
                            <text id="txtTestStatus" text="" textSize="11sp" textColor="#10B981" marginTop="4" visibility="gone" />
                        </vertical>
                    </card>
                </vertical>

                {/* TAB 4: SETTINGS AND PERMISSIONS */}
                <vertical padding="12">
                    <card bg="#1E1E2E" cardCornerRadius="12dp" padding="12" marginBottom="10">
                        <vertical>
                            <text text="Detection and AI Engine" textStyle="bold" textSize="16sp" textColor="#F59E0B" />
                            <checkbox id="checkOcr" text="Enable On-Device AI OCR (For Games and Canvas)" textColor="#FFFFFF" checked="true" marginTop="8" />
                            <text text="Turn ON if your app draws text as graphics (e.g. Unity, Flutter, Games). Turn OFF for maximum speed on regular apps." textSize="11sp" textColor="#9CA3AF" />
                        </vertical>
                    </card>

                    <card bg="#1E1E2E" cardCornerRadius="12dp" padding="12" marginBottom="10">
                        <vertical>
                            <text text="Permissions Status" textStyle="bold" textSize="16sp" textColor="#FFFFFF" />
                            <text text="1. Accessibility Service: Needed to detect text and click without PC or Developer mode." textSize="12sp" textColor="#9CA3AF" marginTop="4" />
                            <button id="btnCheckAccessibility" text="Check / Grant Accessibility" bg="#374151" textColor="#FFFFFF" marginTop="6" h="38dp" />
                            
                            <text text="2. Floating Window: Needed to show start and pause buttons over your apps." textSize="12sp" textColor="#9CA3AF" marginTop="8" />
                            <button id="btnCheckFloating" text="Check / Grant Floating Window" bg="#374151" textColor="#FFFFFF" marginTop="6" h="38dp" />
                        </vertical>
                    </card>

                    <card bg="#1E1E2E" cardCornerRadius="12dp" padding="12">
                        <vertical>
                            <text text="How To Use" textStyle="bold" textSize="15sp" textColor="#6366F1" />
                            <text text="• Select your desired mode above (Anytime, Line-by-Line, or AI Quiz)." textSize="12sp" textColor="#D1D5DB" marginTop="4" />
                            <text text="• Tap START FLOATING BOT at the bottom." textSize="12sp" textColor="#D1D5DB" marginTop="2" />
                            <text text="• Open your quiz or game app." textSize="12sp" textColor="#D1D5DB" marginTop="2" />
                            <text text="• Tap START or SOLVE on the floating widget!" textSize="12sp" textColor="#D1D5DB" marginTop="2" />
                        </vertical>
                    </card>
                </vertical>

            </viewpager>

            {/* Bottom Master Launch Bar */}
            <card bg="#1E1E2E" cardCornerRadius="0" cardElevation="10dp" padding="10">
                <vertical>
                    <button id="btnLaunchFloating" text="🚀 START FLOATING BOT OVER APPS" bg="#10B981" textColor="#FFFFFF" textStyle="bold" textSize="15sp" h="48dp" />
                </vertical>
            </card>
        </vertical>
    </drawer>
);

// -------------------------------------------------------------
// APP INITIALIZATION AND EVENT BINDINGS
// -------------------------------------------------------------

// Setup Tabs
ui.viewpager.setTitles(["Anytime Words", "Line-by-Line", "AI Quiz Solver", "Settings"]);
ui.tabs.setupWithViewPager(ui.viewpager);

// Bind lists to data
ui.listReactive.setDataSource(reactiveList);
ui.listSequential.setDataSource(sequentialList);

// Restore saved settings
if (currentMode === "sequential") {
    ui.radioSequential.setChecked(true);
    ui.radioReactive.setChecked(false);
    ui.radioAiQuiz.setChecked(false);
} else if (currentMode === "ai_quiz") {
    ui.radioAiQuiz.setChecked(true);
    ui.radioReactive.setChecked(false);
    ui.radioSequential.setChecked(false);
} else {
    ui.radioReactive.setChecked(true);
    ui.radioSequential.setChecked(false);
    ui.radioAiQuiz.setChecked(false);
}

if (solverMethod === "ai") {
    ui.radioMethodAI.setChecked(true);
    ui.radioMethodWeb.setChecked(false);
} else {
    ui.radioMethodWeb.setChecked(true);
    ui.radioMethodAI.setChecked(false);
}

ui.radioMethodWeb.on("check", function(checked) {
    if (checked) {
        ui.radioMethodAI.setChecked(false);
        solverMethod = "web";
        storage.put("solverMethod", "web");
        toast("Solver: Mobile Web Search (No API Key)");
    }
});

ui.radioMethodAI.on("check", function(checked) {
    if (checked) {
        ui.radioMethodWeb.setChecked(false);
        solverMethod = "ai";
        storage.put("solverMethod", "ai");
        toast("Solver: AI Model (Requires Key)");
    }
});

ui.checkOcr.setChecked(ocrEnabled);
ui.inputApiKey.setText(aiApiKey);
ui.checkAutoSubmit.setChecked(aiAutoSubmit);
ui.inputSubmitKeyword.setText(aiSubmitKeyword);
ui.inputQuizKeywords.setText(quizKeywords);
ui.checkAlsoClickButtons.setChecked(alsoClickButtonsInQuiz);

if (aiProvider === "groq") {
    ui.radioGroq.setChecked(true);
    ui.radioGemini.setChecked(false);
} else {
    ui.radioGemini.setChecked(true);
    ui.radioGroq.setChecked(false);
}

// Mode Selection Radio Events
ui.radioReactive.on("check", function(checked) {
    if (checked) {
        ui.radioSequential.setChecked(false);
        ui.radioAiQuiz.setChecked(false);
        setMode("reactive", "Anytime (Reactive)");
    }
});

ui.radioSequential.on("check", function(checked) {
    if (checked) {
        ui.radioReactive.setChecked(false);
        ui.radioAiQuiz.setChecked(false);
        setMode("sequential", "Line-by-Line (Sequential)");
    }
});

ui.radioAiQuiz.on("check", function(checked) {
    if (checked) {
        ui.radioReactive.setChecked(false);
        ui.radioSequential.setChecked(false);
        setMode("ai_quiz", "Quiz Auto-Solver");
    }
});

function setMode(modeKey, modeName) {
    currentMode = modeKey;
    storage.put("currentMode", modeKey);
    toast("Mode set to: " + modeName);
}

// Save Quiz Config
ui.btnSaveAiConfig.on("click", function() {
    solverMethod = ui.radioMethodAI.isChecked() ? "ai" : "web";
    aiApiKey = ui.inputApiKey.getText().toString().trim();
    aiProvider = ui.radioGroq.isChecked() ? "groq" : "gemini";
    aiAutoSubmit = ui.checkAutoSubmit.isChecked();
    aiSubmitKeyword = ui.inputSubmitKeyword.getText().toString().trim() || "Next";
    quizKeywords = ui.inputQuizKeywords.getText().toString().trim() || "?, Question, Choose, Select";
    alsoClickButtonsInQuiz = ui.checkAlsoClickButtons.isChecked();

    storage.put("solverMethod", solverMethod);
    storage.put("aiApiKey", aiApiKey);
    storage.put("aiProvider", aiProvider);
    storage.put("aiAutoSubmit", aiAutoSubmit);
    storage.put("aiSubmitKeyword", aiSubmitKeyword);
    storage.put("quizKeywords", quizKeywords);
    storage.put("alsoClickButtonsInQuiz", alsoClickButtonsInQuiz);

    toast("Quiz Configuration Saved! ✅");
});

// Test Solver button (Tests Web Search or AI depending on selection)
ui.btnTestAiConnection.on("click", function() {
    var method = ui.radioMethodAI.isChecked() ? "ai" : "web";
    ui.txtTestStatus.setVisibility(android.view.View.VISIBLE);

    if (method === "web") {
        ui.txtTestStatus.setText("Testing Mobile Web Search...");
        ui.txtTestStatus.setTextColor(colors.parseColor("#F59E0B"));
        threads.start(function() {
            var sample = "Question: Which city is the capital of France?\nLondon\nParis\nRome\nBerlin";
            var res = queryWebSearchAnswer(sample);
            ui.run(function() {
                if (res.success) {
                    ui.txtTestStatus.setText("✅ Web Search Working! Answer: " + res.answer);
                    ui.txtTestStatus.setTextColor(colors.parseColor("#10B981"));
                    dialogs.alert("✅ Web Search Working Perfectly!", "Question: Capital of France?\nDetected Options: London, Paris, Rome, Berlin\n\nSearch Winner: " + res.answer + " (" + (res.details || "highest hits") + ")\n\nZero API Key needed! You can start solving quizzes immediately!");
                } else {
                    ui.txtTestStatus.setText("❌ Failed: " + res.error);
                    ui.txtTestStatus.setTextColor(colors.parseColor("#EF4444"));
                    dialogs.alert("❌ Search Failed", res.error + "\n\nPlease check your mobile internet connection.");
                }
            });
        });
    } else {
        // AI Test
        var key = ui.inputApiKey.getText().toString().trim().replace(/^["']|["']$/g, '');
        var prov = ui.radioGroq.isChecked() ? "groq" : "gemini";
        if (!key) {
            toast("Please enter your API Key first!");
            return;
        }

        ui.txtTestStatus.setText("Connecting to " + (prov === "groq" ? "Groq" : "Gemini") + "...");
        ui.txtTestStatus.setTextColor(colors.parseColor("#F59E0B"));

        threads.start(function() {
            var testPrompt = "What is the capital of France? Return ONLY the city name.";
            var res = executeAiCall(prov, key, testPrompt);
            ui.run(function() {
                if (res.success) {
                    ui.txtTestStatus.setText("✅ Success! AI answered: " + res.answer);
                    ui.txtTestStatus.setTextColor(colors.parseColor("#10B981"));
                    dialogs.alert("✅ Connection Successful!", "AI responded: " + res.answer + "\n\nYour API key is working perfectly!");
                } else {
                    ui.txtTestStatus.setText("❌ Failed: " + res.error);
                    ui.txtTestStatus.setTextColor(colors.parseColor("#EF4444"));
                    dialogs.alert("❌ AI Test Failed", res.error + "\n\nPlease check:\n1. Did you copy the full API key without extra spaces?\n2. Did you select the correct provider (Gemini vs Groq)?\n3. Check your internet connection.");
                }
            });
        });
    }
});

ui.checkOcr.on("check", function(checked) {
    ocrEnabled = checked;
    storage.put("ocrEnabled", checked);
});

// ADD REACTIVE TARGET
ui.btnAddReactive.on("click", function() {
    var txt = ui.inputReactiveText.getText().toString().trim();
    var cd = parseFloat(ui.inputReactiveCooldown.getText().toString().trim()) || 2;
    if (!txt) {
        toast("Please enter a text word!");
        return;
    }
    reactiveList.push({ id: new Date().getTime(), text: txt, cooldown: cd, exact: false });
    saveAndRefreshReactive();
    ui.inputReactiveText.setText("");
    toast("Added: " + txt);
});

// DELETE REACTIVE TARGET
ui.listReactive.on("item_bind", function(itemView, itemHolder) {
    itemView.btnDeleteReactive.on("click", function() {
        var pos = itemHolder.position;
        reactiveList.splice(pos, 1);
        saveAndRefreshReactive();
    });
});

function saveAndRefreshReactive() {
    storage.put("reactiveList", reactiveList);
    ui.listReactive.setDataSource(reactiveList);
}

// ADD SEQUENTIAL STEP
ui.btnAddStep.on("click", function() {
    var txt = ui.inputStepText.getText().toString().trim();
    var delay = parseFloat(ui.inputStepDelay.getText().toString().trim()) || 1.0;
    if (!txt) {
        toast("Please enter text for this step!");
        return;
    }
    sequentialList.push({ id: new Date().getTime(), stepNum: sequentialList.length + 1, text: txt, delay: delay });
    saveAndRefreshSequential();
    ui.inputStepText.setText("");
    toast("Added Step " + sequentialList.length + ": " + txt);
});

// DELETE SEQUENTIAL STEP
ui.listSequential.on("item_bind", function(itemView, itemHolder) {
    itemView.btnDeleteStep.on("click", function() {
        var pos = itemHolder.position;
        sequentialList.splice(pos, 1);
        for (var i = 0; i < sequentialList.length; i++) {
            sequentialList[i].stepNum = i + 1;
        }
        saveAndRefreshSequential();
    });
});

function saveAndRefreshSequential() {
    storage.put("sequentialList", sequentialList);
    ui.listSequential.setDataSource(sequentialList);
}

// PERMISSION CHECK BUTTONS
ui.btnCheckAccessibility.on("click", function() {
    if (auto.service == null) {
        app.startActivity({ action: "android.settings.ACCESSIBILITY_SETTINGS" });
    } else {
        toast("Accessibility Service is already enabled! ✅");
    }
});

ui.btnCheckFloating.on("click", function() {
    if (!floaty.checkPermission()) {
        floaty.requestPermission();
    } else {
        toast("Floating Window permission is already enabled! ✅");
    }
});

// -------------------------------------------------------------
// LAUNCH FLOATING BOT CONTROLLER OVER APPS
// -------------------------------------------------------------
ui.btnLaunchFloating.on("click", function() {
    if (auto.service == null) {
        toast("Please enable Accessibility Service first!");
        app.startActivity({ action: "android.settings.ACCESSIBILITY_SETTINGS" });
        return;
    }

    if (!floaty.checkPermission()) {
        toast("Please allow Floating Window permission!");
        floaty.requestPermission();
        return;
    }

    if (ocrEnabled) {
        threads.start(function() {
            if (!requestScreenCapture(false)) {
                toast("Screen capture denied. Native UI detection only.");
                ocrEnabled = false;
            }
        });
    }

    // Save state
    storage.put("reactiveList", reactiveList);
    storage.put("sequentialList", sequentialList);
    storage.put("currentMode", currentMode);
    storage.put("ocrEnabled", ocrEnabled);

    // Minimize app to home screen
    app.startActivity({
        action: "android.intent.action.MAIN",
        category: "android.intent.category.HOME",
        flags: ["ACTIVITY_NEW_TASK"]
    });

    // Launch floating overlay widget
    startFloatingOverlay();
});

// -------------------------------------------------------------
// FLOATING CONTROLLER WIDGET AND BACKGROUND SCANNER
// -------------------------------------------------------------
var isBotActive = false;
var engineThread = null;
var cooldownMap = {};
var currentStepIndex = 0;

function startFloatingOverlay() {
    var floatWin = floaty.window(
        <frame id="mainFrame" bg="#DD181825" padding="8" cornerRadius="16">
            <vertical gravity="center">
                <text id="floatTitle" text="🤖 AI Clicker" textSize="13sp" textColor="#FFFFFF" textStyle="bold" gravity="center" />
                <text id="floatMode" text="Mode: Anytime" textSize="10sp" textColor="#6366F1" gravity="center" marginTop="1" />
                <text id="floatStatus" text="PAUSED" textSize="11sp" textColor="#F59E0B" textStyle="bold" gravity="center" marginTop="2" />
                <text id="floatLastAction" text="Tap START" textSize="9sp" textColor="#9CA3AF" gravity="center" marginTop="1" />
                
                <horizontal gravity="center" marginTop="6">
                    <button id="btnToggle" text="START" textSize="11sp" w="54" h="32" bg="#10B981" textColor="#FFFFFF" margin="2" />
                    <button id="btnSolveNow" text="🧠 SOLVE" textSize="10sp" w="64" h="32" bg="#EC4899" textColor="#FFFFFF" textStyle="bold" margin="2" />
                    <button id="btnReturnApp" text="⚙" textSize="12sp" w="30" h="32" bg="#4F46E5" textColor="#FFFFFF" margin="2" />
                    <button id="btnClose" text="✕" textSize="11sp" w="30" h="32" bg="#EF4444" textColor="#FFFFFF" margin="2" />
                </horizontal>
            </vertical>
        </frame>
    );

    // Update initial label
    ui.run(function() {
        var modeStr = "Mode: Anytime";
        if (currentMode === "sequential") modeStr = "Mode: Line-by-Line";
        if (currentMode === "ai_quiz") modeStr = "Mode: AI Quiz Solver";
        floatWin.floatMode.setText(modeStr);
    });

    // Make floating widget draggable
    var touchX = 0, touchY = 0, winX = 0, winY = 0;
    floatWin.mainFrame.setOnTouchListener(function(v, event) {
        switch (event.getAction()) {
            case event.ACTION_DOWN:
                touchX = event.getRawX();
                touchY = event.getRawY();
                winX = floatWin.getX();
                winY = floatWin.getY();
                return true;
            case event.ACTION_MOVE:
                floatWin.setPosition(winX + (event.getRawX() - touchX), winY + (event.getRawY() - touchY));
                return true;
            case event.ACTION_UP:
                return true;
        }
        return false;
    });

    // Manual SOLVE button: Taps instantly on demand
    floatWin.btnSolveNow.setOnClickListener(function() {
        threads.start(function() {
            triggerAiSolveWorkflow(floatWin);
        });
    });

    // START / PAUSE toggle
    floatWin.btnToggle.setOnClickListener(function() {
        if (!isBotActive) {
            isBotActive = true;
            ui.run(function() {
                floatWin.floatStatus.setText("ACTIVE");
                floatWin.floatStatus.setTextColor(colors.parseColor("#10B981"));
                floatWin.btnToggle.setText("PAUSE");
                floatWin.btnToggle.attr("bg", "#F59E0B");
            });
            toast("Bot Activated!");

            if (engineThread == null || !engineThread.isAlive()) {
                engineThread = threads.start(function() {
                    backgroundScanLoop(floatWin);
                });
            }
        } else {
            isBotActive = false;
            ui.run(function() {
                floatWin.floatStatus.setText("PAUSED");
                floatWin.floatStatus.setTextColor(colors.parseColor("#F59E0B"));
                floatWin.btnToggle.setText("START");
                floatWin.btnToggle.attr("bg", "#10B981");
            });
            toast("Bot Paused");
        }
    });

    // Return to main configuration screen
    floatWin.btnReturnApp.setOnClickListener(function() {
        isBotActive = false;
        if (engineThread != null && engineThread.isAlive()) {
            engineThread.interrupt();
        }
        floatWin.close();
        app.startActivity({
            action: "android.intent.action.MAIN",
            packageName: context.getPackageName(),
            className: "org.autojs.autojs.ui.main.MainActivity"
        });
    });

    // Close float window
    floatWin.btnClose.setOnClickListener(function() {
        isBotActive = false;
        if (engineThread != null && engineThread.isAlive()) {
            engineThread.interrupt();
        }
        floatWin.close();
        toast("Bot Closed.");
    });
}

/**
 * Background loop that monitors screen
 */
function backgroundScanLoop(floatWin) {
    while (true) {
        if (isBotActive) {
            try {
                if (currentMode === "ai_quiz") {
                    handleAiQuizAutoLoop(floatWin);
                } else if (currentMode === "sequential") {
                    handleSequentialStep(floatWin);
                } else {
                    handleReactiveScan(floatWin);
                }
            } catch (err) {
                log("Scan error: " + err);
            }
        }
        sleep(scanInterval);
    }
}

/**
 * AI Quiz Solver Workflow
 */
var lastSolvedQuestion = "";

function handleAiQuizAutoLoop(floatWin) {
    // 1. Check if any reactive button from Tab 1 (e.g. Next, Submit, Claim, Continue, Start) is visible on screen
    if (alsoClickButtonsInQuiz) {
        var clickedButton = checkAndClickReactiveButtons(floatWin);
        if (clickedButton) {
            sleep(1000);
            return;
        }
    }

    // 2. Read screen text to check for quiz question
    var screenContent = scrapeCurrentScreen();
    if (!screenContent || screenContent.length < 8) return;

    // Avoid repeatedly solving the exact same question
    if (screenContent === lastSolvedQuestion) return;

    // 3. Check if screen contains any of the user's custom quiz trigger keywords
    if (isQuizScreen(screenContent)) {
        triggerAiSolveWorkflow(floatWin);
    }
}

function isQuizScreen(content) {
    if (!quizKeywords) return content.indexOf("?") !== -1;
    var lowerContent = content.toLowerCase();
    var kwList = quizKeywords.split(",");
    for (var i = 0; i < kwList.length; i++) {
        var kw = kwList[i].trim().toLowerCase();
        if (kw.length > 0 && lowerContent.indexOf(kw) !== -1) {
            return true;
        }
    }
    return false;
}

function checkAndClickReactiveButtons(floatWin) {
    var now = new Date().getTime();
    for (var i = 0; i < reactiveList.length; i++) {
        var item = reactiveList[i];
        var keyword = item.text;
        var cdMs = (item.cooldown || 2) * 1000;

        if (cooldownMap[keyword] && (now - cooldownMap[keyword] < cdMs)) {
            continue;
        }

        var didClick = detectAndClick(keyword, item.exact, floatWin);
        if (didClick) {
            cooldownMap[keyword] = now;
            return true;
        }
    }
    return false;
}

function triggerAiSolveWorkflow(floatWin) {
    ui.run(function() {
        floatWin.floatLastAction.setText("Reading Screen...");
    });

    var screenText = scrapeCurrentScreen();
    if (!screenText || screenText.length < 5) {
        ui.run(function() { floatWin.floatLastAction.setText("No text found"); });
        return;
    }

    lastSolvedQuestion = screenText;

    var result = null;
    if (solverMethod === "ai") {
        if (!aiApiKey) {
            toast("Please enter your API Key or switch to Web Search mode!");
            ui.run(function() { floatWin.floatLastAction.setText("Missing API Key"); });
            return;
        }
        ui.run(function() { floatWin.floatLastAction.setText("AI Thinking..."); });
        result = queryAiAnswer(screenText);
    } else {
        // Mobile Web Search (Default, No API Key Needed)
        ui.run(function() { floatWin.floatLastAction.setText("Searching Web..."); });
        result = queryWebSearchAnswer(screenText);
    }

    if (!result || !result.success) {
        var errStr = (result && result.error) ? result.error : "No answer found";
        ui.run(function() { floatWin.floatLastAction.setText(errStr); });
        toast(errStr);
        return;
    }

    var displayLabel = (result.letter ? result.letter + ": " : "") + (result.answer || "");
    ui.run(function() {
        floatWin.floatLastAction.setText("Ans: " + displayLabel);
    });

    // Click option (matches A/B/C/D letter or option text)
    var clicked = clickQuizAnswerOption(result, floatWin);
    if (clicked) {
        toast("Clicked: " + displayLabel);
        sleep(1000);
        if (aiAutoSubmit && aiSubmitKeyword) {
            detectAndClick(aiSubmitKeyword, false, floatWin);
        } else if (alsoClickButtonsInQuiz) {
            checkAndClickReactiveButtons(floatWin);
        }
    } else {
        log("Could not find matching option on screen: " + displayLabel);
    }
}

/**
 * Tries multiple variants to ensure clicking the right option:
 * 1. Option Text (e.g. 'Paris')
 * 2. Full option line (e.g. 'B. Paris')
 * 3. Letter with dot/bracket (e.g. 'B.', 'B)')
 * 4. Letter alone exact (e.g. 'B')
 * 5. 'Option B'
 */
function clickQuizAnswerOption(resObj, floatWin) {
    var letter = (resObj.letter || "").trim().toUpperCase();
    var text = (resObj.answer || "").trim();
    var raw = (resObj.raw || "").trim();
    var cleanText = text.replace(/^[A-Ea-e1-5][\.\)\:\s]\s*/, "").trim();

    var candidates = [];

    // 1. Text of option
    if (cleanText && cleanText.length > 0) candidates.push({ text: cleanText, exact: false });
    if (text && text.length > 0 && text !== cleanText) candidates.push({ text: text, exact: false });
    if (raw && raw.length > 0 && raw !== text && raw !== cleanText) candidates.push({ text: raw, exact: false });

    // 2. Letter button variants (e.g. 'B', 'B.', 'B)', 'Option B')
    if (letter && letter.length > 0) {
        candidates.push({ text: letter + ".", exact: true });
        candidates.push({ text: letter + ")", exact: true });
        candidates.push({ text: "Option " + letter, exact: false });
        candidates.push({ text: "Option" + letter, exact: false });
        candidates.push({ text: letter, exact: true }); // Exact match to avoid false matching words with 'A'
    }

    for (var i = 0; i < candidates.length; i++) {
        var item = candidates[i];
        var didClick = detectAndClick(item.text, item.exact, floatWin);
        if (didClick) {
            log("[Quiz Clicked] " + item.text);
            return true;
        }
    }
    return false;
}

/**
 * Mobile Web Search Quiz Solver (Zero API Key Needed!)
 * Searches DuckDuckGo / Bing in the background and counts option occurrences
 */
function queryWebSearchAnswer(screenContent) {
    try {
        var parsed = parseQuizQuestionAndOptions(screenContent);
        if (!parsed || !parsed.question || parsed.options.length === 0) {
            return { success: false, error: "No quiz options detected" };
        }

        var q = parsed.question;
        var opts = parsed.options;

        // 1. Fetch search result HTML
        var res = null;
        try {
            res = http.get("https://html.duckduckgo.com/html/?q=" + encodeURIComponent(q), {
                headers: {
                    "User-Agent": "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36"
                },
                timeout: 8000
            });
        } catch (e) {}

        // Fallback to Bing if needed
        if (!res || res.statusCode !== 200) {
            try {
                res = http.get("https://www.bing.com/search?q=" + encodeURIComponent(q), {
                    headers: {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    },
                    timeout: 8000
                });
            } catch (e) {}
        }

        if (!res || res.statusCode !== 200) {
            return { success: false, error: "Search failed (Check internet)" };
        }

        var html = (res.body ? res.body.string() : "").toLowerCase();

        // Check if question asks for NOT / EXCEPT / INCORRECT
        var isNegative = /\b(not|never|except|least|incorrect|wrong|false)\b/i.test(q);

        var bestOptionObj = null;
        var bestCount = isNegative ? 999999 : -1;
        var details = [];

        for (var i = 0; i < opts.length; i++) {
            var optObj = opts[i];
            var cleanOpt = optObj.text.toLowerCase();
            if (cleanOpt.length < 1) continue;

            var count = countOccurrences(html, cleanOpt);
            details.push(optObj.letter + ":" + count);

            if (isNegative) {
                if (count < bestCount) {
                    bestCount = count;
                    bestOptionObj = optObj;
                }
            } else {
                if (count > bestCount) {
                    bestCount = count;
                    bestOptionObj = optObj;
                }
            }
        }

        if (!bestOptionObj) {
            return { success: false, error: "No clear answer found" };
        }

        return {
            success: true,
            letter: bestOptionObj.letter,
            answer: bestOptionObj.text,
            raw: bestOptionObj.raw,
            details: details.join(", ")
        };
    } catch (err) {
        return { success: false, error: "Search Error: " + err };
    }
}

function countOccurrences(text, searchTerm) {
    if (!searchTerm || searchTerm.length === 0) return 0;
    var count = 0;
    var pos = 0;
    while ((pos = text.indexOf(searchTerm, pos)) !== -1) {
        count++;
        pos += searchTerm.length;
    }
    return count;
}

function parseQuizQuestionAndOptions(content) {
    var lines = content.split("\n");
    var cleanLines = [];
    for (var i = 0; i < lines.length; i++) {
        var l = lines[i].trim();
        if (l.length > 0 && !/^(score|points|coins|level|round|time|timer|\d+s|\d+:\d+)/i.test(l)) {
            cleanLines.push(l);
        }
    }

    if (cleanLines.length < 2) return null;

    var qIndex = -1;
    for (var i = 0; i < cleanLines.length; i++) {
        if (cleanLines[i].indexOf("?") !== -1) {
            qIndex = i;
            break;
        }
    }

    if (qIndex === -1) {
        for (var i = 0; i < cleanLines.length; i++) {
            if (cleanLines[i].length > 15) {
                qIndex = i;
                break;
            }
        }
        if (qIndex === -1) qIndex = 0;
    }

    var question = cleanLines[qIndex].replace(/^(question\s*\d*[\:\.\-]?|q\s*\d*[\:\.\-]?)/i, "").trim();
    var letters = ["A", "B", "C", "D", "E"];
    var options = [];
    var optCount = 0;

    for (var j = 0; j < cleanLines.length; j++) {
        if (j !== qIndex) {
            var raw = cleanLines[j].trim();
            if (!/^(next|submit|continue|start|skip|confirm|quit|exit|back|add)/i.test(raw)) {
                var match = raw.match(/^([A-Ea-e1-5])[\.\)\:\s]\s*(.*)$/);
                var assignedLetter = "";
                var cleanText = raw;

                if (match) {
                    var lChar = match[1].toUpperCase();
                    if (/^\d$/.test(lChar)) {
                        assignedLetter = letters[parseInt(lChar) - 1] || lChar;
                    } else {
                        assignedLetter = lChar;
                    }
                    cleanText = match[2].trim();
                } else {
                    assignedLetter = letters[optCount] || "";
                }

                options.push({
                    letter: assignedLetter,
                    raw: raw,
                    text: cleanText.length > 0 ? cleanText : raw
                });
                optCount++;
            }
        }
    }

    return { question: question, options: options };
}

/**
 * Scrapes all visible text from screen (Native UI or OCR)
 */
function scrapeCurrentScreen() {
    var texts = [];

    // 1. Try Native UI
    try {
        var nodes = textMatches(/.+/).find();
        for (var i = 0; i < nodes.length; i++) {
            var t = nodes[i].text();
            if (t && t.trim().length > 0 && texts.indexOf(t) === -1) {
                texts.push(t.trim());
            }
        }
    } catch (e) {}

    // 2. Also run OCR if enabled and we have few texts (or game canvas)
    if (texts.length < 5 && ocrEnabled) {
        try {
            var img = captureScreen();
            if (img) {
                var ocrRes = (typeof paddle !== 'undefined' && paddle.ocr) ? paddle.ocr(img) : ocr.detect(img);
                if (ocrRes) {
                    for (var j = 0; j < ocrRes.length; j++) {
                        var ocrTxt = ocrRes[j].text;
                        if (ocrTxt && ocrTxt.trim().length > 0 && texts.indexOf(ocrTxt) === -1) {
                            texts.push(ocrTxt.trim());
                        }
                    }
                }
            }
        } catch (e) {}
    }

    return texts.join("\n");
}

/**
 * Calls AI API (Google Gemini or Groq) to find the correct answer
 */
function queryAiAnswer(screenContent) {
    var key = (aiApiKey || "").trim().replace(/^["']|["']$/g, '');
    if (!key) {
        return { success: false, error: "API Key Empty" };
    }

    var prompt = "Here is the text from a quiz app screen containing a question and multiple choice options:\n\n"
               + screenContent
               + "\n\nIdentify the correct option. Return ONLY the exact text of the correct answer option, with no explanations, no prefixes, and no extra words.";

    return executeAiCall(aiProvider, key, prompt);
}

function executeAiCall(provider, key, prompt) {
    try {
        if (provider === "groq") {
            var url = "https://api.groq.com/openai/v1/chat/completions";
            var payload = JSON.stringify({
                model: "llama-3.1-8b-instant",
                messages: [
                    { role: "system", content: "You are a quiz assistant. Output ONLY the exact text of the correct choice." },
                    { role: "user", content: prompt }
                ],
                temperature: 0.1,
                max_tokens: 30
            });

            var res = http.post(url, payload, {
                headers: {
                    "Authorization": "Bearer " + key,
                    "Content-Type": "application/json"
                },
                timeout: 10000
            });

            if (!res) return { success: false, error: "No response from Groq" };

            var bodyStr = res.body ? res.body.string() : "";
            if (res.statusCode === 200) {
                var json = JSON.parse(bodyStr);
                var text = json.choices[0].message.content.trim();
                var letterMatch = text.match(/LETTER\s*:\s*([A-Ea-e1-5])/i);
                var optLetter = letterMatch ? letterMatch[1].toUpperCase() : "";
                var clean = cleanAnswerText(text.replace(/LETTER\s*:\s*[A-Ea-e1-5]/i, ""));
                return { success: true, letter: optLetter, answer: clean };
            } else {
                return { success: false, error: parseErrorMsg(bodyStr, res.statusCode) };
            }
        } else {
            // Google Gemini API
            var payload = JSON.stringify({
                contents: [{
                    parts: [{ text: prompt }]
                }],
                generationConfig: {
                    temperature: 0.1,
                    maxOutputTokens: 35
                }
            });

            var url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=" + key;
            var res = http.post(url, payload, {
                headers: { "Content-Type": "application/json" },
                timeout: 10000
            });

            if (res && res.statusCode === 404) {
                // Fallback to gemini-2.0-flash
                url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=" + key;
                res = http.post(url, payload, {
                    headers: { "Content-Type": "application/json" },
                    timeout: 10000
                });
            }

            if (!res) return { success: false, error: "No response from Gemini" };

            var bodyStr = res.body ? res.body.string() : "";
            if (res.statusCode === 200) {
                var json = JSON.parse(bodyStr);
                if (json.candidates && json.candidates.length > 0 && json.candidates[0].content && json.candidates[0].content.parts.length > 0) {
                    var text = json.candidates[0].content.parts[0].text.trim();
                    var letterMatch = text.match(/LETTER\s*:\s*([A-Ea-e1-5])/i);
                    var optLetter = letterMatch ? letterMatch[1].toUpperCase() : "";
                    var clean = cleanAnswerText(text.replace(/LETTER\s*:\s*[A-Ea-e1-5]/i, ""));
                    return { success: true, letter: optLetter, answer: clean };
                } else {
                    return { success: false, error: "Empty AI response" };
                }
            } else {
                return { success: false, error: parseErrorMsg(bodyStr, res.statusCode) };
            }
        }
    } catch (e) {
        var msg = e.message || String(e);
        if (msg.indexOf("UnknownHost") !== -1) msg = "No Internet Connection";
        if (msg.indexOf("timeout") !== -1) msg = "Network Timeout";
        return { success: false, error: msg };
    }
}

function parseErrorMsg(bodyStr, statusCode) {
    try {
        var j = JSON.parse(bodyStr);
        if (j.error && j.error.message) {
            return "HTTP " + statusCode + ": " + j.error.message.substring(0, 35);
        }
    } catch(e) {}
    return "HTTP " + statusCode + " Error";
}

function cleanAnswerText(txt) {
    if (!txt) return "";
    var cleaned = txt.replace(/[\*\"\'\`]/g, "").trim();
    cleaned = cleaned.replace(/^[A-Da-d1-4][\.\)\:\s]\s*/, "");
    return cleaned;
}

/**
 * Reactive Mode Scanner (Anytime target appears)
 */
function handleReactiveScan(floatWin) {
    checkAndClickReactiveButtons(floatWin);
}

/**
 * Line-by-Line Sequential Mode
 */
function handleSequentialStep(floatWin) {
    if (!sequentialList || sequentialList.length === 0) return;

    if (currentStepIndex >= sequentialList.length) {
        currentStepIndex = 0;
    }

    var step = sequentialList[currentStepIndex];
    ui.run(function() {
        floatWin.floatLastAction.setText("Waiting Step " + step.stepNum + ": " + step.text);
    });

    var didClick = detectAndClick(step.text, false, floatWin);
    if (didClick) {
        currentStepIndex++;
        if (step.delay) {
            sleep(step.delay * 1000);
        }
    }
}

/**
 * Dual-Engine Detection: Level 1 Native UI -> Level 2 AI OCR
 */
function detectAndClick(keyword, exact, floatWin) {
    if (!keyword) return false;

    // Level 1: Native Accessibility Hierarchy (0ms lag)
    var nativeNode = findNativeNode(keyword, exact);
    if (nativeNode != null) {
        var b = nativeNode.bounds();
        click(b.centerX(), b.centerY());
        ui.run(function() {
            floatWin.floatLastAction.setText("Clicked: " + keyword);
        });
        return true;
    }

    // Level 2: AI OCR for canvas / Unity / Flutter games
    if (ocrEnabled) {
        var pt = findByAIOCR(keyword);
        if (pt != null) {
            click(pt.x, pt.y);
            ui.run(function() {
                floatWin.floatLastAction.setText("Clicked (OCR): " + keyword);
            });
            return true;
        }
    }

    return false;
}

function findNativeNode(keyword, exact) {
    try {
        var sel = exact ? text(keyword) : textContains(keyword);
        if (sel.exists()) return sel.findOnce();

        var descSel = exact ? desc(keyword) : descContains(keyword);
        if (descSel.exists()) return descSel.findOnce();
    } catch (e) {}
    return null;
}

function findByAIOCR(keyword) {
    try {
        var img = captureScreen();
        if (!img) return null;

        var ocrRes = null;
        if (typeof paddle !== 'undefined' && paddle.ocr) {
            ocrRes = paddle.ocr(img);
        } else if (typeof ocr !== 'undefined' && ocr.detect) {
            ocrRes = ocr.detect(img);
        }

        if (!ocrRes || ocrRes.length === 0) return null;

        var targetLower = keyword.toLowerCase();
        for (var i = 0; i < ocrRes.length; i++) {
            var item = ocrRes[i];
            var detected = (item.text || "").toLowerCase();

            if (detected.indexOf(targetLower) !== -1) {
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

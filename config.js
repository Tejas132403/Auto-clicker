/**
 * AUTOX.JS SMART AUTOMATION CONFIGURATION
 * 
 * Edit this file to add or change the texts and tasks you want
 * the bot to watch for and click automatically.
 */

var AppConfig = {
    // General Settings
    settings: {
        scanIntervalMs: 600,       // Interval between scans (600ms is balanced for speed & battery)
        defaultCooldownMs: 2500,   // Wait time after clicking a text before clicking it again
        useOcr: true,              // Enable on-device AI OCR for graphics/canvas/games
        ocrConfidenceThreshold: 0.6// Minimum OCR accuracy (0.0 to 1.0)
    },

    // -------------------------------------------------------------
    // 1. REACTIVE RULES (Independent triggers)
    // Whenever ANY of these texts appear on screen, the bot clicks them.
    // -------------------------------------------------------------
    reactiveTriggers: [
        {
            text: "Next",
            action: "click",
            cooldownMs: 2000,
            exactMatch: false // false = matches "Next Question", "Go Next", etc.
        },
        {
            text: "Continue",
            action: "click",
            cooldownMs: 2000,
            exactMatch: false
        },
        {
            text: "Submit",
            action: "click",
            cooldownMs: 3000,
            exactMatch: false
        },
        {
            text: "Claim",
            action: "click",
            cooldownMs: 4000,
            exactMatch: false
        },
        {
            text: "Confirm",
            action: "click",
            cooldownMs: 2500,
            exactMatch: false
        },
        {
            text: "Start",
            action: "click",
            cooldownMs: 3000,
            exactMatch: false
        },
        {
            text: "Accept",
            action: "click",
            cooldownMs: 3000,
            exactMatch: false
        }
    ],

    // -------------------------------------------------------------
    // 2. SEQUENTIAL TASKS (Step-by-step workflows)
    // Runs step 1 -> then waits for step 2 -> then step 3, etc.
    // Set 'enabled: true' to activate sequential mode instead of pure reactive.
    // -------------------------------------------------------------
    sequentialWorkflow: {
        enabled: false, // Set to true if you want strict step-by-step
        loopWorkflow: true,
        steps: [
            {
                stepName: "Step 1: Start Quiz",
                waitForText: "Start",
                action: "click",
                delayAfterMs: 1500
            },
            {
                stepName: "Step 2: Answer Question",
                waitForText: "Option A",
                action: "click",
                delayAfterMs: 1000
            },
            {
                stepName: "Step 3: Confirm Submission",
                waitForText: "Submit",
                action: "click",
                delayAfterMs: 2000
            },
            {
                stepName: "Step 4: Go to Next",
                waitForText: "Next",
                action: "click",
                delayAfterMs: 1500
            }
        ]
    }
};

// Export config if running in modular environment
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AppConfig;
}

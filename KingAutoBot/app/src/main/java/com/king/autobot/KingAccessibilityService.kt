package com.king.autobot

import android.accessibilityservice.AccessibilityService
import android.content.Intent
import android.util.Log
import android.view.accessibility.AccessibilityEvent
import com.king.autobot.ai.AnswerCacheManager
import com.king.autobot.ai.GeminiApiClient
import com.king.autobot.automation.ShakeMasterAutomator
import com.king.autobot.automation.UniversalAiAutomator

class KingAccessibilityService : AccessibilityService() {
    companion object {
        private const val TAG = "KingAccessibility"
        var instance: KingAccessibilityService? = null
        var isRunning: Boolean = false
        var currentMode: String = "QUIZ" // "QUIZ" or "UNIVERSAL"
    }

    private lateinit var shakeMasterAutomator: ShakeMasterAutomator
    private lateinit var universalAiAutomator: UniversalAiAutomator

    override fun onServiceConnected() {
        super.onServiceConnected()
        instance = this
        Log.d(TAG, "KingAccessibilityService connected!")

        AnswerCacheManager.init(applicationContext)
        shakeMasterAutomator = ShakeMasterAutomator(this)
        universalAiAutomator = UniversalAiAutomator(this)

        updateWidgetStatus("Service Ready! Tap START")
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        if (!isRunning) return
        if (event == null) return

        val currentPkg = event.packageName?.toString() ?: ""
        val rootNode = rootInActiveWindow ?: return

        when (currentMode) {
            "QUIZ" -> shakeMasterAutomator.onScreenUpdated(rootNode, currentPkg)
            "UNIVERSAL" -> universalAiAutomator.onScreenUpdated(rootNode, currentPkg)
        }
    }

    override fun onInterrupt() {
        Log.w(TAG, "KingAccessibilityService interrupted")
        isRunning = false
    }

    override fun onDestroy() {
        super.onDestroy()
        instance = null
        isRunning = false
    }

    fun updateWidgetStatus(status: String) {
        FloatingOverlayService.updateStatus(status)
    }
}

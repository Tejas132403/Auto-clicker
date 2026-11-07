package com.king.autobot

import android.accessibilityservice.AccessibilityService
import android.content.Intent
import android.util.Log
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import com.king.autobot.ai.AnswerCacheManager
import com.king.autobot.ai.GeminiApiClient
import com.king.autobot.automation.ShakeMasterAutomator
import com.king.autobot.automation.UniversalAiAutomator
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

class KingAccessibilityService : AccessibilityService() {
    companion object {
        private const val TAG = "KingAccessibility"
        var instance: KingAccessibilityService? = null
        var isRunning: Boolean = false
        var currentMode: String = "QUIZ" // "QUIZ" or "UNIVERSAL"
    }

    private lateinit var shakeMasterAutomator: ShakeMasterAutomator
    private lateinit var universalAiAutomator: UniversalAiAutomator
    private val serviceScope = CoroutineScope(Dispatchers.Main)
    private var scanJob: Job? = null

    override fun onServiceConnected() {
        super.onServiceConnected()
        instance = this
        Log.d(TAG, "KingAccessibilityService connected!")

        AnswerCacheManager.init(applicationContext)
        shakeMasterAutomator = ShakeMasterAutomator(this)
        universalAiAutomator = UniversalAiAutomator(this)

        updateWidgetStatus("Service Ready! Tap START")
    }

    private var lastProcessTime = 0L

    fun processScreen(root: AccessibilityNodeInfo, pkg: String) {
        val now = System.currentTimeMillis()
        if (now - lastProcessTime < 700) return
        lastProcessTime = now

        when (currentMode) {
            "QUIZ" -> shakeMasterAutomator.onScreenUpdated(root, pkg)
            "UNIVERSAL" -> universalAiAutomator.onScreenUpdated(root, pkg)
        }
    }

    fun startAutomation() {
        isRunning = true
        scanJob?.cancel()
        scanJob = serviceScope.launch {
            while (isRunning) {
                try {
                    val root = rootInActiveWindow
                    if (root != null) {
                        val pkg = root.packageName?.toString() ?: ""
                        processScreen(root, pkg)
                    }
                } catch (e: Exception) {
                    Log.e(TAG, "Error in periodic scan: ${e.message}")
                }
                delay(1000)
            }
        }
    }

    fun stopAutomation() {
        isRunning = false
        scanJob?.cancel()
        scanJob = null
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        if (!isRunning) return
        if (event == null) return

        val currentPkg = event.packageName?.toString() ?: ""
        val rootNode = rootInActiveWindow ?: return

        processScreen(rootNode, currentPkg)
    }

    override fun onInterrupt() {
        Log.w(TAG, "KingAccessibilityService interrupted")
        stopAutomation()
    }

    override fun onDestroy() {
        super.onDestroy()
        instance = null
        stopAutomation()
    }

    fun updateWidgetStatus(status: String) {
        FloatingOverlayService.updateStatus(status)
    }
}

package com.king.autobot.automation

import android.accessibilityservice.AccessibilityService
import android.util.Log
import android.view.accessibility.AccessibilityNodeInfo
import com.king.autobot.KingAccessibilityService
import com.king.autobot.ai.GeminiApiClient
import com.king.autobot.utils.GestureUtils
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import org.json.JSONObject

class UniversalAiAutomator(private val service: KingAccessibilityService) {
    companion object {
        private const val TAG = "UniversalAiAutomator"
    }

    private val scope = CoroutineScope(Dispatchers.Main)
    var userGoal: String = "Progress through the task, click continue/claim/next, and dismiss ads"
    private var isThinking = false

    // Cache of screen signature -> element index to click
    private val decisionCache = mutableMapOf<String, Int>()

    fun onScreenUpdated(rootNode: AccessibilityNodeInfo?, currentPkg: String) {
        if (rootNode == null || isThinking) return

        val clickableNodes = mutableListOf<AccessibilityNodeInfo>()
        collectClickableNodes(rootNode, clickableNodes)
        if (clickableNodes.isEmpty()) return

        // Create a unique signature of the screen layout
        val screenElements = clickableNodes.mapIndexed { idx, node ->
            val label = node.text?.toString() ?: node.contentDescription?.toString() ?: "element_$idx"
            val id = node.viewIdResourceName ?: "no_id"
            "[$idx] id='$id' text='$label'"
        }
        val screenSig = "$currentPkg:${screenElements.joinToString("|")}"

        // Check if we already know what to click on this screen
        val cachedTarget = decisionCache[screenSig]
        if (cachedTarget != null && cachedTarget in clickableNodes.indices) {
            Log.d(TAG, "[0ms Universal Cache] Clicking element #$cachedTarget on $currentPkg")
            service.updateWidgetStatus("Clicking cached element...")
            GestureUtils.clickNode(clickableNodes[cachedTarget])
            return
        }

        // Zero-Training: Ask Gemini Flash-Lite what to do
        isThinking = true
        service.updateWidgetStatus("AI Analyzing screen...")
        scope.launch {
            try {
                val screenSummary = screenElements.take(15).joinToString("\n")
                val decisionRaw = GeminiApiClient.decideUniversalAction(screenSummary, userGoal)

                if (decisionRaw != null) {
                    val jsonStart = decisionRaw.indexOf("{")
                    val jsonEnd = decisionRaw.lastIndexOf("}")
                    if (jsonStart != -1 && jsonEnd != -1) {
                        val json = JSONObject(decisionRaw.substring(jsonStart, jsonEnd + 1))
                        val action = json.optString("action", "click")

                        if (action == "click") {
                            val targetIdx = json.optInt("target_id", 0)
                            if (targetIdx in clickableNodes.indices) {
                                decisionCache[screenSig] = targetIdx
                                GestureUtils.clickNode(clickableNodes[targetIdx])
                                service.updateWidgetStatus("Action: Clicked #$targetIdx")
                            }
                        } else if (action == "back") {
                            service.performGlobalAction(AccessibilityService.GLOBAL_ACTION_BACK)
                            service.updateWidgetStatus("Action: Pressed Back")
                        }
                    }
                }
            } catch (e: Exception) {
                Log.e(TAG, "Error in Universal AI loop: ${e.message}")
            } finally {
                isThinking = false
            }
        }
    }

    private fun collectClickableNodes(node: AccessibilityNodeInfo, list: MutableList<AccessibilityNodeInfo>) {
        if (node.isClickable && (node.text != null || node.contentDescription != null)) {
            list.add(node)
        }
        for (i in 0 until node.childCount) {
            node.getChild(i)?.let { collectClickableNodes(it, list) }
        }
    }
}

package com.king.autobot.automation

import android.accessibilityservice.AccessibilityService
import android.content.Intent
import android.graphics.Rect
import android.net.Uri
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.view.accessibility.AccessibilityNodeInfo
import com.king.autobot.KingAccessibilityService
import com.king.autobot.ai.AnswerCacheManager
import com.king.autobot.ai.GeminiApiClient
import com.king.autobot.utils.GestureUtils
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import java.util.Locale

class ShakeMasterAutomator(private val service: KingAccessibilityService) {
    companion object {
        private const val TAG = "ShakeMasterAutomator"
        const val TARGET_PKG = "com.shake.master"
        val REDIRECT_PKGS = setOf(
            "com.android.vending",
            "com.android.chrome",
            "com.google.android.apps.messaging",
            "com.vivo.browser"
        )
        val CLOSE_WORDS = setOf("close", "skip", "dismiss", "no thanks", "x", "×", "✕")
    }

    private val handler = Handler(Looper.getMainLooper())
    private val scope = CoroutineScope(Dispatchers.Main)

    private var sameTaskCount = 0
    private var lastTaskSignature = ""
    private var isHandlingInstall = false

    fun onScreenUpdated(rootNode: AccessibilityNodeInfo?, currentPkg: String) {
        if (rootNode == null) return

        // 1. Redirect Shield: Instant dismissal of Play Store / Chrome
        if (REDIRECT_PKGS.contains(currentPkg)) {
            Log.d(TAG, "[SHIELD] Intercepted redirect to $currentPkg -> Executing BACK!")
            service.performGlobalAction(AccessibilityService.GLOBAL_ACTION_BACK)
            return
        }

        // 2. Ad Handling (AdActivity / fullscreen ad)
        if (currentPkg.contains("gms.ads") || isAdScreen(rootNode)) {
            dismissAd(rootNode)
            return
        }

        // Only process if Shake Master is active
        if (currentPkg != TARGET_PKG) return

        // 3. Check for Quiz Screen
        val questionNode = findQuestionNode(rootNode)
        if (questionNode != null) {
            val qText = questionNode.text?.toString()?.trim() ?: ""
            if (qText.length > 5) {
                handleQuizScreen(rootNode, qText)
                return
            }
        }

        // 4. Check for 'Add Bonus' / Completion button
        val bonusBtn = findButton(rootNode, setOf("add bonus", "bonus", "claim", "continue", "done", "next", "ok"))
        if (bonusBtn != null) {
            Log.d(TAG, "Tapping bonus/claim button: ${bonusBtn.text}")
            GestureUtils.clickNode(service, bonusBtn)
            return
        }

        // 5. Check for 'Watch Video' button
        val videoBtn = findButton(rootNode, setOf("watch video", "watch", "play video"))
        if (videoBtn != null) {
            Log.d(TAG, "Tapping watch video button")
            GestureUtils.clickNode(service, videoBtn)
            return
        }
    }

    private fun handleQuizScreen(rootNode: AccessibilityNodeInfo, qText: String) {
        val options = findOptionNodes(rootNode)
        if (options.isEmpty()) return

        val optTexts = options.mapNotNull { it.text?.toString()?.trim() }.filter { it.isNotEmpty() }
        val currentSig = "$qText|${optTexts.joinToString(",")}"

        // Track repeat attempts for Install Task detection
        if (currentSig == lastTaskSignature) {
            sameTaskCount++
            Log.d(TAG, "Question repeated $sameTaskCount times: '$qText'")
        } else {
            sameTaskCount = 1
            lastTaskSignature = currentSig
        }

        // If repeated 3 times, attempt 4 is an Install Task!
        if (sameTaskCount >= 3 && !isHandlingInstall) {
            Log.d(TAG, "Repeat threshold reached ($sameTaskCount). Triggering Install Task flow!")
            isHandlingInstall = true
            executeInstallTaskFlow(qText, options, optTexts)
            return
        }

        // Normal Quiz Answering: First check 0ms cache
        val cachedAns = AnswerCacheManager.lookup(qText)
        if (cachedAns != null) {
            val targetNode = findBestOptionNode(options, cachedAns)
            if (targetNode != null) {
                Log.d(TAG, "[0ms CACHE] Answering '$qText' -> '$cachedAns'")
                GestureUtils.clickNode(service, targetNode)
                service.updateWidgetStatus("Cached: $cachedAns")
                return
            }
        }

        // Cache Miss: Query Gemini Cloud API
        scope.launch {
            service.updateWidgetStatus("Thinking (Gemini)...")
            val aiAns = GeminiApiClient.askQuiz(qText, optTexts)
            if (aiAns != null) {
                AnswerCacheManager.saveAnswer(qText, aiAns)
                val targetNode = findBestOptionNode(options, aiAns)
                if (targetNode != null) {
                    Log.d(TAG, "[GEMINI ANSWER] Clicked: '$aiAns'")
                    GestureUtils.clickNode(service, targetNode)
                    service.updateWidgetStatus("Answered: $aiAns")
                }
            }
        }
    }

    private fun executeInstallTaskFlow(qText: String, options: List<AccessibilityNodeInfo>, optTexts: List<String>) {
        service.updateWidgetStatus("Install Task Flow...")
        // 1. Give answer
        val answer = AnswerCacheManager.lookup(qText) ?: optTexts.firstOrNull() ?: ""
        val targetNode = findBestOptionNode(options, answer)
        if (targetNode != null) GestureUtils.clickNode(service, targetNode)

        // 2. Wait 1.5s then tap 'Add Bonus'
        handler.postDelayed({
            val root = service.rootInActiveWindow ?: return@postDelayed
            val bonusBtn = findButton(root, setOf("add bonus", "bonus"))
            if (bonusBtn != null) GestureUtils.clickNode(service, bonusBtn)

            // 3. Go to Home Screen after ad starts
            handler.postDelayed({
                service.performGlobalAction(AccessibilityService.GLOBAL_ACTION_HOME)

                // 4. Wait 10 seconds (simulating dummy app open/wait)
                handler.postDelayed({
                    // 5. Open Recents overview
                    service.updateWidgetStatus("Resuming from Recents...")
                    service.performGlobalAction(AccessibilityService.GLOBAL_ACTION_RECENTS)

                    // 6. In Recents, tap center snapshot to resume Shake Master without cold restart
                    handler.postDelayed({
                        val displayMetrics = service.resources.displayMetrics
                        val cx = (displayMetrics.widthPixels / 2).toFloat()
                        val cy = (displayMetrics.heightPixels * 0.479f)

                        GestureUtils.tap(service, cx, cy) {
                            Log.d(TAG, "Tapped snapshot in Recents. Shake Master resumed!")
                            service.updateWidgetStatus("Resumed! Cutting ad...")

                            // 7. Cut ad and claim bonus
                            handler.postDelayed({
                                service.performGlobalAction(AccessibilityService.GLOBAL_ACTION_BACK)
                                isHandlingInstall = false
                                sameTaskCount = 0
                            }, 1500)
                        }
                    }, 1000)
                }, 10000)
            }, 3000)
        }, 1500)
    }

    private fun dismissAd(rootNode: AccessibilityNodeInfo) {
        val closeBtn = findCloseButton(rootNode)
        if (closeBtn != null) {
            Log.d(TAG, "Closing ad via close button node")
            GestureUtils.clickNode(service, closeBtn)
            return
        }

        // Tap top-right corner (1015, 130 on 1080x2400)
        val metrics = service.resources.displayMetrics
        val trX = metrics.widthPixels * 0.94f
        val trY = metrics.heightPixels * 0.054f
        GestureUtils.tap(service, trX, trY) {
            handler.postDelayed({
                service.performGlobalAction(AccessibilityService.GLOBAL_ACTION_BACK)
            }, 600)
        }
    }

    private fun isAdScreen(root: AccessibilityNodeInfo): Boolean {
        val list = mutableListOf<String>()
        collectAllText(root, list)
        return list.any { it.contains("reward in", true) || it.contains("ad", true) || it.contains("sponsored", true) }
    }

    private fun findCloseButton(root: AccessibilityNodeInfo): AccessibilityNodeInfo? {
        val nodes = mutableListOf<AccessibilityNodeInfo>()
        collectClickableNodes(root, nodes)
        for (n in nodes) {
            val t = (n.text?.toString() ?: n.contentDescription?.toString() ?: "").lowercase().trim()
            if (CLOSE_WORDS.contains(t) || t.startsWith("close") || t.startsWith("skip")) {
                return n
            }
        }
        return null
    }

    private fun findQuestionNode(root: AccessibilityNodeInfo): AccessibilityNodeInfo? {
        val allTexts = mutableListOf<AccessibilityNodeInfo>()
        collectTextNodes(root, allTexts)
        for (n in allTexts) {
            val resId = n.viewIdResourceName ?: ""
            if (resId.contains("tvQuestion")) return n
        }
        for (n in allTexts) {
            val t = n.text?.toString()?.trim() ?: ""
            if (t.endsWith("?") || t.length in 12..150) {
                return n
            }
        }
        return null
    }

    private fun findOptionNodes(root: AccessibilityNodeInfo): List<AccessibilityNodeInfo> {
        val textNodes = mutableListOf<AccessibilityNodeInfo>()
        collectTextNodes(root, textNodes)

        // 1. Direct match by id 'tvOptionText'
        val byId = textNodes.filter { it.viewIdResourceName?.contains("tvOptionText") == true }
        if (byId.isNotEmpty()) return byId

        // 2. Clickable items that contain text
        val clickable = mutableListOf<AccessibilityNodeInfo>()
        collectClickableNodes(root, clickable)
        val candidateNodes = mutableListOf<AccessibilityNodeInfo>()
        for (c in clickable) {
            val childTexts = mutableListOf<String>()
            collectAllText(c, childTexts)
            val fullText = childTexts.joinToString(" ").trim()
            if (fullText.isNotEmpty() && !fullText.lowercase().contains("bonus") && !fullText.lowercase().contains("video") && !fullText.lowercase().contains("task")) {
                candidateNodes.add(c)
            }
        }
        return candidateNodes
    }

    private fun findBestOptionNode(options: List<AccessibilityNodeInfo>, answer: String): AccessibilityNodeInfo? {
        val normAns = answer.lowercase().trim()
        for (opt in options) {
            val optT = opt.text?.toString()?.lowercase()?.trim() ?: ""
            val allOptText = mutableListOf<String>()
            opt.parent?.let { collectAllText(it, allOptText) } ?: collectAllText(opt, allOptText)
            val combined = allOptText.joinToString(" ").lowercase()

            if (optT == normAns || optT.contains(normAns) || normAns.contains(optT)) return opt
            if (combined.contains(normAns) || normAns.contains(combined)) return opt

            if (normAns.length == 1 && combined.contains("${normAns}.")) return opt
        }
        return options.firstOrNull()
    }

    private fun findButton(root: AccessibilityNodeInfo, words: Set<String>): AccessibilityNodeInfo? {
        val clickable = mutableListOf<AccessibilityNodeInfo>()
        collectClickableNodes(root, clickable)
        for (n in clickable) {
            val t = (n.text?.toString() ?: n.contentDescription?.toString() ?: "").lowercase().trim()
            if (words.any { t.contains(it) }) return n
        }
        return null
    }

    private fun collectClickableNodes(node: AccessibilityNodeInfo, list: MutableList<AccessibilityNodeInfo>) {
        if (node.isClickable) list.add(node)
        for (i in 0 until node.childCount) {
            node.getChild(i)?.let { collectClickableNodes(it, list) }
        }
    }

    private fun collectTextNodes(node: AccessibilityNodeInfo, list: MutableList<AccessibilityNodeInfo>) {
        if (!node.text.isNullOrEmpty()) list.add(node)
        for (i in 0 until node.childCount) {
            node.getChild(i)?.let { collectTextNodes(it, list) }
        }
    }

    private fun collectAllText(node: AccessibilityNodeInfo, list: MutableList<String>) {
        node.text?.toString()?.let { list.add(it) }
        node.contentDescription?.toString()?.let { list.add(it) }
        for (i in 0 until node.childCount) {
            node.getChild(i)?.let { collectAllText(it, list) }
        }
    }
}

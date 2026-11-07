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
    private var sameVideoCount = 0
    private var lastVideoSignature = ""
    private var isHandlingInstall = false

    fun onScreenUpdated(rootNode: AccessibilityNodeInfo?, currentPkg: String) {
        if (rootNode == null) return

        // 1. Redirect Shield: Instant dismissal of Play Store / Chrome
        if (REDIRECT_PKGS.contains(currentPkg)) {
            Log.d(TAG, "[SHIELD] Intercepted redirect to $currentPkg -> Executing BACK!")
            service.performGlobalAction(AccessibilityService.GLOBAL_ACTION_BACK)
            return
        }

        // If install flow is actively executing, let it finish uninterrupted
        if (isHandlingInstall) return

        // 2. Check for 'Add Bonus' / Completion button FIRST!
        val bonusBtn = findButton(rootNode, setOf("add bonus", "bonus", "claim", "continue", "done", "next", "ok"))
        if (bonusBtn != null) {
            Log.d(TAG, "Tapping bonus/claim button: ${bonusBtn.text}")
            service.updateWidgetStatus("Claiming Bonus...")
            GestureUtils.clickNode(service, bonusBtn)
            return
        }

        // 3. Ad Handling (AdActivity / fullscreen ad)
        if (currentPkg.contains("gms.ads") || isAdScreen(rootNode)) {
            dismissAd(rootNode)
            return
        }

        // Only process if Shake Master is active
        if (currentPkg != TARGET_PKG) return

        // 4. Check for active countdown timer ("Wait 10 sec...")
        if (isCountdownActive(rootNode)) {
            service.updateWidgetStatus("Waiting countdown timer...")
            return
        }

        // 5. Watch Video Screen Handling (Play Video / Final Video Install Task)
        val watchBtn = findWatchVideoButton(rootNode)
        if (watchBtn != null) {
            handleWatchVideoScreen(rootNode, watchBtn)
            return
        }

        // 6. Home Screen Navigation (if Quiz is finished, enter Watch Video)
        val watchCard = findWatchVideoCard(rootNode)
        if (watchCard != null && isQuizFinished(rootNode)) {
            Log.d(TAG, "Quiz finished! Entering Watch Video section...")
            service.updateWidgetStatus("Entering Watch Video...")
            GestureUtils.clickNode(service, watchCard)
            return
        }

        // 7. Check for Quiz Screen (must have 2+ options)
        val options = findOptionNodes(rootNode)
        if (options.size >= 2) {
            val questionNode = findQuestionNode(rootNode)
            if (questionNode != null) {
                val qText = questionNode.text?.toString()?.trim() ?: ""
                if (qText.length > 5) {
                    handleQuizScreen(rootNode, qText, options)
                    return
                }
            }
        }
    }

    private fun handleWatchVideoScreen(rootNode: AccessibilityNodeInfo, watchBtn: AccessibilityNodeInfo) {
        val isComplete = isWatchVideoComplete(rootNode)
        val pStr = getWatchProgressString(rootNode)

        // Track repeat progress on Video screen
        if (pStr.isNotEmpty() && pStr == lastVideoSignature) {
            sameVideoCount++
            Log.d(TAG, "Watch Video progress '$pStr' repeated $sameVideoCount times")
        } else {
            sameVideoCount = 1
            if (pStr.isNotEmpty()) lastVideoSignature = pStr
        }

        // If all video tasks are complete OR repeated 3 times -> FINAL VIDEO INSTALL TASK!
        if ((isComplete || sameVideoCount >= 3) && !isHandlingInstall) {
            Log.d(TAG, "[WATCH VIDEO] Complete ($pStr) / Repeat ($sameVideoCount) -> FINAL VIDEO INSTALL TASK!")
            service.updateWidgetStatus("Final Video Install Task...")

            // 1. Click final video button to trigger ad
            GestureUtils.clickNode(service, watchBtn)

            // 2. Run full install sequence (Home -> wait 10s -> Recents -> cut ad -> claim bonus)
            executeInstallSequence {
                Log.d(TAG, "[WATCH VIDEO] Install sequence finished!")
                sameVideoCount = 0
                lastVideoSignature = ""
            }
            return
        }

        // Normal video task: tap Play Video
        Log.d(TAG, "[WATCH VIDEO] Tapping Play Video ($pStr)...")
        service.updateWidgetStatus("Watching Video ($pStr)...")
        GestureUtils.clickNode(service, watchBtn)
    }

    private fun handleQuizScreen(rootNode: AccessibilityNodeInfo, qText: String, options: List<AccessibilityNodeInfo>) {
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

            // 1. Give answer
            val answer = AnswerCacheManager.lookup(qText) ?: optTexts.firstOrNull() ?: ""
            val targetNode = findBestOptionNode(options, answer)
            if (targetNode != null) GestureUtils.clickNode(service, targetNode)

            // 2. Wait 1.5s then tap 'Add Bonus' to trigger ad
            handler.postDelayed({
                val root = service.rootInActiveWindow
                if (root != null) {
                    val bonusBtn = findButton(root, setOf("add bonus", "bonus"))
                    if (bonusBtn != null) GestureUtils.clickNode(service, bonusBtn)
                }

                // 3. Execute full install sequence
                executeInstallSequence {
                    sameTaskCount = 0
                    lastTaskSignature = ""
                }
            }, 1500)
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

    private fun executeInstallSequence(onComplete: (() -> Unit)? = null) {
        service.updateWidgetStatus("Install Flow: Waiting Ad...")
        isHandlingInstall = true

        // 1. Wait 2.5s for ad to open, then go to Home screen
        handler.postDelayed({
            service.updateWidgetStatus("Install Flow: Home Screen...")
            service.performGlobalAction(AccessibilityService.GLOBAL_ACTION_HOME)

            // 2. Wait 10 seconds on home screen (simulating install wait)
            handler.postDelayed({
                service.updateWidgetStatus("Install Flow: Recents...")
                // 3. Open Recents overview
                service.performGlobalAction(AccessibilityService.GLOBAL_ACTION_RECENTS)

                // 4. In Recents, tap center snapshot to resume Shake Master without cold restart
                handler.postDelayed({
                    val displayMetrics = service.resources.displayMetrics
                    val cx = (displayMetrics.widthPixels / 2).toFloat()
                    val cy = (displayMetrics.heightPixels * 0.479f)

                    GestureUtils.tap(service, cx, cy) {
                        Log.d(TAG, "Tapped snapshot in Recents. Shake Master resumed!")
                        service.updateWidgetStatus("Resumed! Cutting ad...")

                        // 5. Cut ad
                        handler.postDelayed({
                            service.performGlobalAction(AccessibilityService.GLOBAL_ACTION_BACK)

                            // 6. Wait 1.2s to claim bonus if popup appears
                            handler.postDelayed({
                                val root = service.rootInActiveWindow
                                if (root != null) {
                                    val bonus = findButton(root, setOf("add bonus", "bonus", "claim", "continue", "done"))
                                    if (bonus != null) {
                                        GestureUtils.clickNode(service, bonus)
                                    }
                                }
                                isHandlingInstall = false
                                sameTaskCount = 0
                                sameVideoCount = 0
                                service.updateWidgetStatus("Install Task Complete!")
                                onComplete?.invoke()
                            }, 1200)
                        }, 1500)
                    }
                }, 1000)
            }, 10000)
        }, 2500)
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
        val combined = list.joinToString(" ").lowercase()
        if (combined.contains("bonus") || combined.contains("quiz") || combined.contains("option")) {
            return false
        }

        return list.any { raw ->
            val t = raw.lowercase().trim()
            t == "ad" ||
            t.startsWith("ad ") ||
            t.contains("advertisement") ||
            t.contains("sponsored") ||
            t.contains("video will end in")
        }
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
            if (t.contains("?") || t.contains("Free Fire") || (t.length in 15..120 && !t.contains("Click Below") && !t.contains("Bonus Coins"))) {
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

    private fun isCountdownActive(root: AccessibilityNodeInfo): Boolean {
        val texts = mutableListOf<String>()
        collectAllText(root, texts)
        return texts.any { it.contains("Wait", ignoreCase = true) && it.contains("sec", ignoreCase = true) }
    }

    private fun getWatchProgressString(root: AccessibilityNodeInfo): String {
        val nodes = mutableListOf<AccessibilityNodeInfo>()
        collectTextNodes(root, nodes)
        val rem = nodes.firstOrNull { it.viewIdResourceName?.contains("progress_remaining_count") == true }?.text?.toString()?.replace("/", "")?.trim() ?: ""
        val tot = nodes.firstOrNull { it.viewIdResourceName?.contains("progress_count") == true }?.text?.toString()?.trim() ?: ""
        if (rem.isNotEmpty() && tot.isNotEmpty()) {
            return "$rem/$tot"
        }
        for (n in nodes) {
            val t = n.text?.toString() ?: ""
            val m = Regex("(\\d+)\\s*/\\s*(\\d+)").find(t)
            if (m != null) return m.value
        }
        return ""
    }

    private fun isWatchVideoComplete(root: AccessibilityNodeInfo): Boolean {
        val pStr = getWatchProgressString(root)
        if (pStr.isNotEmpty()) {
            val parts = pStr.split("/")
            if (parts.size == 2) {
                val cur = parts[0].trim().toIntOrNull()
                val tot = parts[1].trim().toIntOrNull()
                if (cur != null && tot != null && cur >= tot && tot > 0) return true
            }
        }
        val texts = mutableListOf<String>()
        collectAllText(root, texts)
        return texts.any {
            val l = it.lowercase().trim()
            l.contains("0 more videos") ||
            l.contains("watch 0 more") ||
            l.contains("all videos completed") ||
            l.contains("come back tomorrow") ||
            l.contains("limit reached")
        }
    }

    private fun findWatchVideoButton(root: AccessibilityNodeInfo): AccessibilityNodeInfo? {
        val clickable = mutableListOf<AccessibilityNodeInfo>()
        collectClickableNodes(root, clickable)
        for (n in clickable) {
            val resId = n.viewIdResourceName ?: ""
            if (resId.contains("btn_watch_now")) return n
            val t = (n.text?.toString() ?: n.contentDescription?.toString() ?: "").lowercase().trim()
            if (t == "play video" || t == "watch video" || t == "watch now") return n
        }
        return null
    }

    private fun findWatchVideoCard(root: AccessibilityNodeInfo): AccessibilityNodeInfo? {
        val clickable = mutableListOf<AccessibilityNodeInfo>()
        collectClickableNodes(root, clickable)
        for (n in clickable) {
            val resId = n.viewIdResourceName ?: ""
            if (resId.contains("clWatchVideo")) return n
            val t = (n.text?.toString() ?: n.contentDescription?.toString() ?: "").lowercase().trim()
            if (t.contains("watch video") || t.contains("watch & earn")) return n
        }
        return null
    }

    private fun isQuizFinished(root: AccessibilityNodeInfo): Boolean {
        val texts = mutableListOf<String>()
        collectAllText(root, texts)
        return texts.any {
            it.contains("25/25") || it.contains("0/25") || it.contains("quiz completed", ignoreCase = true)
        }
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

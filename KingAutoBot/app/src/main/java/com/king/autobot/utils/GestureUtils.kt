package com.king.autobot.utils

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.graphics.Path
import android.graphics.Rect
import android.util.Log
import android.view.accessibility.AccessibilityNodeInfo

object GestureUtils {
    private const val TAG = "GestureUtils"

    @Volatile
    private var isGestureRunning = false

    fun tap(service: AccessibilityService, x: Float, y: Float, callback: (() -> Unit)? = null) {
        if (isGestureRunning) {
            Log.w(TAG, "Gesture already in progress, skipping tap at ($x, $y)")
            return
        }
        isGestureRunning = true

        val path = Path().apply {
            moveTo(x, y)
        }
        val stroke = GestureDescription.StrokeDescription(path, 0, 80)
        val gesture = GestureDescription.Builder().addStroke(stroke).build()

        service.dispatchGesture(gesture, object : AccessibilityService.GestureResultCallback() {
            override fun onCompleted(gestureDescription: GestureDescription?) {
                super.onCompleted(gestureDescription)
                isGestureRunning = false
                callback?.invoke()
            }

            override fun onCancelled(gestureDescription: GestureDescription?) {
                super.onCancelled(gestureDescription)
                isGestureRunning = false
                Log.w(TAG, "Tap at ($x, $y) cancelled")
            }
        }, null)
    }

    fun swipe(
        service: AccessibilityService,
        x1: Float, y1: Float,
        x2: Float, y2: Float,
        durationMs: Long = 300,
        callback: (() -> Unit)? = null
    ) {
        if (isGestureRunning) return
        isGestureRunning = true

        val path = Path().apply {
            moveTo(x1, y1)
            lineTo(x2, y2)
        }
        val stroke = GestureDescription.StrokeDescription(path, 0, durationMs)
        val gesture = GestureDescription.Builder().addStroke(stroke).build()

        service.dispatchGesture(gesture, object : AccessibilityService.GestureResultCallback() {
            override fun onCompleted(gestureDescription: GestureDescription?) {
                super.onCompleted(gestureDescription)
                isGestureRunning = false
                callback?.invoke()
            }

            override fun onCancelled(gestureDescription: GestureDescription?) {
                super.onCancelled(gestureDescription)
                isGestureRunning = false
                Log.w(TAG, "Swipe from ($x1,$y1) to ($x2,$y2) cancelled")
            }
        }, null)
    }

    fun clickNode(service: AccessibilityService, node: AccessibilityNodeInfo): Boolean {
        // 1. Direct accessibility click action (instant, reliable, cannot conflict)
        if (node.isClickable && node.performAction(AccessibilityNodeInfo.ACTION_CLICK)) {
            Log.d(TAG, "Direct ACTION_CLICK succeeded on: ${node.text} / ${node.viewIdResourceName}")
            return true
        }

        // 2. Clickable parent
        var parent = node.parent
        while (parent != null) {
            if (parent.isClickable && parent.performAction(AccessibilityNodeInfo.ACTION_CLICK)) {
                Log.d(TAG, "Parent ACTION_CLICK succeeded on: ${parent.viewIdResourceName}")
                return true
            }
            parent = parent.parent
        }

        // 3. Fallback to physical coordinate tap dispatch
        val rect = Rect()
        node.getBoundsInScreen(rect)
        if (rect.width() > 0 && rect.height() > 0) {
            val cx = rect.centerX().toFloat()
            val cy = rect.centerY().toFloat()
            Log.d(TAG, "Dispatching coordinate tap at ($cx, $cy)")
            tap(service, cx, cy)
            return true
        }
        return false
    }

    fun getNodeBounds(node: AccessibilityNodeInfo): Rect {
        val rect = Rect()
        node.getBoundsInScreen(rect)
        return rect
    }
}

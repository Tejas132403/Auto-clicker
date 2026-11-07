package com.king.autobot.utils

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.graphics.Path
import android.graphics.Rect
import android.util.Log
import android.view.accessibility.AccessibilityNodeInfo

object GestureUtils {
    private const val TAG = "GestureUtils"

    fun tap(service: AccessibilityService, x: Float, y: Float, callback: (() -> Unit)? = null) {
        val path = Path().apply {
            moveTo(x, y)
        }
        val stroke = GestureDescription.StrokeDescription(path, 0, 50)
        val gesture = GestureDescription.Builder().addStroke(stroke).build()

        service.dispatchGesture(gesture, object : AccessibilityService.GestureResultCallback() {
            override fun onCompleted(gestureDescription: GestureDescription?) {
                super.onCompleted(gestureDescription)
                callback?.invoke()
            }

            override fun onCancelled(gestureDescription: GestureDescription?) {
                super.onCancelled(gestureDescription)
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
        val path = Path().apply {
            moveTo(x1, y1)
            lineTo(x2, y2)
        }
        val stroke = GestureDescription.StrokeDescription(path, 0, durationMs)
        val gesture = GestureDescription.Builder().addStroke(stroke).build()

        service.dispatchGesture(gesture, object : AccessibilityService.GestureResultCallback() {
            override fun onCompleted(gestureDescription: GestureDescription?) {
                super.onCompleted(gestureDescription)
                callback?.invoke()
            }

            override fun onCancelled(gestureDescription: GestureDescription?) {
                super.onCancelled(gestureDescription)
                Log.w(TAG, "Swipe from ($x1,$y1) to ($x2,$y2) cancelled")
            }
        }, null)
    }

    fun clickNode(node: AccessibilityNodeInfo): Boolean {
        // Try direct click
        if (node.isClickable && node.performAction(AccessibilityNodeInfo.ACTION_CLICK)) {
            return true
        }
        // Try clickable parent
        var parent = node.parent
        while (parent != null) {
            if (parent.isClickable && parent.performAction(AccessibilityNodeInfo.ACTION_CLICK)) {
                return true
            }
            parent = parent.parent
        }
        return false
    }

    fun getNodeBounds(node: AccessibilityNodeInfo): Rect {
        val rect = Rect()
        node.getBoundsInScreen(rect)
        return rect
    }
}

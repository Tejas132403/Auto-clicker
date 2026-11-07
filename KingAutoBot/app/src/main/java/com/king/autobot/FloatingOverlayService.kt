package com.king.autobot

import android.app.Service
import android.content.Intent
import android.graphics.PixelFormat
import android.os.Build
import android.os.IBinder
import android.view.Gravity
import android.view.LayoutInflater
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.widget.Button
import android.widget.TextView
import android.widget.Toast

class FloatingOverlayService : Service() {
    companion object {
        private var instance: FloatingOverlayService? = null

        fun updateStatus(status: String) {
            instance?.tvStatus?.text = status
        }
    }

    private lateinit var windowManager: WindowManager
    private lateinit var floatingView: View
    private lateinit var tvStatus: TextView
    private lateinit var btnStart: Button
    private lateinit var btnStop: Button
    private lateinit var btnMode: Button

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        instance = this

        windowManager = getSystemService(WINDOW_SERVICE) as WindowManager
        floatingView = LayoutInflater.from(this).inflate(R.layout.layout_floating_widget, null)

        val layoutParamsType = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
        } else {
            WindowManager.LayoutParams.TYPE_PHONE
        }

        val params = WindowManager.LayoutParams(
            WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.WRAP_CONTENT,
            layoutParamsType,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
            PixelFormat.TRANSLUCENT
        ).apply {
            gravity = Gravity.TOP or Gravity.START
            x = 50
            y = 200
        }

        windowManager.addView(floatingView, params)

        tvStatus = floatingView.findViewById(R.id.tv_status)
        btnStart = floatingView.findViewById(R.id.btn_start)
        btnStop = floatingView.findViewById(R.id.btn_stop)
        btnMode = floatingView.findViewById(R.id.btn_mode)

        btnStart.setOnClickListener {
            val a11y = KingAccessibilityService.instance
            if (a11y != null) {
                a11y.startAutomation()
                tvStatus.text = "Running (${KingAccessibilityService.currentMode})..."
            } else {
                tvStatus.text = "Error: Enable Accessibility!"
                Toast.makeText(this, "Please enable 'King AutoBot' in Accessibility Settings!", Toast.LENGTH_LONG).show()
                val intent = Intent(android.provider.Settings.ACTION_ACCESSIBILITY_SETTINGS).apply {
                    flags = Intent.FLAG_ACTIVITY_NEW_TASK
                }
                startActivity(intent)
            }
        }

        btnStop.setOnClickListener {
            KingAccessibilityService.instance?.stopAutomation()
            tvStatus.text = "Stopped"
        }

        val btnCollapse = floatingView.findViewById<TextView>(R.id.btn_collapse)
        val btnClose = floatingView.findViewById<TextView>(R.id.btn_close_widget)
        val controlsContainer = floatingView.findViewById<View>(R.id.controls_container)

        btnCollapse.setOnClickListener {
            if (controlsContainer.visibility == View.VISIBLE) {
                controlsContainer.visibility = View.GONE
                btnCollapse.text = "➕"
            } else {
                controlsContainer.visibility = View.VISIBLE
                btnCollapse.text = "➖"
            }
        }

        btnClose.setOnClickListener {
            KingAccessibilityService.instance?.stopAutomation()
            stopSelf()
        }

        btnMode.setOnClickListener {
            if (KingAccessibilityService.currentMode == "QUIZ") {
                KingAccessibilityService.currentMode = "UNIVERSAL"
                btnMode.text = "UNIVERSAL"
                tvStatus.text = "Mode: Universal AI"
            } else {
                KingAccessibilityService.currentMode = "QUIZ"
                btnMode.text = "QUIZ"
                tvStatus.text = "Mode: Shake Master"
            }
        }

        // Draggable Handle
        val dragHandle = floatingView.findViewById<View>(R.id.drag_handle)
        var initialX = 0
        var initialY = 0
        var initialTouchX = 0f
        var initialTouchY = 0f

        dragHandle.setOnTouchListener { _, event ->
            when (event.action) {
                MotionEvent.ACTION_DOWN -> {
                    initialX = params.x
                    initialY = params.y
                    initialTouchX = event.rawX
                    initialTouchY = event.rawY
                    true
                }
                MotionEvent.ACTION_MOVE -> {
                    params.x = initialX + (event.rawX - initialTouchX).toInt()
                    params.y = initialY + (event.rawY - initialTouchY).toInt()
                    windowManager.updateViewLayout(floatingView, params)
                    true
                }
                else -> false
            }
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        KingAccessibilityService.instance?.stopAutomation()
        if (::floatingView.isInitialized) {
            try {
                windowManager.removeView(floatingView)
            } catch (e: Exception) {
                // View might already be detached
            }
        }
        instance = null
    }
}

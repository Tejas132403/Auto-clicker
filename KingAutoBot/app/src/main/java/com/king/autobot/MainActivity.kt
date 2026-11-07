package com.king.autobot

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.king.autobot.ai.AnswerCacheManager
import com.king.autobot.ai.GeminiApiClient

class MainActivity : AppCompatActivity() {

    private lateinit var etApiKey: EditText
    private lateinit var tvCacheCount: TextView
    private lateinit var btnEnableAccessibility: Button
    private lateinit var btnEnableOverlay: Button
    private lateinit var btnLaunchWidget: Button
    private lateinit var btnStopBot: Button

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        etApiKey = findViewById(R.id.et_api_key)
        tvCacheCount = findViewById(R.id.tv_cache_count)
        btnEnableAccessibility = findViewById(R.id.btn_enable_accessibility)
        btnEnableOverlay = findViewById(R.id.btn_enable_overlay)
        btnLaunchWidget = findViewById(R.id.btn_launch_widget)
        btnStopBot = findViewById(R.id.btn_stop_bot)

        // Initialize cache
        AnswerCacheManager.init(this)
        tvCacheCount.text = "Cached Answers Ready: ${AnswerCacheManager.getCacheCount()} questions"

        // Load saved API Key
        val prefs = getSharedPreferences("king_bot_prefs", Context.MODE_PRIVATE)
        val savedKey = prefs.getString("gemini_key", "") ?: ""
        etApiKey.setText(savedKey)
        GeminiApiClient.apiKey = savedKey

        btnEnableAccessibility.setOnClickListener {
            val intent = Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)
            startActivity(intent)
            Toast.makeText(this, "Enable 'King AutoBot' in Accessibility", Toast.LENGTH_LONG).show()
        }

        btnEnableOverlay.setOnClickListener {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M && !Settings.canDrawOverlays(this)) {
                val intent = Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:$packageName"))
                startActivity(intent)
            } else {
                Toast.makeText(this, "Overlay permission already granted!", Toast.LENGTH_SHORT).show()
            }
        }

        btnLaunchWidget.setOnClickListener {
            val key = etApiKey.text.toString().trim()
            if (key.isNotEmpty()) {
                prefs.edit().putString("gemini_key", key).apply()
                GeminiApiClient.apiKey = key
            }

            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M && !Settings.canDrawOverlays(this)) {
                Toast.makeText(this, "Please enable Floating Overlay permission first", Toast.LENGTH_LONG).show()
                return@setOnClickListener
            }

            val intent = Intent(this, FloatingOverlayService::class.java)
            startService(intent)
            Toast.makeText(this, "Floating Controller Launched! Open any app and tap START", Toast.LENGTH_LONG).show()
            moveTaskToBack(true)
        }

        btnStopBot.setOnClickListener {
            KingAccessibilityService.instance?.stopAutomation()
            stopService(Intent(this, FloatingOverlayService::class.java))
            Toast.makeText(this, "Bot Stopped & Floating Controller Closed!", Toast.LENGTH_SHORT).show()
        }
    }

    override fun onResume() {
        super.onResume()
        tvCacheCount.text = "Cached Answers Ready: ${AnswerCacheManager.getCacheCount()} questions"
    }
}

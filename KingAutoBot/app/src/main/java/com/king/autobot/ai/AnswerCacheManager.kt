package com.king.autobot.ai

import android.content.Context
import android.util.Log
import org.json.JSONObject
import java.io.File

object AnswerCacheManager {
    private const val TAG = "AnswerCache"
    private val memoryCache = mutableMapOf<String, String>()
    private lateinit var cacheFile: File

    fun init(context: Context) {
        cacheFile = File(context.filesDir, "quiz_answers_runtime.json")

        // 1. Load bundled pre-trained assets
        try {
            val assetStream = context.assets.open("quiz_answers.json")
            val jsonStr = assetStream.bufferedReader().use { it.readText() }
            val json = JSONObject(jsonStr)
            val keys = json.keys()
            while (keys.hasNext()) {
                val k = keys.next()
                val v = json.optString(k, "")
                if (v.isNotEmpty()) {
                    memoryCache[normalize(k)] = v.trim()
                }
            }
            Log.d(TAG, "Loaded ${memoryCache.size} bundled answers from assets")
        } catch (e: Exception) {
            Log.e(TAG, "Error loading bundled assets: ${e.message}")
        }

        // 2. Load runtime cached answers
        if (cacheFile.exists()) {
            try {
                val jsonStr = cacheFile.readText()
                val json = JSONObject(jsonStr)
                val keys = json.keys()
                var runtimeCount = 0
                while (keys.hasNext()) {
                    val k = keys.next()
                    val v = json.optString(k, "")
                    if (v.isNotEmpty()) {
                        memoryCache[normalize(k)] = v.trim()
                        runtimeCount++
                    }
                }
                Log.d(TAG, "Loaded $runtimeCount runtime answers from disk (Total: ${memoryCache.size})")
            } catch (e: Exception) {
                Log.e(TAG, "Error reading runtime cache: ${e.message}")
            }
        }
    }

    fun normalize(q: String): String {
        return q.lowercase().replace(Regex("[^a-z0-9]"), "").trim()
    }

    fun lookup(question: String): String? {
        val norm = normalize(question)
        // Direct match
        memoryCache[norm]?.let { return it }

        // Substring / fuzzy match
        for ((k, v) in memoryCache) {
            if (k.length > 10 && (norm.contains(k) || k.contains(norm))) {
                return v
            }
        }
        return null
    }

    fun saveAnswer(question: String, answer: String) {
        val norm = normalize(question)
        memoryCache[norm] = answer.trim()

        try {
            val json = if (cacheFile.exists()) {
                JSONObject(cacheFile.readText())
            } else {
                JSONObject()
            }
            json.put(norm, answer.trim())
            cacheFile.writeText(json.toString(2))
            Log.d(TAG, "Saved new answer to disk! Total cache size: ${memoryCache.size}")
        } catch (e: Exception) {
            Log.e(TAG, "Error saving answer: ${e.message}")
        }
    }

    fun getCacheCount(): Int = memoryCache.size
}

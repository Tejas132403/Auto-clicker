package com.king.autobot.ai

import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.TimeUnit

object GeminiApiClient {
    private const val TAG = "GeminiApi"
    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(10, TimeUnit.SECONDS)
        .build()

    var apiKey: String = ""

    suspend fun askQuiz(question: String, options: List<String>): String? = withContext(Dispatchers.IO) {
        if (apiKey.isBlank()) {
            Log.e(TAG, "Gemini API key is missing!")
            return@withContext null
        }

        val prompt = """
            You are an accurate quiz answering engine.
            Question: "$question"
            Options:
            ${options.mapIndexed { idx, opt -> "${idx + 1}. $opt" }.joinToString("\n")}

            Return ONLY the exact text of the correct option. Do not explain.
        """.trimIndent()

        val responseText = callGemini(prompt) ?: return@withContext null
        val cleaned = responseText.trim().lowercase()

        // Match against options
        for (opt in options) {
            val optClean = opt.trim().lowercase()
            if (cleaned == optClean || cleaned.contains(optClean) || optClean.contains(cleaned)) {
                return@withContext opt
            }
        }
        return@withContext options.firstOrNull()
    }

    suspend fun decideUniversalAction(screenSummary: String, goal: String): String? = withContext(Dispatchers.IO) {
        if (apiKey.isBlank()) return@withContext null

        val prompt = """
            You are an autonomous mobile automation agent.
            Current Screen Elements:
            $screenSummary

            User Goal: $goal

            Decide the single best action to advance the goal.
            Format your response as JSON:
            {"action": "click", "target_id": "element_id_or_index"} or {"action": "back"} or {"action": "wait"}
        """.trimIndent()

        return@withContext callGemini(prompt)
    }

    private fun callGemini(prompt: String): String? {
        val url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-lite-latest:generateContent?key=$apiKey"
        val jsonBody = JSONObject().apply {
            val contents = JSONArray().apply {
                val contentObj = JSONObject().apply {
                    val parts = JSONArray().apply {
                        put(JSONObject().apply { put("text", prompt) })
                    }
                    put("parts", parts)
                }
                put(contentObj)
            }
            put("contents", contents)
        }

        val request = Request.Builder()
            .url(url)
            .post(jsonBody.toString().toRequestBody("application/json".toMediaType()))
            .build()

        try {
            client.newCall(request).execute().use { resp ->
                if (!resp.isSuccessful) {
                    Log.e(TAG, "Gemini request failed: ${resp.code} ${resp.message}")
                    return null
                }
                val raw = resp.body?.string() ?: return null
                val root = JSONObject(raw)
                val candidates = root.optJSONArray("candidates") ?: return null
                if (candidates.length() == 0) return null
                val content = candidates.getJSONObject(0).optJSONObject("content") ?: return null
                val parts = content.optJSONArray("parts") ?: return null
                if (parts.length() == 0) return null
                return parts.getJSONObject(0).optString("text", "")
            }
        } catch (e: Exception) {
            Log.e(TAG, "Error executing Gemini call: ${e.message}")
            return null
        }
    }
}

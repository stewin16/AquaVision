package com.rahul.aquavision.utils

import android.content.Context
import android.util.Log
import org.json.JSONObject
import java.io.IOException

/**
 * Resolves scientific fish names to Indian common names.
 * Loads a static JSON mapping from assets/fish_names_india.json
 * for fully offline operation.
 *
 * Usage:
 *   FishNameResolver.init(context)  // Call once in Application or Fragment
 *   val name = FishNameResolver.resolve("Labeo rohita")  // → "Rohu"
 *   val name = FishNameResolver.resolveAuto("Labeo rohita", context) // → auto-detect language
 */
object FishNameResolver {

    private const val TAG = "FishNameResolver"
    private const val ASSET_FILE = "fish_names_india.json"

    private var nameMap: Map<String, DisplayInfo>? = null

    data class DisplayInfo(
        val displayName: String,
        val hindi: String? = null,
        val bengali: String? = null,
        val tamil: String? = null,
        val telugu: String? = null,
        val marathi: String? = null,
        val malayalam: String? = null,
        val kannada: String? = null,
        val gujarati: String? = null
    )

    /**
     * Initialize the resolver by loading the mapping from assets.
     * Safe to call multiple times — only loads once.
     */
    fun init(context: Context) {
        if (nameMap != null) return

        try {
            val json = context.assets.open(ASSET_FILE)
                .bufferedReader().use { it.readText() }
            val root = JSONObject(json)
            val map = mutableMapOf<String, DisplayInfo>()

            root.keys().forEach { sciName ->
                val obj = root.getJSONObject(sciName)
                val names = obj.optJSONObject("names")
                map[sciName] = DisplayInfo(
                    displayName = obj.getString("display_name"),
                    hindi = names?.optString("hindi")?.takeIf { it.isNotEmpty() },
                    bengali = names?.optString("bengali")?.takeIf { it.isNotEmpty() },
                    tamil = names?.optString("tamil")?.takeIf { it.isNotEmpty() },
                    telugu = names?.optString("telugu")?.takeIf { it.isNotEmpty() },
                    marathi = names?.optString("marathi")?.takeIf { it.isNotEmpty() },
                    malayalam = names?.optString("malayalam")?.takeIf { it.isNotEmpty() },
                    kannada = names?.optString("kannada")?.takeIf { it.isNotEmpty() },
                    gujarati = names?.optString("gujarati")?.takeIf { it.isNotEmpty() }
                )
            }
            nameMap = map
            Log.d(TAG, "Loaded ${map.size} species name mappings")
        } catch (e: IOException) {
            // File doesn't exist yet — that's fine, will use raw model labels
            Log.w(TAG, "No $ASSET_FILE found in assets — using raw model labels")
            nameMap = emptyMap()
        }
    }

    /**
     * Resolves a scientific name to a display-friendly Indian name.
     * Falls back to the original name if no mapping exists.
     *
     * @param modelLabel  The label from the YOLO model output
     * @param language    Target language: "hindi", "bengali", "tamil", "telugu", etc.
     * @return Display-friendly name
     */
    fun resolve(modelLabel: String, language: String = "english"): String {
        val info = nameMap?.get(modelLabel) ?: return modelLabel
        return when (language) {
            "hindi" -> info.hindi ?: info.displayName
            "bengali" -> info.bengali ?: info.displayName
            "tamil" -> info.tamil ?: info.displayName
            "telugu" -> info.telugu ?: info.displayName
            "marathi" -> info.marathi ?: info.displayName
            "malayalam" -> info.malayalam ?: info.displayName
            "kannada" -> info.kannada ?: info.displayName
            "gujarati" -> info.gujarati ?: info.displayName
            else -> info.displayName
        }
    }

    /**
     * Auto-resolves based on the device's current locale.
     * E.g., if the phone is set to Hindi, returns the Hindi name.
     */
    fun resolveAuto(modelLabel: String, context: Context): String {
        val locale = context.resources.configuration.locales[0].language
        return resolve(modelLabel, when (locale) {
            "hi" -> "hindi"
            "bn" -> "bengali"
            "ta" -> "tamil"
            "te" -> "telugu"
            "mr" -> "marathi"
            "ml" -> "malayalam"
            "kn" -> "kannada"
            "gu" -> "gujarati"
            else -> "english"
        })
    }

    /**
     * Check if the resolver has a mapping loaded.
     */
    fun isLoaded(): Boolean = nameMap != null && nameMap!!.isNotEmpty()
}

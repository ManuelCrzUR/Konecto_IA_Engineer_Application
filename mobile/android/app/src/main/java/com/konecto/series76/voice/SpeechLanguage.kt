package com.konecto.series76.voice

import com.konecto.series76.chat.plainText
import java.util.Locale

private val SPANISH_WORDS = setOf(
    "el", "la", "los", "las", "de", "del", "que", "para", "con", "es", "hola", "gracias", "cual", "cuál",
    "qué", "un", "una", "por", "necesito", "quiero", "tiene", "tengo", "actuador", "voltaje",
)
private val SPANISH_CHARS = Regex("[áéíóúñ¿¡ÁÉÍÓÚÑ]")
private val WORD_SPLIT = Regex("[^\\p{L}]+")

/** Spanish when the text has Spanish letters or common Spanish words, otherwise English (en-US). */
fun speechLocale(text: String): Locale {
    val spanish = SPANISH_CHARS.containsMatchIn(text) ||
        text.lowercase().split(WORD_SPLIT).any { it in SPANISH_WORDS }
    return if (spanish) Locale.forLanguageTag("es") else Locale.US
}

/** The backend's [language] ("es"/"en") when present, otherwise guessed from [text]. */
fun resolveLocale(language: String?, text: String): Locale =
    when (language) {
        "es" -> Locale.forLanguageTag("es")
        "en" -> Locale.US
        else -> speechLocale(text)
    }

private val LIST_MARKER = Regex("^\\s*(?:[-*•]|\\d+[.)])\\s+")
private val HEADING = Regex("^\\s*#+\\s*")

/** Text for text-to-speech: no markdown decoration, no table rows. Digits are never touched. */
fun speakableText(answer: String): String =
    plainText(answer).lines()
        .filter { '|' !in it }
        .map { it.replace(HEADING, "").replace(LIST_MARKER, "").replace("`", "").trim() }
        .filter { it.isNotEmpty() }
        .joinToString("\n")

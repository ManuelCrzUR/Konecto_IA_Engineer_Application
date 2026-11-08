package com.konecto.series76.voice

private val BOUNDARY = Regex("(?<=[.?!])\\s+|\\n+")

/**
 * Splits speakable text into sentences for pipelined synthesis. A boundary is `.`, `?` or `!` followed
 * by whitespace, or a line break; a dot inside a token ("764A00-11300000/A", "1.1") has no whitespace
 * after it, so it never splits. Spanish openers (¿ ¡) stay with the sentence they open.
 */
fun splitSentences(text: String): List<String> =
    text.split(BOUNDARY).map { it.trim() }.filter { it.isNotEmpty() }

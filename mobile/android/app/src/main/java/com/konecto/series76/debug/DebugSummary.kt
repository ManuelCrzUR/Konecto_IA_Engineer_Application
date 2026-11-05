package com.konecto.series76.debug

/** Header chip text, for example "2 turns · 3 calls". Counts the loaded turns and their tool traces. */
fun summarize(turns: List<DebugTurn>): String {
    val calls = turns.sumOf { it.traces.size }
    return "${plural(turns.size, "turn")} · ${plural(calls, "call")}"
}

private fun plural(count: Int, word: String): String = if (count == 1) "1 $word" else "$count ${word}s"

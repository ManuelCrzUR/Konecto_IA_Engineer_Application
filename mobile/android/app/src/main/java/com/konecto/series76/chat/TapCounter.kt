package com.konecto.series76.chat

/**
 * Fires (returns true from [tap]) when [required] taps happen within [windowMs].
 * Pure: the clock is injected (milliseconds, monotonic).
 */
class TapCounter(
    private val required: Int = 5,
    private val windowMs: Long = 3_000,
    private val clock: () -> Long = { System.nanoTime() / 1_000_000 },
) {
    private val taps = ArrayDeque<Long>()

    fun tap(): Boolean {
        val now = clock()
        taps.addLast(now)
        while (taps.isNotEmpty() && now - taps.first() > windowMs) taps.removeFirst()
        if (taps.size >= required) {
            taps.clear()
            return true
        }
        return false
    }
}

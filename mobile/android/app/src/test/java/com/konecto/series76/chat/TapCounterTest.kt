package com.konecto.series76.chat

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class TapCounterTest {
    private var now = 0L
    private val counter = TapCounter(clock = { now })

    @Test fun fiveQuickTapsFireOnce() {
        val fired = (1..5).map { now += 500; counter.tap() }
        assertEquals(listOf(false, false, false, false, true), fired)
        assertFalse(counter.tap()) // counter reset after firing
    }

    @Test fun slowTapsDoNotFire() {
        repeat(20) { now += 1_000; assertFalse(counter.tap().also { }) }
        // 1 tap/s: 4 taps fit in window, never 5 within 3 s
    }

    @Test fun fiveTapsSpanningMoreThanWindowDoNotFire() {
        val times = listOf(0L, 1000, 2000, 3000, 3001)
        // taps at 0..3000 are within 3000 ms (5th at 3000 fires); use a 3001 span instead
        val c = TapCounter(clock = { now })
        now = 0; c.tap(); now = 1000; c.tap(); now = 2000; c.tap(); now = 3000; c.tap()
        now = 3001
        assertFalse(c.tap()) // first tap (t=0) is 3001 ms old and was dropped
        assertTrue(times.isNotEmpty())
    }
}

package com.konecto.series76.chat

import org.junit.Assert.assertEquals
import org.junit.Test

class PlainTextTest {
    @Test fun stripsBoldMarkers() = assertEquals("764X30-11320000/A — 640 Nm", plainText("**764X30-11320000/A** — 640 Nm"))

    @Test fun numbersUnchanged() {
        val s = "**800** Nm, 2.4 A, 1,600 in-lbs, 34 s, 6.50 and 0.10 at 60Hz"
        assertEquals("800 Nm, 2.4 A, 1,600 in-lbs, 34 s, 6.50 and 0.10 at 60Hz", plainText(s))
    }

    @Test fun singleAsterisksKept() = assertEquals("a*b 3*4", plainText("a*b 3*4"))
}

package com.konecto.series76.ui.axel

import org.junit.Assert.assertEquals
import org.junit.Test

class AxelKeyframesTest {
    @Test fun knobHoldsAt90BetweenStops() {
        assertEquals(0f, knobAngle(0.05f), 0f)
        assertEquals(90f, knobAngle(0.5f), 0f)
        assertEquals(0f, knobAngle(1f), 0f)
    }

    @Test fun bounceHitsPeaks() {
        assertEquals(-5f, bounceOffset(.2f), 1e-4f)
        assertEquals(-2f, bounceOffset(.45f), 1e-4f)
        assertEquals(0f, bounceOffset(.8f), 0f)
    }

    @Test fun blinkClosesThenOpens() {
        assertEquals(1f, blinkScale(0f), 0f)
        assertEquals(.1f, blinkScale(.375f), 1e-4f)
        assertEquals(1f, blinkScale(1f), 0f)
    }

    @Test fun glanceReaches1_6() = assertEquals(1.6f, glanceOffset(.5f), 1e-4f)
}

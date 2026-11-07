package com.konecto.series76.voice

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class AudioRecorderTest {
    @Test
    fun backstopIsOneSecondAfterTheCap() {
        assertEquals(MAX_RECORDING_MS + 1_000, BACKSTOP_RECORDING_MS)
    }

    @Test
    fun keepsFileWithData() = assertTrue(shouldKeepRecording(1_024))

    @Test
    fun dropsEmptyFile() {
        assertFalse(shouldKeepRecording(0))
    }
}

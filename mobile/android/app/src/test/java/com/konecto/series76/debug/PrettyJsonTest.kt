package com.konecto.series76.debug

import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class PrettyJsonTest {
    @Test fun keepsNumberLiterals() {
        val out = prettyJson(Json.parseToJsonElement("""{"torque_nm":750,"fla":6.5,"hz":60.0,"a":[1000,null]}"""))
        assertTrue(out.contains("\"torque_nm\": 750"))
        assertTrue(out.contains("\"fla\": 6.5"))
        assertTrue(out.contains("\"hz\": 60.0"))
        assertTrue(out.contains("1000"))
        assertTrue(out.contains("\n"))
    }

    @Test fun durations() {
        assertEquals("—", formatDuration(null))
        assertEquals("<1 ms", formatDuration(0.4))
        assertEquals("12 ms", formatDuration(12.2))
    }
}

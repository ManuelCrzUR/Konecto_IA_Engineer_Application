package com.konecto.series76.ui

import kotlinx.serialization.json.JsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Test

class KeyFiguresTest {
    private fun rows(vararg f: Pair<String, JsonPrimitive?>) = orderedFields(mapOf(*f))

    @Test fun firstThreeWithValuesBecomeFiguresInContractOrder() {
        val (figs, rest) = splitKeyFigures(
            rows(
                "motor_power_w" to JsonPrimitive(180), "fla_60hz_a" to JsonPrimitive(2.4),
                "onoff_torque_nm" to JsonPrimitive(800), "speed_sec_60hz" to JsonPrimitive(34),
            ),
        )
        assertEquals(listOf("onoff_torque_nm", "speed_sec_60hz", "fla_60hz_a"), figs.map { it.key })
        assertEquals(listOf("motor_power_w"), rest.map { it.key })
    }

    @Test fun nullValuesAreSkippedForFiguresButKeptAsRowsWithDash() {
        val (figs, rest) = splitKeyFigures(
            rows("onoff_torque_nm" to null, "speed_sec_60hz" to JsonPrimitive(34)),
        )
        assertEquals(listOf("speed_sec_60hz"), figs.map { it.key })
        assertEquals(listOf("onoff_torque_nm" to "—"), rest.map { it.key to it.value })
    }

    @Test fun valuesStayLiteral() {
        val (figs, _) = splitKeyFigures(rows("fla_60hz_a" to JsonPrimitive(2.4), "lra_60hz_a" to JsonPrimitive(750)))
        assertEquals(listOf("2.4", "750"), figs.map { it.value })
    }

    @Test fun enclosureIsCapitalized() = assertEquals("Weatherproof", enclosureLabel("weatherproof"))

    @Test fun emptyRowsGiveNoFigures() {
        val (figures, rest) = splitKeyFigures(emptyList())
        assertEquals(0, figures.size)
        assertEquals(0, rest.size)
    }

    @Test fun maxParameterCapsFiguresAndRestKeepsOrder() {
        val all = rows("onoff_torque_nm" to JsonPrimitive(800), "cycles_per_hour" to JsonPrimitive(140), "motor_power_w" to JsonPrimitive(180))
        val (figures, rest) = splitKeyFigures(all, max = 1)
        assertEquals(1, figures.size)
        assertEquals(all.size - 1, rest.size)
        assertEquals(all, (figures + rest).sortedBy { all.indexOf(it) })
    }
}

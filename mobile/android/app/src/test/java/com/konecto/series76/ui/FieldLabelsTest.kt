package com.konecto.series76.ui

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Test

class FieldLabelsTest {
    private fun firstFields(): Map<String, JsonPrimitive?> {
        val text = javaClass.getResource("/ui/conversation_recommend.json")!!.readText()
        val p = Json.parseToJsonElement(text).jsonObject["products"]!!.jsonArray[0].jsonObject
        return p["fields"]!!.jsonObject.mapValues { it.value.jsonPrimitive }
    }

    @Test fun keepsContractOrderAndExactLiterals() {
        val rows = orderedFields(firstFields().entries.reversed().associate { it.key to it.value })
        assertEquals(
            listOf(
                "onoff_torque_nm", "onoff_torque_in_lbs", "mod_torque_nm", "mod_torque_in_lbs",
                "onoff_duty_cycle_pct", "mod_duty_cycle_pct", "cycles_per_hour", "starts_per_hour",
                "speed_sec_60hz", "speed_sec_50hz", "fla_60hz_a", "fla_50hz_a",
                "lra_60hz_a", "lra_50hz_a", "motor_power_w",
            ),
            rows.map { it.key },
        )
        val byKey = rows.associateBy { it.key }
        assertEquals("800", byKey["onoff_torque_nm"]!!.value)
        assertEquals("6900", byKey["onoff_torque_in_lbs"]!!.value)
        assertEquals("2.4", byKey["fla_60hz_a"]!!.value)
        assertEquals("Nm", byKey["onoff_torque_nm"]!!.unit)
    }

    @Test fun unknownKeysGoLastWithRawKeyLabel() {
        val rows = orderedFields(mapOf("zzz_new" to JsonPrimitive("1.50"), "motor_power_w" to JsonPrimitive(180)))
        assertEquals(listOf("motor_power_w", "zzz_new"), rows.map { it.key })
        assertEquals("zzz_new", rows[1].label)
        assertEquals("1.50", rows[1].value)
    }

    @Test fun nullBecomesDash() {
        val rows = orderedFields(mapOf("motor_power_w" to null))
        assertEquals("—", rows.first { it.key == "motor_power_w" }.value)
    }

    @Test fun orderedKeysContractOrderUnknownLast() {
        assertEquals(
            listOf("onoff_torque_nm", "fla_a", "motor_power_w", "b_new", "a_new"),
            orderedKeys(listOf("b_new", "motor_power_w", "fla_a", "a_new", "onoff_torque_nm", "fla_a")),
        )
        assertEquals(emptyList<String>(), orderedKeys(emptyList()))
    }
}

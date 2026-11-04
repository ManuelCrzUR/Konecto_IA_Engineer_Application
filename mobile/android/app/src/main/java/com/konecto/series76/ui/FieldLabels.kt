package com.konecto.series76.ui

import com.konecto.series76.data.displayValue
import kotlinx.serialization.json.JsonPrimitive

/** Presentation-only label and unit for a product field key. */
data class FieldLabel(val key: String, val label: String, val unit: String)

data class FieldRow(val key: String, val label: String, val value: String, val unit: String)

/** Display order = this list's order (see CONTRACT.md). */
val FIELD_LABELS: List<FieldLabel> = listOf(
    FieldLabel("onoff_torque_nm", "On/off torque", "Nm"),
    FieldLabel("onoff_torque_in_lbs", "On/off torque", "in-lbs"),
    FieldLabel("mod_torque_nm", "Modulating torque", "Nm"),
    FieldLabel("mod_torque_in_lbs", "Modulating torque", "in-lbs"),
    FieldLabel("output_torque_nm", "Output torque", "Nm"),
    FieldLabel("output_torque_in_lbs", "Output torque", "in-lbs"),
    FieldLabel("onoff_duty_cycle_pct", "Duty cycle (on/off)", "%"),
    FieldLabel("mod_duty_cycle_pct", "Duty cycle (mod.)", "%"),
    FieldLabel("duty_cycle_pct", "Duty cycle", "%"),
    FieldLabel("cycles_per_hour", "Cycles per hour", "/h"),
    FieldLabel("starts_per_hour", "Starts per hour", "/h"),
    FieldLabel("speed_sec_60hz", "Speed 60 Hz", "s per 90°"),
    FieldLabel("speed_sec_50hz", "Speed 50 Hz", "s per 90°"),
    FieldLabel("speed_sec", "Speed", "s per 90°"),
    FieldLabel("fla_60hz_a", "FLA 60 Hz", "A"),
    FieldLabel("fla_50hz_a", "FLA 50 Hz", "A"),
    FieldLabel("fla_a", "FLA", "A"),
    FieldLabel("lra_60hz_a", "LRA 60 Hz", "A"),
    FieldLabel("lra_50hz_a", "LRA 50 Hz", "A"),
    FieldLabel("lra_a", "LRA", "A"),
    FieldLabel("motor_power_w", "Motor power", "W"),
)

private val LABELS_BY_KEY = FIELD_LABELS.associateBy { it.key }

/** Keys in contract order; unknown keys last, in their given order. */
fun orderedKeys(keys: Collection<String>): List<String> {
    val present = keys.toSet()
    return FIELD_LABELS.map { it.key }.filter { it in present } + keys.distinct().filter { it !in LABELS_BY_KEY }
}

/** Rows in contract order; unknown keys last (raw key as label). Values are never reformatted. */
fun orderedFields(fields: Map<String, JsonPrimitive?>): List<FieldRow> =
    orderedKeys(fields.keys).map { key ->
        val label = LABELS_BY_KEY[key]
        FieldRow(key, label?.label ?: key, displayValue(fields[key]), label?.unit ?: "")
    }

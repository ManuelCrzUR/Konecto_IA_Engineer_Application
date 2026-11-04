package com.konecto.series76.debug

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonElement
import kotlin.math.roundToLong

private val pretty = Json { prettyPrint = true }

/** Pretty-prints JSON keeping every literal exactly as received (750 stays 750, 6.5 stays 6.5). */
fun prettyJson(element: JsonElement): String =
    pretty.encodeToString(JsonElement.serializer(), element)

/** Duration label for a trace: "12 ms", "<1 ms", or "—" when unknown. Not a technical number. */
fun formatDuration(ms: Double?): String = when {
    ms == null -> "—"
    ms < 1.0 -> "<1 ms"
    else -> "${ms.roundToLong()} ms"
}

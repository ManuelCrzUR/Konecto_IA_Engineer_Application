package com.konecto.series76.conversations

import java.time.Duration
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeParseException

/**
 * Pure formatter: ISO-8601 instant -> "just now", "5 min ago", "2 h ago", "yesterday",
 * "3 days ago", or the ISO date for older. Unparseable input is returned unchanged.
 */
fun formatRelative(iso: String, now: Instant, zone: ZoneId = ZoneId.systemDefault()): String {
    val then = try {
        Instant.parse(iso)
    } catch (_: DateTimeParseException) {
        return iso
    }
    val elapsed = Duration.between(then, now)
    if (elapsed.isNegative || elapsed.toMinutes() < 1) return "just now"
    if (elapsed.toMinutes() < 60) return "${elapsed.toMinutes()} min ago"
    val days = java.time.temporal.ChronoUnit.DAYS.between(
        then.atZone(zone).toLocalDate(),
        now.atZone(zone).toLocalDate(),
    )
    return when {
        elapsed.toHours() < 24 && days == 0L -> "${elapsed.toHours()} h ago"
        days == 1L -> "yesterday"
        days < 7 -> "$days days ago"
        else -> then.atZone(zone).toLocalDate().toString()
    }
}

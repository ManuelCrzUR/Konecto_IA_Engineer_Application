package com.konecto.series76.conversations

import java.time.Instant
import java.time.ZoneOffset
import org.junit.Assert.assertEquals
import org.junit.Test

class RelativeDateTest {
    private val now = Instant.parse("2026-11-04T15:00:00Z")
    private fun f(iso: String) = formatRelative(iso, now, ZoneOffset.UTC)

    @Test fun justNow() = assertEquals("just now", f("2026-11-04T14:59:30Z"))
    @Test fun future() = assertEquals("just now", f("2026-11-04T15:05:00Z"))
    @Test fun minutes() = assertEquals("4 min ago", f("2026-11-04T14:55:00.123456Z"))
    @Test fun hours() = assertEquals("2 h ago", f("2026-11-04T13:00:00Z"))
    @Test fun yesterdayCrossingMidnight() = assertEquals("yesterday", f("2026-11-03T23:30:00Z"))
    @Test fun yesterdayLate() = assertEquals("yesterday", f("2026-11-03T10:00:00Z"))
    @Test fun days() = assertEquals("3 days ago", f("2026-11-01T12:00:00Z"))
    @Test fun older() = assertEquals("2026-10-01", f("2026-10-01T12:00:00Z"))
    @Test fun invalid() = assertEquals("garbage", f("garbage"))
}

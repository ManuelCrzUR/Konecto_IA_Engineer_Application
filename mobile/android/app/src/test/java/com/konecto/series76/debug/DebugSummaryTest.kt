package com.konecto.series76.debug

import com.konecto.series76.data.ToolTrace
import org.junit.Assert.assertEquals
import org.junit.Test

class DebugSummaryTest {
    private fun turn(index: Int, calls: Int) =
        DebugTurn(index, "q$index", List(calls) { ToolTrace("get_actuator") })

    @Test fun noTurnsReadsZero() {
        assertEquals("0 turns · 0 calls", summarize(emptyList()))
    }

    @Test fun singularForms() {
        assertEquals("1 turn · 1 call", summarize(listOf(turn(0, 1))))
    }

    @Test fun countsTurnsAndAllTraces() {
        assertEquals("2 turns · 3 calls", summarize(listOf(turn(0, 2), turn(1, 1))))
    }

    @Test fun turnWithoutCallsStillCountsAsTurn() {
        assertEquals("1 turn · 0 calls", summarize(listOf(turn(0, 0))))
    }
}

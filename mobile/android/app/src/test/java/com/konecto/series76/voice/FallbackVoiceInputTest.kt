package com.konecto.series76.voice

import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class FakeVoice : VoiceInput {
    val flow = MutableSharedFlow<VoiceEvent>(extraBufferCapacity = 16)
    override val events: Flow<VoiceEvent> = flow
    var starts = 0
    var stops = 0
    override fun start(languageTag: String?) { starts++ }
    override fun stop() { stops++ }
    override fun release() {}
}

@OptIn(ExperimentalCoroutinesApi::class)
class FallbackVoiceInputTest {
    private var now = 0L
    private val primary = FakeVoice()
    private val fallback = FakeVoice()

    private fun TestScope.build(available: Boolean = true): Pair<FallbackVoiceInput, MutableList<VoiceEvent>> {
        val input = FallbackVoiceInput(primary, fallback, backgroundScope, { available }, FallbackMemory { now })
        val events = mutableListOf<VoiceEvent>()
        backgroundScope.launch(StandardTestDispatcher(testScheduler)) { input.events.collect { events += it } }
        testScheduler.runCurrent()
        return input to events
    }

    @Test fun successNeverTouchesFallback() = runTest {
        val (input, events) = build()
        input.start("en"); testScheduler.runCurrent()
        primary.flow.tryEmit(VoiceEvent.Listening); primary.flow.tryEmit(VoiceEvent.Final("x")); primary.flow.tryEmit(VoiceEvent.Ended)
        testScheduler.runCurrent()
        assertEquals(listOf(VoiceEvent.Listening, VoiceEvent.Final("x"), VoiceEvent.Ended), events)
        assertEquals(0, fallback.starts)
        input.stop(); assertEquals(1, primary.stops)
    }

    @Test fun unavailableEmitsNoticeAndStartsFallbackForSameTap() = runTest {
        val (input, events) = build()
        input.start("es"); testScheduler.runCurrent()
        primary.flow.tryEmit(VoiceEvent.Unavailable("503")); testScheduler.runCurrent()
        assertEquals(listOf<VoiceEvent>(VoiceEvent.Notice("Using the device recognizer")), events)
        assertEquals(1, fallback.starts)
        fallback.flow.tryEmit(VoiceEvent.Partial("hi")); testScheduler.runCurrent()
        assertEquals(VoiceEvent.Partial("hi"), events.last())
        input.stop(); assertEquals(1, fallback.stops)
    }

    @Test fun fallbackIsStickyForFiveMinutes() = runTest {
        val (input, _) = build()
        input.start(null); testScheduler.runCurrent()
        primary.flow.tryEmit(VoiceEvent.Unavailable("503")); testScheduler.runCurrent()
        now = 4 * 60_000L
        input.start(null)
        assertEquals(1, primary.starts)
        assertEquals(2, fallback.starts)
        now = 5 * 60_000L + 1
        input.start(null)
        assertEquals(2, primary.starts)
    }

    @Test fun noRecognizerEitherIsVoiceUnavailable() = runTest {
        val (input, events) = build(available = false)
        input.start(null); testScheduler.runCurrent()
        primary.flow.tryEmit(VoiceEvent.Unavailable("503")); testScheduler.runCurrent()
        assertEquals(VoiceEvent.Error("Voice is unavailable"), events[1])
        assertTrue(events.last() == VoiceEvent.Ended)
        assertEquals(0, fallback.starts)
    }
}

package com.konecto.series76.voice

import com.konecto.series76.data.ApiResult
import com.konecto.series76.data.SpeechAudio
import com.konecto.series76.data.SpeechSynthesizer
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/** Each sentence's result is released by the test, so completion order is controlled. */
private class GatedSynthesizer : SpeechSynthesizer {
    val gates = mutableMapOf<String, CompletableDeferred<ApiResult<SpeechAudio>>>()
    val requested = mutableListOf<Pair<String, String?>>()
    var inFlight = 0
    var maxInFlight = 0
    override suspend fun synthesize(text: String, language: String?): ApiResult<SpeechAudio> {
        requested += text to language
        inFlight++; maxInFlight = maxOf(maxInFlight, inFlight)
        try {
            return gates.getOrPut(text) { CompletableDeferred() }.await()
        } finally {
            inFlight--
        }
    }
    fun release(text: String, bytes: Byte) =
        gates.getOrPut(text) { CompletableDeferred() }.complete(ApiResult.Success(SpeechAudio(byteArrayOf(bytes), "audio/mpeg")))
    fun fail(text: String) =
        gates.getOrPut(text) { CompletableDeferred() }.complete(serverFailure(503))
}

@OptIn(ExperimentalCoroutinesApi::class)
class SentencePipelineTest {
    private class Setup(scope: kotlinx.coroutines.test.TestScope) {
        val synth = GatedSynthesizer()
        val player = FakePlayer()
        val failures = mutableListOf<Triple<String, String, Boolean>>()
        var firstAudio = 0
        val speaker = CloudSpeaker(synth, player, tempCacheDir(), scope, StandardTestDispatcher(scope.testScheduler))
            .also { s -> s.onFailure = { k, t, st -> failures += Triple(k, t, st) } }
        fun speak(text: String, language: String? = null) = speaker.speak("k", text, language) { firstAudio++ }
    }

    @Test fun sentencesFinishingOutOfOrderStillPlayInOrder() = runTest {
        val s = Setup(this)
        s.speak("One. Two. Three.")
        testScheduler.advanceUntilIdle()
        assertEquals(3, s.synth.requested.size) // all requested concurrently
        s.synth.release("Three.", 3)
        s.synth.release("Two.", 2)
        testScheduler.advanceUntilIdle()
        assertTrue(s.player.played.isEmpty()) // sentence 1 is not ready: nothing plays, not even the later ones
        assertEquals(0, s.firstAudio)
        s.synth.release("One.", 1)
        testScheduler.advanceUntilIdle()
        assertEquals(1, s.firstAudio)
        assertEquals(listOf<Byte>(1), s.player.played.map { it.readBytes()[0] })
        s.player.finish(); testScheduler.advanceUntilIdle()
        s.player.finish(); testScheduler.advanceUntilIdle()
        assertEquals(listOf<Byte>(1, 2, 3), s.player.played.map { it.readBytes()[0] })
        s.player.finish(); testScheduler.advanceUntilIdle()
        assertNull(s.speaker.speakingKey.value)
        assertEquals(1, s.firstAudio)
        assertTrue(s.failures.isEmpty())
    }

    @Test fun nextSentenceStartsAsSoonAsPreviousEnds() = runTest {
        val s = Setup(this)
        s.speak("One. Two.")
        testScheduler.advanceUntilIdle()
        s.synth.release("One.", 1); s.synth.release("Two.", 2)
        testScheduler.advanceUntilIdle()
        assertEquals(1, s.player.played.size)
        s.player.finish()
        testScheduler.advanceUntilIdle()
        assertEquals(2, s.player.played.size)
        s.speaker.stop()
    }

    @Test fun atMostFourRequestsInFlight() = runTest {
        val s = Setup(this)
        s.speak("A. B. C. D. E. F.")
        testScheduler.advanceUntilIdle()
        assertEquals(4, s.synth.maxInFlight)
        assertEquals(4, s.synth.requested.size)
        s.synth.release("A.", 1)
        testScheduler.advanceUntilIdle()
        assertEquals(5, s.synth.requested.size)
        s.speaker.stop()
    }

    @Test fun preparingUntilFirstSentenceIsReady() = runTest {
        val s = Setup(this)
        s.speak("One. Two.")
        assertEquals("k", s.speaker.preparingKey.value)
        testScheduler.advanceUntilIdle()
        s.synth.release("One.", 1)
        testScheduler.advanceUntilIdle()
        assertNull(s.speaker.preparingKey.value)
        assertEquals("k", s.speaker.speakingKey.value)
        s.speaker.stop()
    }

    @Test fun laterFailureReportsOnlyTheUnspokenRest() = runTest {
        val s = Setup(this)
        s.speak("One. Two. Three.")
        testScheduler.advanceUntilIdle()
        s.synth.release("One.", 1); s.synth.fail("Two."); s.synth.release("Three.", 3)
        testScheduler.advanceUntilIdle()
        assertEquals(1, s.firstAudio)
        s.player.finish()
        testScheduler.advanceUntilIdle()
        assertEquals(listOf(Triple("k", "Two. Three.", true)), s.failures)
        assertNull(s.speaker.speakingKey.value)
        assertEquals(1, s.player.played.size)
    }

    @Test fun replayComesFromCacheWithoutNewRequests() = runTest {
        val s = Setup(this)
        s.speak("One. Two.")
        testScheduler.advanceUntilIdle()
        s.synth.release("One.", 1); s.synth.release("Two.", 2)
        testScheduler.advanceUntilIdle()
        s.player.finish(); testScheduler.advanceUntilIdle()
        s.player.finish(); testScheduler.advanceUntilIdle()
        s.speak("One. Two.")
        testScheduler.advanceUntilIdle()
        assertEquals(2, s.synth.requested.size)
        assertEquals(3, s.player.played.size)
        s.speaker.stop()
    }

    @Test fun backendLanguageIsSentToTheSynthesizer() = runTest {
        val s = Setup(this)
        s.speak("Hello there.", language = "es")
        testScheduler.advanceUntilIdle()
        assertEquals(listOf("Hello there." to "es"), s.synth.requested)
        s.speaker.stop()
    }

    @Test fun firstAudioDeadlineMakesDeviceTakeOverOnce() = runTest {
        val s = Setup(this)
        val device = FakeSpeaker()
        val fb = FallbackSpeaker(
            s.speaker, device,
            kotlinx.coroutines.CoroutineScope(backgroundScope.coroutineContext + UnconfinedTestDispatcher(testScheduler)),
            FallbackMemory { 0L }, deadlineMs = 10_000,
        )
        var revealed = 0
        fb.speak("k", "One. Two.", "en") { revealed++ }
        testScheduler.advanceTimeBy(9_999)
        assertEquals(0, revealed)
        assertTrue(device.spoken.isEmpty())
        testScheduler.advanceTimeBy(2)
        assertEquals(1, revealed)
        assertEquals(listOf("k" to "One. Two."), device.spoken)
        assertEquals(listOf<String?>("en"), device.languages)
        s.synth.release("One.", 1) // arrives too late: must not double fire or play
        testScheduler.advanceUntilIdle()
        assertEquals(1, revealed)
        assertTrue(s.player.played.isEmpty())
        assertFalse(s.speaker.preparingKey.value != null)
    }

    @Test fun cloudAudioBeforeDeadlineRevealsAndCancelsDeadline() = runTest {
        val s = Setup(this)
        val device = FakeSpeaker()
        val fb = FallbackSpeaker(
            s.speaker, device,
            kotlinx.coroutines.CoroutineScope(backgroundScope.coroutineContext + UnconfinedTestDispatcher(testScheduler)),
            FallbackMemory { 0L }, deadlineMs = 10_000,
        )
        var revealed = 0
        fb.speak("k", "One.") { revealed++ }
        testScheduler.advanceUntilIdle()
        s.synth.release("One.", 1)
        testScheduler.advanceTimeBy(1_000)
        assertEquals(1, revealed)
        testScheduler.advanceTimeBy(20_000)
        assertEquals(1, revealed)
        assertTrue(device.spoken.isEmpty())
        fb.stop()
    }

    @Suppress("unused") private val unused: File? = null
}

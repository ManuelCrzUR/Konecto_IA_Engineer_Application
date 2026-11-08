package com.konecto.series76.voice

import com.konecto.series76.data.ApiResult
import com.konecto.series76.data.FailureKind
import com.konecto.series76.data.SpeechAudio
import com.konecto.series76.data.SpeechSynthesizer
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

open class FakeSynthesizer(var result: ApiResult<SpeechAudio> = ApiResult.Success(SpeechAudio(byteArrayOf(1, 2), "audio/mpeg"))) :
    SpeechSynthesizer {
    val calls = mutableListOf<Pair<String, String?>>()
    override suspend fun synthesize(text: String, language: String?): ApiResult<SpeechAudio> {
        calls += text to language
        return result
    }
}

class FakePlayer : AudioPlayer {
    val played = mutableListOf<File>()
    var stops = 0
    var released = false
    private var done: (() -> Unit)? = null
    private var error: (() -> Unit)? = null
    override fun play(file: File, onDone: () -> Unit, onError: () -> Unit) {
        played += file; done = onDone; error = onError
    }
    override fun stop() { stops++; done = null; error = null }
    override fun release() { released = true }
    fun finish() = done?.invoke()
    fun fail() = error?.invoke()
}

fun tempCacheDir(): File = File.createTempFile("speech", "").apply { delete(); mkdirs(); deleteOnExit() }

@OptIn(ExperimentalCoroutinesApi::class)
class CloudSpeakerTest {
    private class Setup(scope: TestScope, val synth: FakeSynthesizer = FakeSynthesizer()) {
        val player = FakePlayer()
        val dir = tempCacheDir()
        var now = 10_000_000_000L
        val failures = mutableListOf<Triple<String, String, Boolean>>()
        val speaker = CloudSpeaker(
            synth, player, dir, scope, StandardTestDispatcher(scope.testScheduler), clock = { now },
        ).also { s -> s.onFailure = { k, t, st -> failures += Triple(k, t, st) } }
    }

    @Test fun successPlaysCachesAndClearsWhenDone() = runTest {
        val s = Setup(this)
        s.speaker.speak("k1", "Hello there")
        assertEquals("k1", s.speaker.preparingKey.value)
        assertNull(s.speaker.speakingKey.value)
        testScheduler.advanceUntilIdle()
        assertNull(s.speaker.preparingKey.value)
        assertEquals("k1", s.speaker.speakingKey.value)
        assertEquals(listOf("Hello there" to "en"), s.synth.calls)
        assertEquals(1, s.player.played.size)
        assertTrue(s.player.played[0].isFile)
        s.player.finish()
        testScheduler.advanceUntilIdle()
        assertNull(s.speaker.speakingKey.value)
        assertTrue(s.failures.isEmpty())
    }

    @Test fun sameKeyAndTextReplaysFromCache() = runTest {
        val s = Setup(this)
        s.speaker.speak("k1", "Hola, qué tal")
        testScheduler.advanceUntilIdle()
        s.player.finish()
        testScheduler.advanceUntilIdle()
        s.speaker.speak("k1", "Hola, qué tal")
        testScheduler.advanceUntilIdle()
        assertEquals(1, s.synth.calls.size)
        assertEquals("es", s.synth.calls[0].second)
        assertEquals(2, s.player.played.size)
        assertEquals(s.player.played[0], s.player.played[1])
        s.speaker.stop()
    }

    @Test fun serverFailureReportsStickyAndGoesIdle() = runTest {
        val s = Setup(this, FakeSynthesizer(serverFailure(503)))
        s.speaker.speak("k1", "Hello")
        testScheduler.advanceUntilIdle()
        assertEquals(listOf(Triple("k1", "Hello", true)), s.failures)
        assertNull(s.speaker.speakingKey.value)
        assertTrue(s.player.played.isEmpty())
    }

    @Test fun clientErrorIsNotSticky() = runTest {
        val s = Setup(this, FakeSynthesizer(serverFailure(429)))
        s.speaker.speak("k1", "Hello")
        testScheduler.advanceUntilIdle()
        assertEquals(false, s.failures.single().third)
    }

    @Test fun timeoutAndNetworkAreSticky() = runTest {
        val s = Setup(this, FakeSynthesizer(ApiResult.Failure(FailureKind.Network, "x")))
        s.speaker.speak("k1", "Hello")
        testScheduler.advanceUntilIdle()
        assertEquals(true, s.failures.single().third)
    }

    @Test fun overlongTextIsNotSent() = runTest {
        val s = Setup(this)
        val text = "a".repeat(MAX_SPEECH_CHARS + 1)
        s.speaker.speak("k1", text)
        testScheduler.advanceUntilIdle()
        assertTrue(s.synth.calls.isEmpty())
        assertEquals(listOf(Triple("k1", text, false)), s.failures)
        assertNull(s.speaker.speakingKey.value)
    }

    @Test fun stopHaltsPlayerAndClearsKey() = runTest {
        val s = Setup(this)
        s.speaker.speak("k1", "Hello")
        testScheduler.advanceUntilIdle()
        s.speaker.stop()
        assertNull(s.speaker.speakingKey.value)
        assertTrue(s.player.stops > 0)
    }

    @Test fun playbackErrorReportsFailureAndDropsCacheFile() = runTest {
        val s = Setup(this)
        s.speaker.speak("k1", "Hello")
        testScheduler.advanceUntilIdle()
        val f = s.player.played[0]
        s.player.fail()
        testScheduler.advanceUntilIdle()
        assertTrue(!f.exists())
        assertEquals(false, s.failures.single().third)
    }

    @Test fun pruneRemovesOldFilesAndCapsCount() = runTest {
        val s = Setup(this)
        repeat(CACHE_MAX_FILES + 5) { i ->
            File(s.dir, "old$i.mp3").apply { writeBytes(byteArrayOf(1)); setLastModified(s.now - 10_000L - i) }
        }
        File(s.dir, "stale.mp3").apply { writeBytes(byteArrayOf(1)); setLastModified(s.now - 2 * 3600_000L) }
        s.speaker.speak("k9", "Hello")
        testScheduler.advanceUntilIdle()
        val files = s.dir.listFiles()!!.map { it.name }
        assertEquals(CACHE_MAX_FILES, files.size)
        assertTrue("stale.mp3" !in files)
        s.speaker.stop()
    }

    @Test fun stateSequenceIsPreparingThenReadingThenIdle() = runTest {
        val s = Setup(this)
        val seen = mutableListOf<SpeakerButtonState>()
        fun snap() { seen += voiceButtonState("k1", s.speaker.speakingKey.value, s.speaker.preparingKey.value) }
        s.speaker.speak("k1", "Hello there"); snap()
        testScheduler.advanceUntilIdle(); snap()
        s.player.finish(); testScheduler.advanceUntilIdle(); snap()
        assertEquals(listOf(SpeakerButtonState.Preparing, SpeakerButtonState.Reading, SpeakerButtonState.Idle), seen)
    }

    @Test fun cacheDirThatIsAFileFailsTheSentenceWithoutThrowing() = runTest {
        val s = Setup(this)
        val file = File.createTempFile("notadir", "").apply { deleteOnExit() }
        val speaker = CloudSpeaker(s.synth, s.player, file, this, StandardTestDispatcher(testScheduler), clock = { s.now })
        val failures = mutableListOf<Triple<String, String, Boolean>>()
        speaker.onFailure = { k, t, st -> failures += Triple(k, t, st) }
        speaker.speak("k1", "Hello there")
        testScheduler.advanceUntilIdle()
        assertEquals(listOf(Triple("k1", "Hello there", false)), failures)
        assertNull(speaker.speakingKey.value)
        assertNull(speaker.preparingKey.value)
    }

    @Test fun unexpectedSynthesizerExceptionFailsTheSentenceNotTheApp() = runTest {
        val s = Setup(this, object : FakeSynthesizer() {
            override suspend fun synthesize(text: String, language: String?): ApiResult<SpeechAudio> = error("boom")
        })
        s.speaker.speak("k1", "Hello there")
        testScheduler.advanceUntilIdle()
        assertEquals(listOf(Triple("k1", "Hello there", false)), s.failures)
        assertNull(s.speaker.speakingKey.value)
    }

    @Test fun releaseCancelsOwnScopeAndLaterSpeakDoesNothing() = runTest {
        val s = Setup(this)
        s.speaker.release()
        assertTrue(s.player.released)
        s.speaker.speak("k1", "Hello there")
        testScheduler.advanceUntilIdle()
        assertTrue(s.synth.calls.isEmpty())
        assertTrue(this.coroutineContext[kotlinx.coroutines.Job]!!.isActive)
    }
}

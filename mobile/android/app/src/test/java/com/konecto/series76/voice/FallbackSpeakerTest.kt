package com.konecto.series76.voice

import com.konecto.series76.data.ApiResult
import com.konecto.series76.data.FailureKind
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class FallbackSpeakerTest {
    private class Setup(scope: TestScope, result: ApiResult<com.konecto.series76.data.SpeechAudio>?) {
        val synth = result?.let { FakeSynthesizer(it) } ?: FakeSynthesizer()
        val player = FakePlayer()
        val device = FakeSpeaker()
        var now = 0L
        val cloud = CloudSpeaker(
            synth, player, tempCacheDir(), scope, StandardTestDispatcher(scope.testScheduler), clock = { now },
        )
        val speaker = FallbackSpeaker(
            cloud, device, kotlinx.coroutines.CoroutineScope(scope.backgroundScope.coroutineContext + UnconfinedTestDispatcher(scope.testScheduler)), FallbackMemory { now },
        )
    }

    @Test fun successNeverTouchesDevice() = runTest {
        val s = Setup(this, null)
        s.speaker.speak("k", "Hello")
        testScheduler.advanceUntilIdle()
        assertEquals(1, s.player.played.size)
        assertEquals(emptyList<Pair<String, String>>(), s.device.spoken)
        assertEquals("k", s.speaker.speakingKey.value)
        s.player.finish()
        testScheduler.advanceUntilIdle()
        assertNull(s.speaker.speakingKey.value)
    }

    @Test fun serverErrorSpeaksOnDeviceAndSticksForFiveMinutes() = runTest {
        val s = Setup(this, serverFailure(503))
        s.speaker.speak("k", "Hello")
        testScheduler.advanceUntilIdle()
        assertEquals(listOf("k" to "Hello"), s.device.spoken)
        // Within the window: straight to the device, no cloud call.
        s.now += 4 * 60_000L
        s.speaker.speak("k2", "Again")
        testScheduler.advanceUntilIdle()
        assertEquals(1, s.synth.calls.size)
        assertEquals("k2" to "Again", s.device.spoken.last())
        // After the window the cloud is tried again.
        s.now += 2 * 60_000L
        s.speaker.speak("k3", "Third")
        testScheduler.advanceUntilIdle()
        assertEquals(2, s.synth.calls.size)
    }

    @Test fun rateLimitFallsBackForThatMessageOnly() = runTest {
        val s = Setup(this, serverFailure(429))
        s.speaker.speak("k", "Hello")
        testScheduler.advanceUntilIdle()
        assertEquals(listOf("k" to "Hello"), s.device.spoken)
        s.speaker.speak("k2", "Again")
        testScheduler.advanceUntilIdle()
        assertEquals(2, s.synth.calls.size) // cloud tried again
    }

    @Test fun timeoutIsSticky() = runTest {
        val s = Setup(this, ApiResult.Failure(FailureKind.Timeout, "t"))
        s.speaker.speak("k", "Hello")
        testScheduler.advanceUntilIdle()
        s.speaker.speak("k2", "Again")
        testScheduler.advanceUntilIdle()
        assertEquals(1, s.synth.calls.size)
        assertEquals(2, s.device.spoken.size)
    }

    @Test fun overlongTextGoesToDeviceWithoutCloud() = runTest {
        val s = Setup(this, null)
        val text = "a".repeat(MAX_SPEECH_CHARS + 1)
        s.speaker.speak("k", text)
        testScheduler.advanceUntilIdle()
        assertEquals(0, s.synth.calls.size)
        assertEquals(listOf("k" to text), s.device.spoken)
    }

    @Test fun stopStopsWhicheverIsActive() = runTest {
        val s = Setup(this, null)
        s.speaker.speak("k", "Hello")
        testScheduler.advanceUntilIdle()
        s.speaker.stop()
        assertNull(s.speaker.speakingKey.value)
        assertEquals(true, s.player.stops > 0)

        val f = Setup(this, serverFailure(503))
        f.speaker.speak("k", "Hello")
        testScheduler.advanceUntilIdle()
        assertEquals("k", f.speaker.speakingKey.value)
        f.speaker.stop()
        assertNull(f.device.speakingKey.value)
        assertNull(f.speaker.speakingKey.value)
    }

    @Test fun releaseCancelsTheCollector() = runTest {
        val s = Setup(this, null)
        s.device.speak("d1", "x")
        assertEquals("d1", s.speaker.speakingKey.value)
        s.speaker.release()
        s.device.speak("d2", "y")
        testScheduler.advanceUntilIdle()
        assertNull(s.speaker.speakingKey.value.takeIf { it == "d2" })
    }
}

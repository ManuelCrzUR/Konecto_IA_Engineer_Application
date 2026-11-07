package com.konecto.series76.voice

import com.konecto.series76.data.ApiResult
import com.konecto.series76.data.FailureKind
import com.konecto.series76.data.Transcriber
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

class FakeRecorder(var startOk: Boolean = true, var hasAudio: Boolean = true) : AudioRecorder {
    var file: File? = null
    var cancelled = false
    override fun start(): Boolean {
        if (startOk) file = File.createTempFile("question", ".m4a")
        return startOk
    }
    override fun stop(): File? = if (hasAudio) file else null.also { file?.delete() }
    override fun cancel() { cancelled = true; file?.delete() }
}

class FakeTranscriber(var result: ApiResult<String>) : Transcriber {
    var seenFile: File? = null
    var seenLanguage: String? = null
    var fileExistedDuringUpload = false
    override suspend fun transcribe(audio: File, language: String?): ApiResult<String> {
        seenFile = audio; seenLanguage = language; fileExistedDuringUpload = audio.exists()
        return result
    }
}

fun serverFailure(status: Int, message: String = "m") =
    ApiResult.Failure(FailureKind.Server(status, "x"), message)

@OptIn(ExperimentalCoroutinesApi::class)
class CloudVoiceInputTest {
    private fun TestScope.run(
        t: FakeTranscriber,
        rec: FakeRecorder = FakeRecorder(),
        block: TestScope.(CloudVoiceInput, MutableList<VoiceEvent>) -> Unit,
    ) {
        val input = CloudVoiceInput(rec, t, this)
        val events = mutableListOf<VoiceEvent>()
        backgroundScope.launch(UnconfinedTestDispatcher(testScheduler)) { input.events.collect { events += it } }
        block(input, events)
    }

    @Test fun successEmitsListeningTranscribingFinalEnded() = runTest {
        val t = FakeTranscriber(ApiResult.Success("hello 764A"))
        run(t) { input, events ->
            input.start("es-ES"); testScheduler.runCurrent()
            input.stop(); advanceUntilIdle()
            assertEquals(
                listOf(VoiceEvent.Listening, VoiceEvent.Transcribing, VoiceEvent.Final("hello 764A"), VoiceEvent.Ended),
                events.toList(),
            )
        }
        assertEquals("es", t.seenLanguage)
        assertTrue(t.fileExistedDuringUpload)
        assertFalse(t.seenFile!!.exists())
    }

    @Test fun serverDownIsUnavailableWithoutEnded() = runTest {
        run(FakeTranscriber(serverFailure(503))) { input, events ->
            input.start(null); testScheduler.runCurrent(); input.stop(); advanceUntilIdle()
            assertTrue(events.last() is VoiceEvent.Unavailable)
            assertFalse(VoiceEvent.Ended in events)
        }
    }

    @Test fun timeoutIsUnavailable() = runTest {
        run(FakeTranscriber(ApiResult.Failure(FailureKind.Timeout, "slow"))) { input, events ->
            input.start(null); testScheduler.runCurrent(); input.stop(); advanceUntilIdle()
            assertTrue(events.last() is VoiceEvent.Unavailable)
        }
    }

    @Test fun tooLargeIsErrorThenEndedAndFileDeleted() = runTest {
        val t = FakeTranscriber(serverFailure(413, "Audio too large"))
        run(t) { input, events ->
            input.start(null); testScheduler.runCurrent(); input.stop(); advanceUntilIdle()
            assertEquals(listOf(VoiceEvent.Error("Audio too large"), VoiceEvent.Ended), events.takeLast(2))
        }
        assertFalse(t.seenFile!!.exists())
    }

    @Test fun recordingStopsItselfAtTheCap() = runTest {
        val t = FakeTranscriber(ApiResult.Success("x"))
        run(t) { input, events ->
            input.start(null); testScheduler.runCurrent()
            advanceTimeBy(29_000); testScheduler.runCurrent()
            assertFalse(VoiceEvent.Transcribing in events)
            advanceTimeBy(1_500); testScheduler.runCurrent()
            assertTrue(VoiceEvent.Transcribing in events)
        }
    }

    @Test fun recorderFailureIsErrorAndEnded() = runTest {
        run(FakeTranscriber(ApiResult.Success("x")), FakeRecorder(startOk = false)) { input, events ->
            input.start(null); testScheduler.runCurrent()
            assertEquals(listOf(VoiceEvent.Error("Could not start recording"), VoiceEvent.Ended), events.toList())
        }
    }
}

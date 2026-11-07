package com.konecto.series76.voice

import com.konecto.series76.data.ApiResult
import com.konecto.series76.data.FailureKind
import com.konecto.series76.data.Transcriber
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.launch
import java.io.File

/**
 * Record, then transcribe through the backend (D-53). Flow: Listening -> (stop or 30 s) -> Transcribing ->
 * Final + Ended. Server 5xx, timeouts and network errors emit [VoiceEvent.Unavailable] (no Ended: a
 * fallback takes over); 4xx emit Error + Ended because the audio or the user is the problem.
 * [scope] must run on the main thread.
 */
class CloudVoiceInput(
    private val recorder: AudioRecorder,
    private val transcriber: Transcriber,
    private val scope: CoroutineScope,
    private val maxRecordingMs: Long = MAX_RECORDING_MS.toLong(),
) : VoiceInput {
    private val _events = MutableSharedFlow<VoiceEvent>(extraBufferCapacity = 32)
    override val events: Flow<VoiceEvent> = _events.asSharedFlow()

    private enum class Phase { Idle, Recording, Uploading }

    private var phase = Phase.Idle
    private var language: String? = null
    private var capJob: Job? = null
    private var uploadJob: Job? = null

    override fun start(languageTag: String?) {
        if (phase != Phase.Idle) return
        if (!recorder.start()) {
            _events.tryEmit(VoiceEvent.Error("Could not start recording"))
            _events.tryEmit(VoiceEvent.Ended)
            return
        }
        phase = Phase.Recording
        language = languageTag?.substringBefore('-')?.lowercase()?.takeIf { it == "es" || it == "en" }
        _events.tryEmit(VoiceEvent.Listening)
        capJob = scope.launch {
            delay(maxRecordingMs)
            stop()
        }
    }

    override fun stop() {
        if (phase != Phase.Recording) return
        capJob?.cancel()
        val file = recorder.stop()
        if (file == null) {
            phase = Phase.Idle
            _events.tryEmit(VoiceEvent.Error("Didn't catch that, try again"))
            _events.tryEmit(VoiceEvent.Ended)
            return
        }
        phase = Phase.Uploading
        _events.tryEmit(VoiceEvent.Transcribing)
        uploadJob = scope.launch { upload(file) }
    }

    private suspend fun upload(file: File) {
        val result = try {
            transcriber.transcribe(file, language)
        } finally {
            file.delete()
        }
        phase = Phase.Idle
        when (result) {
            is ApiResult.Success ->
                if (result.value.isBlank()) {
                    _events.tryEmit(VoiceEvent.Error("Didn't catch that, try again"))
                } else {
                    _events.tryEmit(VoiceEvent.Final(result.value))
                }
            is ApiResult.Failure -> {
                val k = result.kind
                val unavailable = k == FailureKind.Network || k == FailureKind.Timeout ||
                    (k is FailureKind.Server && k.status >= 500)
                if (unavailable) {
                    _events.tryEmit(VoiceEvent.Unavailable(result.message))
                    return
                }
                _events.tryEmit(VoiceEvent.Error(result.message))
            }
        }
        _events.tryEmit(VoiceEvent.Ended)
    }

    override fun release() {
        capJob?.cancel()
        uploadJob?.cancel()
        recorder.cancel()
        phase = Phase.Idle
    }
}

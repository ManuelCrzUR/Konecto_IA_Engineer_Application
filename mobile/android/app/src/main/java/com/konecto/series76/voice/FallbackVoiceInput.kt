package com.konecto.series76.voice

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.launch

const val FALLBACK_WINDOW_MS = 5 * 60 * 1000L

/** Shared across screens so the "use the device recognizer" decision outlives one chat screen. */
class FallbackMemory(private val clock: () -> Long = System::currentTimeMillis) {
    private var until = 0L
    val active: Boolean get() = clock() < until
    fun remember() { until = clock() + FALLBACK_WINDOW_MS }
}

/**
 * Primary (cloud) first; when it reports [VoiceEvent.Unavailable] it emits a Notice and starts the
 * fallback for the same tap, then prefers the fallback for [FALLBACK_WINDOW_MS]. Everything else is forwarded.
 */
class FallbackVoiceInput(
    private val primary: VoiceInput,
    private val fallback: VoiceInput,
    scope: CoroutineScope,
    private val fallbackAvailable: () -> Boolean,
    private val memory: FallbackMemory = FallbackMemory(),
) : VoiceInput {
    private val _events = MutableSharedFlow<VoiceEvent>(extraBufferCapacity = 64)
    override val events: Flow<VoiceEvent> = _events.asSharedFlow()

    private var current: VoiceInput = primary
    private var language: String? = null
    private val jobs: List<Job>

    init {
        val a = scope.launch {
            primary.events.collect { e ->
                if (e is VoiceEvent.Unavailable) {
                    memory.remember()
                    _events.tryEmit(VoiceEvent.Notice("Using the device recognizer"))
                    startFallback()
                } else {
                    _events.tryEmit(e)
                }
            }
        }
        val b = scope.launch { fallback.events.collect { _events.tryEmit(it) } }
        jobs = listOf(a, b)
    }

    private fun startFallback() {
        if (!fallbackAvailable()) {
            _events.tryEmit(VoiceEvent.Error("Voice is unavailable"))
            _events.tryEmit(VoiceEvent.Ended)
            return
        }
        current = fallback
        fallback.start(language)
    }

    override fun start(languageTag: String?) {
        language = languageTag
        if (memory.active && fallbackAvailable()) {
            current = fallback
            fallback.start(languageTag)
        } else {
            current = primary
            primary.start(languageTag)
        }
    }

    override fun stop() = current.stop()

    override fun release() {
        jobs.forEach { it.cancel() }
        primary.release()
        fallback.release()
    }
}

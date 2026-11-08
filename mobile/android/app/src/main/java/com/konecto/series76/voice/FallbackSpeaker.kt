package com.konecto.series76.voice

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

const val FIRST_AUDIO_DEADLINE_MS = 10_000L

/**
 * Cloud voice first (D-54). When the cloud speaker reports a failure the unspoken text is read by the
 * device voice immediately; the same happens when the first sentence is not ready within
 * [deadlineMs]. Network, timeout and 5xx failures also make the device voice the first choice for
 * [FALLBACK_WINDOW_MS]; 4xx and oversized text affect only that message. `onFirstAudio` fires exactly
 * once per [speak]: when cloud audio is ready, or when the device voice takes over.
 */
class FallbackSpeaker(
    private val primary: CloudSpeaker,
    private val fallback: Speaker,
    parentScope: CoroutineScope,
    private val memory: FallbackMemory = FallbackMemory(),
    private val deadlineMs: Long = FIRST_AUDIO_DEADLINE_MS,
) : Speaker {
    // Own scope (collector + deadline, independent job); release() cancels it so nothing outlives the screen.
    private val scope = CoroutineScope(parentScope.coroutineContext + SupervisorJob())

    override val speakingKey: StateFlow<String?> =
        combine(primary.speakingKey, fallback.speakingKey) { a, b -> a ?: b }
            .stateIn(scope, SharingStarted.Eagerly, null)
    override val preparingKey: StateFlow<String?> get() = primary.preparingKey

    private var deadline: Job? = null
    private var language: String? = null
    private var firstAudio: (() -> Unit)? = null

    init {
        primary.onFailure = { key, text, sticky ->
            if (sticky) memory.remember()
            deviceTakesOver(key, text)
        }
    }

    private fun deviceTakesOver(key: String, text: String) {
        deadline?.cancel()
        fallback.speak(key, text, language)
        fireFirstAudio()
    }

    private fun fireFirstAudio() {
        val f = firstAudio
        firstAudio = null
        f?.invoke()
    }

    override fun speak(key: String, text: String, language: String?, onFirstAudio: () -> Unit) {
        // One voice at a time: silence whichever is active before choosing.
        stop()
        this.language = language
        firstAudio = onFirstAudio
        if (memory.active || text.length > MAX_SPEECH_CHARS) return deviceTakesOver(key, text)
        deadline = scope.launch {
            delay(deadlineMs)
            primary.stop()
            deviceTakesOver(key, text)
        }
        primary.speak(key, text, language) { deadline?.cancel(); fireFirstAudio() }
    }

    override fun stop() {
        deadline?.cancel()
        fireFirstAudio() // a pending reveal must never be lost when speech is cut short
        primary.stop()
        fallback.stop()
    }

    override fun release() {
        stop()
        primary.release()
        fallback.release()
        scope.cancel()
    }
}

package com.konecto.series76.voice

import com.konecto.series76.data.ApiResult
import com.konecto.series76.data.FailureKind
import com.konecto.series76.data.SpeechSynthesizer
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.async
import kotlinx.coroutines.cancel
import kotlinx.coroutines.isActive
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.sync.withPermit
import java.io.File
import kotlin.coroutines.resume

const val MAX_SPEECH_CHARS = 1500
private const val MAX_IN_FLIGHT = 4

private sealed interface Piece {
    class Ready(val file: File) : Piece
    class Failed(val sticky: Boolean) : Piece
}

/**
 * Plays backend-synthesized speech (D-54) sentence by sentence. All sentences are requested at once (at
 * most [MAX_IN_FLIGHT] in flight) and played strictly in order; sentence n+1 starts as soon as n ends
 * and n+1 is ready. [speak]'s `onFirstAudio` fires once, when the first sentence is ready. Audio is
 * cached per (key, sentence index, sentence), so replaying does not call the paid route again.
 * When a sentence cannot be produced or played, [onFailure] gets (key, the text not yet spoken, whether
 * the failure should make the fallback sticky) and the speaker goes idle; [FallbackSpeaker] reads that
 * text with the device voice. Main thread only.
 */
class CloudSpeaker(
    private val synthesizer: SpeechSynthesizer,
    private val player: AudioPlayer,
    cacheDir: File,
    parentScope: CoroutineScope,
    io: CoroutineDispatcher = Dispatchers.IO,
    clock: () -> Long = System::currentTimeMillis,
) : Speaker {
    // Own scope (same dispatcher, independent job): release() cancels it.
    private val scope = CoroutineScope(parentScope.coroutineContext + SupervisorJob())
    private val cache = SpeechCache(cacheDir, io, clock)
    private val _speakingKey = MutableStateFlow<String?>(null)
    override val speakingKey: StateFlow<String?> = _speakingKey.asStateFlow()
    private val _preparingKey = MutableStateFlow<String?>(null)
    override val preparingKey: StateFlow<String?> = _preparingKey.asStateFlow()

    var onFailure: (key: String, text: String, sticky: Boolean) -> Unit = { _, _, _ -> }

    private var job: Job? = null

    override fun speak(key: String, text: String, language: String?, onFirstAudio: () -> Unit) {
        halt()
        // Preparing until the first audio actually starts; only then Reading.
        _speakingKey.value = null
        _preparingKey.value = key
        if (!scope.isActive) return fail(key, text, sticky = false)
        val sentences = splitSentences(text)
        if (text.length > MAX_SPEECH_CHARS || sentences.isEmpty()) return fail(key, text, sticky = false)
        val lang = language ?: speechLocale(text).language
        job = scope.launch { pipeline(key, text, sentences, lang, onFirstAudio) }
    }

    private suspend fun pipeline(key: String, text: String, sentences: List<String>, lang: String, onFirstAudio: () -> Unit) =
        coroutineScope {
            val gate = Semaphore(MAX_IN_FLIGHT)
            val pieces = sentences.mapIndexed { i, s -> async { gate.withPermit { piece(key, i, s, lang) } } }
            for ((i, deferred) in pieces.withIndex()) {
                val p = deferred.await()
                val file = (p as? Piece.Ready)?.file
                val ok = file != null && try {
                    if (i == 0) {
                        _speakingKey.value = key
                        _preparingKey.compareAndSet(key, null)
                        onFirstAudio()
                    }
                    play(file)
                } catch (e: CancellationException) {
                    throw e
                } catch (e: Exception) {
                    false
                }
                if (!ok) {
                    pieces.forEach { it.cancel() }
                    val rest = if (i == 0) text else sentences.drop(i).joinToString(" ")
                    return@coroutineScope fail(key, rest, sticky = (p as? Piece.Failed)?.sticky ?: false)
                }
            }
            _speakingKey.compareAndSet(key, null)
        }

    private suspend fun piece(key: String, index: Int, sentence: String, lang: String): Piece {
        // Any unexpected exception fails this sentence only (device voice reads the rest); never a crash.
        return try {
            cache.get(key, index, sentence)?.let { return Piece.Ready(it) }
            when (val r = synthesizer.synthesize(sentence, lang)) {
                is ApiResult.Success ->
                    cache.put(key, index, sentence, r.value.bytes, r.value.extension)?.let { Piece.Ready(it) }
                        ?: Piece.Failed(sticky = false)
                is ApiResult.Failure -> Piece.Failed(
                    when (val k = r.kind) {
                        FailureKind.Network, FailureKind.Timeout -> true
                        is FailureKind.Server -> k.status >= 500
                    },
                )
            }
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            Piece.Failed(sticky = false)
        }
    }

    /** True when the file played to the end; a playback error drops the cached file. */
    private suspend fun play(file: File): Boolean = suspendCancellableCoroutine { c ->
        player.play(
            file,
            onDone = { if (c.isActive) c.resume(true) },
            onError = { file.delete(); if (c.isActive) c.resume(false) },
        )
    }

    private fun fail(key: String, text: String, sticky: Boolean) {
        _speakingKey.compareAndSet(key, null)
        _preparingKey.compareAndSet(key, null)
        onFailure(key, text, sticky)
    }

    private fun halt() {
        job?.cancel()
        job = null
        player.stop()
    }

    override fun stop() {
        halt()
        _speakingKey.value = null
        _preparingKey.value = null
    }

    override fun release() {
        stop()
        player.release()
        scope.cancel()
    }
}

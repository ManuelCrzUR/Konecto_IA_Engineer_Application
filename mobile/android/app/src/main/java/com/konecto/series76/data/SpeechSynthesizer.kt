package com.konecto.series76.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout

class SpeechAudio(val bytes: ByteArray, val mimeType: String) {
    /** File extension for the cache: WAV for PCM-wrapped audio, MP3 otherwise. */
    val extension: String get() = if (mimeType.contains("wav", ignoreCase = true)) "wav" else "mp3"
}

/** Text-to-speech through the backend (D-54). [language] is "es", "en" or null. */
interface SpeechSynthesizer {
    suspend fun synthesize(text: String, language: String?): ApiResult<SpeechAudio>
}

const val SPEECH_TIMEOUT_MS = 8_000L

class HttpSpeechSynthesizer(
    private val api: ApiService,
    private val timeoutMs: Long = SPEECH_TIMEOUT_MS,
) : SpeechSynthesizer {
    override suspend fun synthesize(text: String, language: String?): ApiResult<SpeechAudio> =
        try {
            // One overall budget: connect, wait for the model and download the audio.
            withTimeout(timeoutMs) {
                apiCall {
                    val body = api.speech(SpeechRequest(text, language))
                    val mime = body.contentType()?.let { "${it.type}/${it.subtype}" } ?: "audio/mpeg"
                    // Read the bytes off the caller's (main) thread.
                    SpeechAudio(withContext(Dispatchers.IO) { body.bytes() }, mime)
                }
            }
        } catch (e: TimeoutCancellationException) {
            ApiResult.Failure(FailureKind.Timeout, "Speech took too long")
        }
}

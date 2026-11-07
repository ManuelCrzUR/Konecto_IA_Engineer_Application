package com.konecto.series76.voice

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.asSharedFlow

sealed interface VoiceEvent {
    data object Listening : VoiceEvent
    data class Partial(val text: String) : VoiceEvent
    data class Final(val text: String) : VoiceEvent
    data class Error(val message: String) : VoiceEvent
    data object Ended : VoiceEvent
}

/** Speech-to-text. Call every method from the main thread. */
interface VoiceInput {
    val events: Flow<VoiceEvent>
    fun start(languageTag: String?)
    fun stop()
    fun release()
}

internal fun recognizerErrorMessage(code: Int): String = when (code) {
    SpeechRecognizer.ERROR_NO_MATCH, SpeechRecognizer.ERROR_SPEECH_TIMEOUT -> "Didn't catch that, try again"
    SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS -> "Microphone permission needed"
    SpeechRecognizer.ERROR_NETWORK, SpeechRecognizer.ERROR_NETWORK_TIMEOUT,
    SpeechRecognizer.ERROR_SERVER -> "Network needed for speech recognition"
    SpeechRecognizer.ERROR_RECOGNIZER_BUSY, SpeechRecognizer.ERROR_CLIENT -> "Didn't catch that, try again"
    else -> "No speech recognizer on this device"
}

class AndroidVoiceInput(private val context: Context) : VoiceInput {
    private val _events = MutableSharedFlow<VoiceEvent>(extraBufferCapacity = 32)
    override val events: Flow<VoiceEvent> = _events.asSharedFlow()
    private var recognizer: SpeechRecognizer? = null

    private val listener = object : RecognitionListener {
        override fun onReadyForSpeech(params: Bundle?) { _events.tryEmit(VoiceEvent.Listening) }
        override fun onPartialResults(partialResults: Bundle?) {
            firstResult(partialResults)?.let { _events.tryEmit(VoiceEvent.Partial(it)) }
        }
        override fun onResults(results: Bundle?) {
            val text = firstResult(results)
            if (text != null) _events.tryEmit(VoiceEvent.Final(text))
            _events.tryEmit(VoiceEvent.Ended)
        }
        override fun onError(error: Int) {
            _events.tryEmit(VoiceEvent.Error(recognizerErrorMessage(error)))
            _events.tryEmit(VoiceEvent.Ended)
        }
        override fun onBeginningOfSpeech() {}
        override fun onRmsChanged(rmsdB: Float) {}
        override fun onBufferReceived(buffer: ByteArray?) {}
        override fun onEndOfSpeech() {}
        override fun onEvent(eventType: Int, params: Bundle?) {}
    }

    private fun firstResult(b: Bundle?): String? =
        b?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull()?.takeIf { it.isNotBlank() }

    override fun start(languageTag: String?) {
        if (!isAvailable(context)) {
            _events.tryEmit(VoiceEvent.Error("No speech recognizer on this device"))
            _events.tryEmit(VoiceEvent.Ended)
            return
        }
        val r = recognizer ?: SpeechRecognizer.createSpeechRecognizer(context).also {
            it.setRecognitionListener(listener)
            recognizer = it
        }
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
            if (languageTag != null) putExtra(RecognizerIntent.EXTRA_LANGUAGE, languageTag)
        }
        r.startListening(intent)
    }

    override fun stop() { recognizer?.stopListening() }

    override fun release() {
        recognizer?.destroy()
        recognizer = null
    }

    companion object {
        fun isAvailable(context: Context): Boolean = SpeechRecognizer.isRecognitionAvailable(context)
    }
}

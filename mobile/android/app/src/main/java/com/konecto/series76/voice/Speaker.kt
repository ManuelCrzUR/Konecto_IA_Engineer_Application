package com.konecto.series76.voice

import android.content.Context
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/** Text-to-speech. [speakingKey] is the key of the message being read, or null. Main thread only. */
interface Speaker {
    val speakingKey: StateFlow<String?>
    fun speak(key: String, text: String)
    fun stop()
    fun release()
}

class AndroidSpeaker(private val context: Context) : Speaker {
    private val _speakingKey = MutableStateFlow<String?>(null)
    override val speakingKey: StateFlow<String?> = _speakingKey.asStateFlow()

    private var tts: TextToSpeech? = null
    private var ready = false
    private var pending: Pair<String, String>? = null

    private val progress = object : UtteranceProgressListener() {
        override fun onStart(utteranceId: String?) {}
        override fun onDone(utteranceId: String?) = clear(utteranceId)
        @Deprecated("Deprecated in Java")
        override fun onError(utteranceId: String?) = clear(utteranceId)
        override fun onStop(utteranceId: String?, interrupted: Boolean) = clear(utteranceId)
    }

    // Callbacks arrive on a binder thread; MutableStateFlow is thread-safe. Ignore stale ids so a
    // flushed utterance does not clear the key of the one that replaced it.
    private fun clear(id: String?) { _speakingKey.compareAndSet(id, null) }

    private fun engine(): TextToSpeech = tts ?: TextToSpeech(context) { status ->
        ready = status == TextToSpeech.SUCCESS
        val p = pending
        pending = null
        if (ready && p != null) speakNow(p.first, p.second) else if (!ready) _speakingKey.value = null
    }.also {
        it.setOnUtteranceProgressListener(progress)
        tts = it
    }

    override fun speak(key: String, text: String) {
        engine()
        _speakingKey.value = key
        if (ready) speakNow(key, text) else pending = key to text
    }

    private fun speakNow(key: String, text: String) {
        val e = tts ?: return
        val result = e.setLanguage(speechLocale(text))
        if (result == TextToSpeech.LANG_MISSING_DATA || result == TextToSpeech.LANG_NOT_SUPPORTED) {
            e.language = java.util.Locale.getDefault()
        }
        e.speak(text, TextToSpeech.QUEUE_FLUSH, null, key)
    }

    override fun stop() {
        pending = null
        tts?.stop()
        _speakingKey.value = null
    }

    override fun release() {
        pending = null
        tts?.stop()
        tts?.shutdown()
        tts = null
        ready = false
        _speakingKey.value = null
    }
}

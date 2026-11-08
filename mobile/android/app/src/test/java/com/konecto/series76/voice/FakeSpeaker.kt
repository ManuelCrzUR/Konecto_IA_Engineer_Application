package com.konecto.series76.voice

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

class FakeSpeaker : Speaker {
    val spoken = mutableListOf<Pair<String, String>>()
    private val _key = MutableStateFlow<String?>(null)
    override val speakingKey: StateFlow<String?> = _key
    val languages = mutableListOf<String?>()
    var onFirstAudio: (() -> Unit)? = null
    override fun speak(key: String, text: String, language: String?, onFirstAudio: () -> Unit) {
        spoken += key to text; languages += language; _key.value = key; this.onFirstAudio = onFirstAudio
    }
    override fun stop() { _key.value = null }
    override fun release() { _key.value = null }
}

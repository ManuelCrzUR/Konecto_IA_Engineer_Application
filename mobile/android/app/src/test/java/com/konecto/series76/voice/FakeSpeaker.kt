package com.konecto.series76.voice

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

class FakeSpeaker : Speaker {
    val spoken = mutableListOf<Pair<String, String>>()
    private val _key = MutableStateFlow<String?>(null)
    override val speakingKey: StateFlow<String?> = _key
    override fun speak(key: String, text: String) { spoken += key to text; _key.value = key }
    override fun stop() { _key.value = null }
    override fun release() { _key.value = null }
}

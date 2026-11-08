package com.konecto.series76.voice

import android.media.AudioAttributes
import android.media.MediaPlayer
import java.io.File

/** Plays one audio file at a time. Callbacks run on the main thread and never fire after [stop]. */
interface AudioPlayer {
    fun play(file: File, onDone: () -> Unit, onError: () -> Unit)
    fun stop()
    fun release()
}

class MediaAudioPlayer : AudioPlayer {
    private var player: MediaPlayer? = null

    override fun play(file: File, onDone: () -> Unit, onError: () -> Unit) {
        stop()
        val p = MediaPlayer()
        player = p
        try {
            p.setAudioAttributes(
                AudioAttributes.Builder()
                    .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                    .setUsage(AudioAttributes.USAGE_MEDIA)
                    .build(),
            )
            p.setDataSource(file.absolutePath)
            p.setOnPreparedListener { if (player === p) it.start() }
            p.setOnCompletionListener { if (player === p) { discard(p); onDone() } }
            p.setOnErrorListener { _, _, _ -> if (player === p) { discard(p); onError() }; true }
            p.prepareAsync()
        } catch (e: Exception) {
            discard(p)
            onError()
        }
    }

    private fun discard(p: MediaPlayer) {
        if (player === p) player = null
        runCatching { p.release() }
    }

    override fun stop() {
        player?.let { discard(it) }
    }

    override fun release() = stop()
}

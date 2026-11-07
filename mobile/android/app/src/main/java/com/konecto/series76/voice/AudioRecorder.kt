package com.konecto.series76.voice

import android.content.Context
import android.media.MediaRecorder
import android.os.Build
import java.io.File

/** Records one question to a file. Call every method from the main thread. */
interface AudioRecorder {
    /** Starts recording; false when the microphone cannot be opened. */
    fun start(): Boolean

    /** Stops and returns the recorded file, or null when nothing usable was recorded. */
    fun stop(): File?

    /** Stops without keeping anything and deletes the file. Safe to call at any time. */
    fun cancel()
}

const val MAX_RECORDING_MS = 30_000

/** MediaRecorder's own limit sits after the caller's cap so the caller is the only normal stop. */
const val BACKSTOP_RECORDING_MS = MAX_RECORDING_MS + 1_000

/** A recording is worth keeping when the file has data, whether stop() succeeded, threw or was skipped. */
internal fun shouldKeepRecording(fileBytes: Long): Boolean = fileBytes > 0

/** AAC in an MPEG-4 container (.m4a), 16 kHz mono, about 64 kbps: small and accepted by the backend. */
class MediaAudioRecorder(private val context: Context) : AudioRecorder {
    private var recorder: MediaRecorder? = null
    private var file: File? = null
    private var maxReached = false

    @Suppress("DEPRECATION")
    override fun start(): Boolean {
        cancel()
        maxReached = false
        val out = File(context.cacheDir, "question-${System.nanoTime()}.m4a")
        val r = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) MediaRecorder(context) else MediaRecorder()
        return try {
            r.setAudioSource(MediaRecorder.AudioSource.MIC)
            r.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
            r.setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
            r.setAudioChannels(1)
            r.setAudioSamplingRate(16_000)
            r.setAudioEncodingBitRate(64_000)
            r.setMaxDuration(BACKSTOP_RECORDING_MS) // backstop only; the caller stops at MAX_RECORDING_MS
            r.setOnInfoListener { _, what, _ ->
                if (what == MediaRecorder.MEDIA_RECORDER_INFO_MAX_DURATION_REACHED) maxReached = true
            }
            r.setOutputFile(out.absolutePath)
            r.prepare()
            r.start()
            recorder = r
            file = out
            true
        } catch (e: Exception) { // IOException, IllegalStateException, RuntimeException from a busy mic
            runCatching { r.release() }
            out.delete()
            false
        }
    }

    override fun stop(): File? {
        val r = recorder ?: return null
        val f = file
        recorder = null
        file = null
        val alreadyStopped = maxReached // MediaRecorder stopped itself; calling stop() again can throw
        return try {
            if (!alreadyStopped) r.stop()
            keepOrDelete(f)
        } catch (e: RuntimeException) { // stop() throws when no audio data was captured
            keepOrDelete(f)
        } finally {
            runCatching { r.release() }
        }
    }

    private fun keepOrDelete(f: File?): File? {
        if (f != null && shouldKeepRecording(f.length())) return f
        f?.delete()
        return null
    }

    override fun cancel() {
        recorder?.let { r ->
            runCatching { r.stop() }
            runCatching { r.release() }
        }
        recorder = null
        file?.delete()
        file = null
    }
}

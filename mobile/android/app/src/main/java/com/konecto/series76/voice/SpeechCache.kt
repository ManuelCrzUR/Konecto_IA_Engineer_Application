package com.konecto.series76.voice

import android.util.Log
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.withContext
import java.io.File
import java.security.MessageDigest

private const val CACHE_MAX_AGE_MS = 60 * 60 * 1000L
internal const val CACHE_MAX_FILES = 80
private const val TMP_SUFFIX = ".tmp"
private const val TAG = "SpeechCache"

/** Audio files per (message key, sentence index, sentence text). Contract: [get] hit or null, [put] writes and prunes. */
class SpeechCache(
    private val dir: File,
    private val io: CoroutineDispatcher,
    private val clock: () -> Long,
) {
    /** Cache hit, or null. A hit is touched so pruning treats it as recent. Never throws: IO errors are a miss. */
    suspend fun get(key: String, index: Int, text: String): File? = withContext(io) {
        try {
            val base = name(key, index, text)
            listOf("mp3", "wav").map { File(dir, "$base.$it") }.firstOrNull { it.isFile && it.length() > 0 }
                ?.also { it.setLastModified(clock()) }
        } catch (e: Exception) {
            Log.w(TAG, "cache read failed", e)
            null
        }
    }

    /**
     * Writes to a temp file in the same directory, then renames it, so a reader never sees a partial
     * file. Returns null (never throws) when the cache cannot be written; the caller treats that as a failure.
     */
    suspend fun put(key: String, index: Int, text: String, bytes: ByteArray, extension: String): File? = withContext(io) {
        var tmp: File? = null
        try {
            prune()
            if (!dir.isDirectory && !dir.mkdirs() && !dir.isDirectory) return@withContext null
            val target = File(dir, "${name(key, index, text)}.$extension")
            tmp = File(dir, "${target.name}$TMP_SUFFIX")
            tmp.writeBytes(bytes)
            tmp.setLastModified(clock())
            if (!tmp.renameTo(target)) {
                tmp.delete()
                return@withContext null
            }
            target
        } catch (e: Exception) {
            Log.w(TAG, "cache write failed", e)
            runCatching { tmp?.delete() }
            null
        }
    }

    /** Delete files older than an hour, then keep only the newest [CACHE_MAX_FILES] - 1 (room for the new one). */
    private fun prune() {
        // Orphaned temp files (a crash mid-write) are old enough to go with the rest.
        dir.listFiles { f -> f.name.endsWith(TMP_SUFFIX) }?.filter { clock() - it.lastModified() > CACHE_MAX_AGE_MS }?.forEach { it.delete() }
        val files = dir.listFiles { f -> f.isFile && (f.name.endsWith(".mp3") || f.name.endsWith(".wav")) } ?: return
        val now = clock()
        val fresh = files.filter { f -> (now - f.lastModified() <= CACHE_MAX_AGE_MS).also { if (!it) f.delete() } }
        fresh.sortedByDescending { it.lastModified() }.drop(CACHE_MAX_FILES - 1).forEach { it.delete() }
    }

    private fun name(key: String, index: Int, text: String): String =
        MessageDigest.getInstance("SHA-256").digest("$key\n$index\n$text".toByteArray())
            .joinToString("") { "%02x".format(it) }.take(32)
}

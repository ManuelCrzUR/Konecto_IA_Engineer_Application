package com.konecto.series76.data

import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.withTimeout
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.File

/** Speech-to-text through the backend. [language] is "es", "en" or null. */
interface Transcriber {
    suspend fun transcribe(audio: File, language: String?): ApiResult<String>
}

const val TRANSCRIBE_TIMEOUT_MS = 15_000L

class HttpTranscriber(
    private val api: ApiService,
    private val timeoutMs: Long = TRANSCRIBE_TIMEOUT_MS,
) : Transcriber {
    override suspend fun transcribe(audio: File, language: String?): ApiResult<String> {
        val part = MultipartBody.Part.createFormData(
            "audio", "question.m4a", audio.asRequestBody("audio/mp4".toMediaType()),
        )
        val lang: RequestBody? = language?.toRequestBody("text/plain".toMediaType())
        return try {
            // withTimeout cancels the Retrofit call, so one 15 s budget covers connect, upload and answer.
            when (val r = withTimeout(timeoutMs) { apiCall { api.transcribe(part, lang) } }) {
                is ApiResult.Success -> ApiResult.Success(r.value.text)
                is ApiResult.Failure -> r
            }
        } catch (e: TimeoutCancellationException) {
            ApiResult.Failure(FailureKind.Timeout, "Transcription took too long")
        }
    }
}

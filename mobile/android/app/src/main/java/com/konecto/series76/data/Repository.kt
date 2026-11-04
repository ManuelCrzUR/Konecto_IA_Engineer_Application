package com.konecto.series76.data

import kotlinx.coroutines.CancellationException
import retrofit2.HttpException
import java.io.IOException
import java.net.SocketTimeoutException

private const val SESSION_HEADER = "X-Session-Id"

class Repository(private val api: ApiService) : AssistantRepository {

    override suspend fun sendMessage(sessionId: String?, query: String): ApiResult<ConversationResponse> =
        call { api.conversation(ConversationRequest(sessionId, query)) }

    override suspend fun sessions(): ApiResult<List<SessionOut>> = call { api.sessions() }

    override suspend fun messages(sessionId: String): ApiResult<List<MessageOut>> =
        call { api.messages(sessionId) }

    private suspend fun <T> call(block: suspend () -> T): ApiResult<T> =
        try {
            ApiResult.Success(block())
        } catch (e: CancellationException) {
            throw e
        } catch (e: HttpException) {
            httpFailure(e)
        } catch (e: IllegalArgumentException) {
            // SerializationException extends IllegalArgumentException: 200 with a body we cannot decode.
            ApiResult.Failure(FailureKind.Server(200, "bad_response"), "The server sent an unexpected response")
        } catch (e: SocketTimeoutException) {
            ApiResult.Failure(FailureKind.Timeout, "The server took too long to answer")
        } catch (e: IOException) {
            ApiResult.Failure(FailureKind.Network, "Cannot reach the server")
        }

    private fun httpFailure(e: HttpException): ApiResult.Failure {
        val body = try {
            e.response()?.errorBody()?.string()
        } catch (_: IOException) {
            null
        }
        val err = body?.let { runCatching { ApiJson.decodeFromString<ErrorOut>(it) }.getOrNull() }
        val message = err?.detail ?: err?.error ?: "Server error (${e.code()})"
        val sessionId = e.response()?.headers()?.get(SESSION_HEADER)
        return ApiResult.Failure(FailureKind.Server(e.code(), err?.error), message, sessionId)
    }
}

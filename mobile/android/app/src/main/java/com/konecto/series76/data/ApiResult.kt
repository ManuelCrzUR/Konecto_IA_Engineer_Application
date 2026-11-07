package com.konecto.series76.data

sealed interface FailureKind {
    data object Network : FailureKind
    data object Timeout : FailureKind
    data class Server(val status: Int, val errorCode: String?) : FailureKind {
        val isTurnInProgress: Boolean get() = status == 409 && errorCode == "turn_in_progress"
    }
}

sealed interface ApiResult<out T> {
    data class Success<T>(val value: T) : ApiResult<T>
    data class Failure(
        val kind: FailureKind,
        val message: String,
        /** Session the server created/used for a failed send (header X-Session-Id), so Retry can reuse it. */
        val sessionId: String? = null,
    ) : ApiResult<Nothing> {
        /** Worth offering Retry: transient problems only, never 4xx (except 409 turn_in_progress: the turn will finish). */
        val retryable: Boolean
            get() = when (kind) {
                FailureKind.Network, FailureKind.Timeout -> true
                is FailureKind.Server -> kind.status >= 500 || kind.isTurnInProgress
            }
    }
}

package com.konecto.series76.data

/** What the ViewModels depend on; [Repository] is the HTTP implementation, tests use fakes. */
interface AssistantRepository {
    suspend fun sendMessage(sessionId: String?, query: String): ApiResult<ConversationResponse>
    suspend fun sessions(): ApiResult<List<SessionOut>>
    /** GET /sessions?q=: sessions whose title or messages contain [q], each with its match. */
    suspend fun searchSessions(q: String): ApiResult<List<SessionOut>>
    suspend fun messages(sessionId: String): ApiResult<List<MessageOut>>

    /** GET /health: true on 2xx, false on any failure. */
    suspend fun health(): Boolean
}

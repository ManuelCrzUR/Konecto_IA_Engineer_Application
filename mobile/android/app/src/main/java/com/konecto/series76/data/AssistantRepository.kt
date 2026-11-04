package com.konecto.series76.data

/** What the ViewModels depend on; [Repository] is the HTTP implementation, tests use fakes. */
interface AssistantRepository {
    suspend fun sendMessage(sessionId: String?, query: String): ApiResult<ConversationResponse>
    suspend fun sessions(): ApiResult<List<SessionOut>>
    suspend fun messages(sessionId: String): ApiResult<List<MessageOut>>
}

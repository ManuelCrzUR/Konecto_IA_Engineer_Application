package com.konecto.series76.data

class Repository(private val api: ApiService) : AssistantRepository {

    override suspend fun sendMessage(sessionId: String?, query: String): ApiResult<ConversationResponse> =
        apiCall { api.conversation(ConversationRequest(sessionId, query)) }

    override suspend fun sessions(): ApiResult<List<SessionOut>> = apiCall { api.sessions() }

    override suspend fun searchSessions(q: String): ApiResult<List<SessionOut>> =
        apiCall { api.sessions(q) }

    override suspend fun messages(sessionId: String): ApiResult<List<MessageOut>> =
        apiCall { api.messages(sessionId) }

    override suspend fun health(): Boolean =
        apiCall { api.health() }.let { it is ApiResult.Success && it.value.isSuccessful }
}

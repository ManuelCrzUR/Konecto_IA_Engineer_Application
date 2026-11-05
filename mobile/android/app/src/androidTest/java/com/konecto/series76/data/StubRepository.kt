package com.konecto.series76.data

/** Base for test fakes: every call fails loudly, so a fake overrides only what its test uses. */
open class StubRepository : AssistantRepository {
    override suspend fun sendMessage(sessionId: String?, query: String): ApiResult<ConversationResponse> = error("unused")
    override suspend fun sessions(): ApiResult<List<SessionOut>> = error("unused")
    override suspend fun searchSessions(q: String): ApiResult<List<SessionOut>> = error("unused")
    override suspend fun messages(sessionId: String): ApiResult<List<MessageOut>> = error("unused")
    override suspend fun health(): Boolean = error("unused")
}

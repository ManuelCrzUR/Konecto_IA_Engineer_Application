package com.konecto.series76.data

import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path

interface ApiService {
    @POST("api/conversation")
    suspend fun conversation(@Body request: ConversationRequest): ConversationResponse

    @GET("api/sessions")
    suspend fun sessions(): List<SessionOut>

    @GET("api/sessions/{id}/messages")
    suspend fun messages(@Path("id") sessionId: String): List<MessageOut>
}

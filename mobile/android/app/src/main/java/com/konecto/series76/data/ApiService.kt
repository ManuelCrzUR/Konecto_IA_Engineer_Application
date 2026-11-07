package com.konecto.series76.data

import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

interface ApiService {
    @GET("health")
    suspend fun health(): Response<Unit>

    @POST("api/conversation")
    suspend fun conversation(@Body request: ConversationRequest): ConversationResponse

    @GET("api/sessions")
    suspend fun sessions(@Query("q") q: String? = null): List<SessionOut>

    @GET("api/sessions/{id}/messages")
    suspend fun messages(@Path("id") sessionId: String): List<MessageOut>

    @POST("api/auth/login")
    suspend fun login(@Body request: LoginRequest): LoginResponse

    @POST("api/auth/logout")
    suspend fun logout(): Response<Unit>

    @GET("api/auth/me")
    suspend fun me(): UserOut
}

package com.konecto.series76.data

import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Header
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

    @POST(LOGIN_PATH)
    suspend fun login(@Body request: LoginRequest): LoginResponse

    /** Explicit header: logout runs after the local session is cleared, so the interceptor has no token. */
    @POST("api/auth/logout")
    suspend fun logout(@Header("Authorization") authorization: String): Response<Unit>

    companion object {
        /** Shared with [AuthInterceptor]: a 401 here is a wrong password, not a lost session. */
        const val LOGIN_PATH = "api/auth/login"
    }
}

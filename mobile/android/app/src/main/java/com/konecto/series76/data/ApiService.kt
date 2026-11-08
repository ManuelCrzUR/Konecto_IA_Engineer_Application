package com.konecto.series76.data

import okhttp3.MultipartBody
import okhttp3.RequestBody
import okhttp3.ResponseBody
import retrofit2.Response
import retrofit2.http.Multipart
import retrofit2.http.Part
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

    @Multipart
    @POST("api/transcribe")
    suspend fun transcribe(
        @Part audio: MultipartBody.Part,
        @Part("language") language: RequestBody?,
    ): TranscribeResponse

    /** Raw audio bytes (audio/mpeg or audio/wav); a few hundred KB at most, so no @Streaming. */
    @POST("api/speech")
    suspend fun speech(@Body request: SpeechRequest): ResponseBody

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

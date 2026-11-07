package com.konecto.series76.data

import okhttp3.Interceptor
import okhttp3.Response

/**
 * Adds the bearer token when one exists. A 401 on any route except login means the session is
 * gone, so [onUnauthorized] fires once for that response (a wrong password is not a lost session).
 */
class AuthInterceptor(
    private val tokenProvider: () -> String?,
    private val onUnauthorized: () -> Unit,
) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val request = chain.request()
        val token = tokenProvider()
        val authed = if (token != null) {
            request.newBuilder().header("Authorization", "Bearer $token").build()
        } else {
            request
        }
        val response = chain.proceed(authed)
        if (response.code == 401 && !request.url.encodedPath.endsWith(ApiService.LOGIN_PATH)) onUnauthorized()
        return response
    }
}

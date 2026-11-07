package com.konecto.series76.data

import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Before
import org.junit.Test

class AuthInterceptorTest {
    private val server = MockWebServer()
    private var token: String? = null
    private var unauthorized = 0

    private val client by lazy {
        OkHttpClient.Builder().addInterceptor(AuthInterceptor({ token }, { unauthorized++ })).build()
    }

    @Before fun setUp() = server.start()
    @After fun tearDown() = server.shutdown()

    private fun get(path: String) = client.newCall(Request.Builder().url(server.url(path)).build()).execute().close()

    @Test fun addsBearerWhenTokenExists() {
        token = "abc"; server.enqueue(MockResponse().setResponseCode(200))
        get("api/sessions")
        assertEquals("Bearer abc", server.takeRequest().getHeader("Authorization"))
    }

    @Test fun noHeaderWithoutToken() {
        server.enqueue(MockResponse().setResponseCode(200))
        get("api/auth/login")
        assertNull(server.takeRequest().getHeader("Authorization"))
    }

    @Test fun unauthorizedFiresOncePerResponse() {
        token = "abc"; server.enqueue(MockResponse().setResponseCode(401))
        get("api/sessions")
        assertEquals(1, unauthorized)
    }

    @Test fun loginUnauthorizedIsIgnored() {
        server.enqueue(MockResponse().setResponseCode(401))
        get("api/auth/login")
        assertEquals(0, unauthorized)
    }

    @Test fun successDoesNotFire() {
        token = "abc"; server.enqueue(MockResponse().setResponseCode(200))
        get("api/sessions")
        assertEquals(0, unauthorized)
    }
}

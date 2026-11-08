package com.konecto.series76.data

import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okio.Buffer
import org.junit.After
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test

class HttpSpeechSynthesizerTest {
    private val server = MockWebServer()
    private lateinit var synth: HttpSpeechSynthesizer

    @Before fun setUp() {
        server.start()
        val api = ApiClient.create(server.url("/").toString(), interceptor = AuthInterceptor({ "tok" }, {}))
        synth = HttpSpeechSynthesizer(api, timeoutMs = 500)
    }

    @After fun tearDown() = server.shutdown()

    @Test fun sendsJsonWithBearerAndReturnsBytesAndMime() = runBlocking {
        val audio = byteArrayOf(1, 2, 3, 4)
        server.enqueue(
            MockResponse().setHeader("Content-Type", "audio/mpeg").setHeader("X-Speech-Model", "m")
                .setBody(Buffer().write(audio)),
        )
        val r = synth.synthesize("Hola", "es") as ApiResult.Success
        assertArrayEquals(audio, r.value.bytes)
        assertEquals("audio/mpeg", r.value.mimeType)
        assertEquals("mp3", r.value.extension)
        val req = server.takeRequest()
        assertEquals("/api/speech", req.path)
        assertEquals("Bearer tok", req.getHeader("Authorization"))
        assertEquals("""{"text":"Hola","language":"es"}""", req.body.readUtf8())
    }

    @Test fun wavMimeGivesWavExtension() = runBlocking {
        server.enqueue(MockResponse().setHeader("Content-Type", "audio/wav").setBody(Buffer().write(byteArrayOf(9))))
        val r = synth.synthesize("Hi", null) as ApiResult.Success
        assertEquals("audio/wav", r.value.mimeType)
        assertEquals("wav", r.value.extension)
    }

    @Test fun mapsServiceUnavailable() = runBlocking {
        server.enqueue(
            MockResponse().setResponseCode(503).setHeader("Content-Type", "application/json")
                .setBody("""{"error":"speech_unavailable","detail":"Down"}"""),
        )
        val r = synth.synthesize("Hola", "es") as ApiResult.Failure
        assertEquals(FailureKind.Server(503, "speech_unavailable"), r.kind)
    }

    @Test fun slowServerBecomesTimeout() = runBlocking {
        server.enqueue(MockResponse().setBodyDelay(3, java.util.concurrent.TimeUnit.SECONDS).setBody("x"))
        val r = synth.synthesize("Hola", "es") as ApiResult.Failure
        assertEquals(FailureKind.Timeout, r.kind)
    }
}

package com.konecto.series76.data

import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.io.File

class HttpTranscriberTest {
    private val server = MockWebServer()
    private lateinit var transcriber: HttpTranscriber
    private lateinit var audio: File

    @Before fun setUp() {
        server.start()
        audio = File.createTempFile("question", ".m4a").apply { writeBytes(byteArrayOf(1, 2, 3)); deleteOnExit() }
        val api = ApiClient.create(server.url("/").toString(), interceptor = AuthInterceptor({ "tok" }, {}))
        transcriber = HttpTranscriber(api, timeoutMs = 500)
    }

    @After fun tearDown() = server.shutdown()

    @Test fun sendsMultipartAudioWithBearer() = runBlocking {
        server.enqueue(
            MockResponse().setHeader("Content-Type", "application/json")
                .setBody("""{"text":"764A00-11300000/A","raw_text":"r","model":"m","seconds":2.5}"""),
        )
        val r = transcriber.transcribe(audio, "es")
        assertEquals(ApiResult.Success("764A00-11300000/A"), r)
        val req = server.takeRequest()
        assertEquals("/api/transcribe", req.path)
        assertEquals("Bearer tok", req.getHeader("Authorization"))
        val body = req.body.readUtf8()
        assertTrue(body.contains("""name="audio"; filename="question.m4a""""))
        assertTrue(body.contains("Content-Type: audio/mp4"))
        assertTrue(body.contains("""name="language""""))
    }

    @Test fun omitsLanguageWhenNull() = runBlocking {
        server.enqueue(MockResponse().setHeader("Content-Type", "application/json").setBody("""{"text":"x"}"""))
        transcriber.transcribe(audio, null)
        assertTrue(!server.takeRequest().body.readUtf8().contains("name=\"language\""))
    }

    @Test fun mapsServiceUnavailable() = runBlocking {
        server.enqueue(
            MockResponse().setResponseCode(503).setHeader("Content-Type", "application/json")
                .setBody("""{"error":"transcription_not_configured","detail":"Not configured"}"""),
        )
        val r = transcriber.transcribe(audio, null) as ApiResult.Failure
        assertEquals(FailureKind.Server(503, "transcription_not_configured"), r.kind)
        assertEquals("Not configured", r.message)
    }

    @Test fun slowServerBecomesTimeout() = runBlocking {
        server.enqueue(MockResponse().setBodyDelay(3, java.util.concurrent.TimeUnit.SECONDS).setBody("{}"))
        val r = transcriber.transcribe(audio, null) as ApiResult.Failure
        assertEquals(FailureKind.Timeout, r.kind)
    }
}

package com.konecto.series76.data

import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.jsonPrimitive
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.mockwebserver.SocketPolicy
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.JsonPrimitive

class RepositoryTest {
    private lateinit var server: MockWebServer
    private lateinit var repo: Repository

    private fun fixture(name: String): String =
        javaClass.getResource("/contract/$name.json")!!.readText()

    private fun json(name: String, code: Int = 200) = MockResponse()
        .setResponseCode(code)
        .setHeader("Content-Type", "application/json")
        .setBody(fixture(name))

    @Before fun setUp() {
        server = MockWebServer().also { it.start() }
        repo = Repository(ApiClient.create(server.url("/").toString()))
    }

    @After fun tearDown() { runCatching { server.shutdown() } }

    private fun <T> ok(r: ApiResult<T>): T {
        assertTrue("expected success but was $r", r is ApiResult.Success)
        return (r as ApiResult.Success).value
    }

    @Test fun recommendKeepsNumbersAsPrinted() = runBlocking {
        server.enqueue(json("conversation_recommend"))
        val r = ok(repo.sendMessage(null, "q"))
        assertEquals(4, r.products.size)
        val p = r.products[0]
        assertEquals("800", displayValue(p.fields["onoff_torque_nm"]))
        assertEquals("2.4", displayValue(p.fields["fla_60hz_a"]))
        assertEquals("3.8", displayValue(p.fields["lra_60hz_a"]))
        assertEquals(1, p.phase)
    }

    @Test fun debugTracesParse() = runBlocking {
        server.enqueue(json("conversation_recommend"))
        val t = ok(repo.sendMessage(null, "q")).debug.single()
        assertEquals("search_actuators", t.tool)
        assertTrue(t.params.containsKey("min_torque"))
        assertTrue(t.result.jsonObject.isNotEmpty())
        assertEquals(7.58, t.durationMs!!, 0.0)
    }

    @Test fun otherConversationFixturesParse() = runBlocking {
        for (n in listOf("conversation_no_data", "conversation_not_found", "conversation_followup")) {
            server.enqueue(json(n))
            val r = ok(repo.sendMessage("s", "q"))
            assertTrue(n, r.answer.isNotEmpty())
            assertEquals(n, 1, r.debug.size)
        }
    }

    @Test fun noDataProductHasNullFields() = runBlocking {
        server.enqueue(json("conversation_no_data"))
        val p = ok(repo.sendMessage(null, "q")).products.single()
        assertEquals(false, p.hasData)
        p.fields.values.forEach { assertEquals("—", displayValue(it)) }
    }

    @Test fun sessionsAndMessagesParse() = runBlocking {
        server.enqueue(json("sessions"))
        server.enqueue(json("messages"))
        val s = ok(repo.sessions())
        assertEquals(5, s.size)
        assertNull(s[0].userId)
        val m = ok(repo.messages(s[0].id))
        assertEquals(4, m.size)
        assertEquals(4, m[1].products.size)
        assertEquals(1, m[1].trace.size)
        assertEquals("/api/sessions", server.takeRequest().path)
        assertEquals("/api/sessions/${s[0].id}/messages", server.takeRequest().path)
    }

    @Test fun notFoundIsServerFailure() = runBlocking {
        server.enqueue(json("error_404", 404))
        val f = repo.sendMessage("x", "q") as ApiResult.Failure
        assertEquals(FailureKind.Server(404, "session_not_found"), f.kind)
        assertEquals("No conversation with id 00000000-0000-0000-0000-000000000000", f.message)
    }

    @Test fun validationErrorIsServerFailure() = runBlocking {
        server.enqueue(json("error_422", 422))
        val f = repo.sendMessage(null, "") as ApiResult.Failure
        assertEquals(FailureKind.Server(422, "validation_error"), f.kind)
        assertTrue(f.message.contains("at least 1 character"))
    }

    @Test fun nonJsonServerErrorFallsBack() = runBlocking {
        server.enqueue(MockResponse().setResponseCode(500).setBody("boom"))
        val f = repo.sessions() as ApiResult.Failure
        assertEquals(FailureKind.Server(500, null), f.kind)
    }

    @Test fun htmlWith200IsBadResponseNotCrash() = runBlocking {
        server.enqueue(MockResponse().setResponseCode(200).setHeader("Content-Type", "application/json").setBody("<html>captive portal</html>"))
        val f = repo.sendMessage(null, "q") as ApiResult.Failure
        assertEquals(FailureKind.Server(200, "bad_response"), f.kind)
        assertEquals("The server sent an unexpected response", f.message)
    }

    @Test fun jsonMissingRequiredFieldIsBadResponse() = runBlocking {
        server.enqueue(MockResponse().setResponseCode(200).setHeader("Content-Type", "application/json").setBody("""{"session_id":"s"}"""))
        val f = repo.sendMessage(null, "q") as ApiResult.Failure
        assertEquals(FailureKind.Server(200, "bad_response"), f.kind)
    }

    @Test fun errorResponseSurfacesSessionIdHeader() = runBlocking {
        server.enqueue(json("error_404", 503).setHeader("X-Session-Id", "sid-9"))
        val f = repo.sendMessage(null, "q") as ApiResult.Failure
        assertEquals("sid-9", f.sessionId)
        assertTrue(f.retryable)
        server.enqueue(json("error_404", 404))
        val g = repo.sendMessage(null, "q") as ApiResult.Failure
        assertNull(g.sessionId)
        assertEquals(false, g.retryable)
    }

    @Test fun serverDownIsNetwork() = runBlocking {
        server.shutdown()
        val f = repo.sessions() as ApiResult.Failure
        assertEquals(FailureKind.Network, f.kind)
        assertEquals("Cannot reach the server", f.message)
    }

    @Test fun slowResponseIsTimeout() = runBlocking {
        val quick = Repository(ApiClient.create(server.url("/").toString(), readTimeoutSeconds = 1))
        server.enqueue(json("sessions").setSocketPolicy(SocketPolicy.NO_RESPONSE))
        val f = quick.sessions() as ApiResult.Failure
        assertEquals(FailureKind.Timeout, f.kind)
        assertEquals("The server took too long to answer", f.message)
    }

    @Test fun requestShape() = runBlocking {
        server.enqueue(json("conversation_followup"))
        server.enqueue(json("conversation_followup"))
        repo.sendMessage(null, "hello")
        repo.sendMessage("abc", "again")
        val r1 = server.takeRequest()
        assertEquals("POST", r1.method)
        assertEquals("/api/conversation", r1.path)
        val b1 = ApiJson.parseToJsonElement(r1.body.readUtf8()).jsonObject
        assertEquals("hello", b1["query"]!!.jsonPrimitive.content)
        assertEquals(JsonNull, b1["session_id"] ?: JsonNull)
        val b2 = ApiJson.parseToJsonElement(server.takeRequest().body.readUtf8()).jsonObject
        assertEquals("abc", b2["session_id"]!!.jsonPrimitive.content)
    }

    @Test fun displayValueNull() {
        assertEquals("—", displayValue(null))
        assertEquals("—", displayValue(JsonNull))
        assertEquals("6.5", displayValue(JsonPrimitive(6.5)))
    }
}

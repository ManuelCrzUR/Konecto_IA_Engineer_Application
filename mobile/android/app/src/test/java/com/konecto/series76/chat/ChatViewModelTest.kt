package com.konecto.series76.chat

import androidx.lifecycle.SavedStateHandle
import com.konecto.series76.data.ApiResult
import com.konecto.series76.data.AssistantRepository
import com.konecto.series76.data.StubRepository
import com.konecto.series76.data.ConversationResponse
import com.konecto.series76.data.FailureKind
import com.konecto.series76.data.MessageOut
import com.konecto.series76.data.Product
import com.konecto.series76.data.SessionOut
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import kotlinx.serialization.json.JsonPrimitive
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class ChatViewModelTest {
    private val product = Product(
        partNumber = "764X30-11320000/A", enclosure = "explosionproof", voltage = "220V", phase = 1,
        service = "on_off_and_modulating", hasData = true, fields = mapOf("onoff_torque_nm" to JsonPrimitive(800)),
    )

    private class FakeRepo : StubRepository() {
        val sent = mutableListOf<Pair<String?, String>>()
        var sendResults = ArrayDeque<ApiResult<ConversationResponse>>()
        var history: ApiResult<List<MessageOut>> = ApiResult.Success(emptyList())
        override suspend fun sendMessage(sessionId: String?, query: String): ApiResult<ConversationResponse> {
            sent += sessionId to query
            return sendResults.removeFirst()
        }
        override suspend fun sessions(): ApiResult<List<SessionOut>> = ApiResult.Success(emptyList())
        override suspend fun messages(sessionId: String) = history
    }

    private fun vm(repo: AssistantRepository, id: String?, handle: SavedStateHandle = SavedStateHandle()): ChatViewModel {
        if (id != null) handle["chat_session_id"] = id
        return ChatViewModel(repo, handle)
    }

    @Before fun setUp() = Dispatchers.setMain(StandardTestDispatcher())
    @After fun tearDown() = Dispatchers.resetMain()

    private fun ok(session: String, answer: String, products: List<Product> = emptyList()) =
        ApiResult.Success(ConversationResponse(session, answer, products))

    @Test fun loadsExistingSessionKeepingProducts() = runTest {
        val repo = FakeRepo().apply {
            history = ApiResult.Success(
                listOf(
                    MessageOut(1, "s1", "user", "hi", createdAt = "t"),
                    MessageOut(2, "s1", "assistant", "answer", products = listOf(product), createdAt = "t"),
                ),
            )
        }
        val vm = vm(repo, "s1")
        assertTrue(vm.state.value.loading)
        advanceUntilIdle()
        val s = vm.state.value
        assertFalse(s.loading)
        assertEquals(listOf("user", "assistant"), s.messages.map { it.role })
        assertEquals(listOf(product), s.messages[1].products)
        assertEquals("s1", s.sessionId)
    }

    @Test fun sendSuccessStoresSessionIdAndAppendsAssistant() = runTest {
        val repo = FakeRepo().apply { sendResults.add(ok("new-id", "Here you go", listOf(product))) }
        val vm = vm(repo, null)
        vm.send("  need 200 Nm  ")
        assertTrue(vm.state.value.sending)
        assertEquals("user", vm.state.value.messages.single().role) // optimistic bubble
        advanceUntilIdle()
        val s = vm.state.value
        assertFalse(s.sending)
        assertEquals("new-id", s.sessionId)
        assertEquals(listOf(null to "need 200 Nm"), repo.sent)
        assertEquals(listOf("user", "assistant"), s.messages.map { it.role })
        assertEquals(listOf(product), s.messages[1].products)
        assertEquals(s.messages.map { it.key }.toSet().size, s.messages.size)
    }

    @Test fun secondSendReusesSessionId() = runTest {
        val repo = FakeRepo().apply { sendResults.add(ok("a", "1")); sendResults.add(ok("a", "2")) }
        val vm = vm(repo, null)
        vm.send("one"); advanceUntilIdle()
        vm.send("two"); advanceUntilIdle()
        assertEquals("a", repo.sent[1].first)
    }

    @Test fun failureKeepsTextAndRetryDoesNotDuplicateBubble() = runTest {
        val repo = FakeRepo().apply {
            sendResults.add(ApiResult.Failure(FailureKind.Network, "Cannot reach the server"))
            sendResults.add(ok("n", "done"))
        }
        val vm = vm(repo, null)
        vm.send("hello"); advanceUntilIdle()
        var s = vm.state.value
        assertEquals("Cannot reach the server", s.error)
        assertEquals("hello", s.failedText)
        assertFalse(s.sending)
        assertEquals(1, s.messages.size)

        vm.retry(); advanceUntilIdle()
        s = vm.state.value
        assertNull(s.error)
        assertNull(s.failedText)
        assertEquals(listOf("user", "assistant"), s.messages.map { it.role })
        assertEquals(listOf<String?>("hello", "hello"), repo.sent.map { it.second })
    }

    @Test fun blankIgnored() = runTest {
        val repo = FakeRepo()
        val vm = vm(repo, null)
        vm.send("   "); vm.send("")
        advanceUntilIdle()
        assertTrue(vm.state.value.messages.isEmpty())
        assertTrue(repo.sent.isEmpty())
        assertFalse(vm.state.value.sending)
    }

    @Test fun loadFailureCanBeRetried() = runTest {
        val repo = FakeRepo().apply { history = ApiResult.Failure(FailureKind.Network, "down") }
        val vm = vm(repo, "s1")
        advanceUntilIdle()
        assertNotNull(vm.state.value.error)
        repo.history = ApiResult.Success(listOf(MessageOut(1, "s1", "user", "hi", createdAt = "t")))
        vm.retry(); advanceUntilIdle()
        assertNull(vm.state.value.error)
        assertEquals(1, vm.state.value.messages.size)
    }

    @Test fun draftClearedOnSend() = runTest {
        val repo = FakeRepo().apply { sendResults.add(ok("a", "x")) }
        val vm = vm(repo, null)
        vm.onDraftChange("typed")
        assertEquals("typed", vm.state.value.draft)
        vm.send("typed")
        assertEquals("", vm.state.value.draft)
        advanceUntilIdle()
    }

    private val serverDown = ApiResult.Failure(FailureKind.Server(503, "llm_unavailable"), "busy", sessionId = "sid-1")

    @Test fun failedSendInNewChatAdoptsSessionIdSoRetryReusesIt() = runTest {
        val repo = FakeRepo().apply { sendResults.add(serverDown); sendResults.add(ok("sid-1", "done")) }
        val handle = SavedStateHandle()
        val vm = vm(repo, null, handle)
        vm.send("hi"); advanceUntilIdle()
        assertEquals("sid-1", vm.state.value.sessionId)
        assertEquals("sid-1", handle["chat_session_id"])
        vm.retry(); advanceUntilIdle()
        assertEquals(listOf<String?>(null, "sid-1"), repo.sent.map { it.first })
        assertEquals(2, vm.state.value.messages.size)
    }

    @Test fun sendBlockedWhileHistoryLoadsAndLoadNeverOverwritesLocal() = runTest {
        val repo = FakeRepo().apply {
            history = ApiResult.Success(listOf(MessageOut(1, "s1", "user", "old", createdAt = "t")))
        }
        val vm = vm(repo, "s1")
        vm.send("too early")
        assertTrue(vm.state.value.messages.isEmpty())
        assertTrue(repo.sent.isEmpty())
        advanceUntilIdle()
        assertEquals(listOf("old"), vm.state.value.messages.map { it.text })
        repo.sendResults.add(ok("s1", "ok"))
        vm.send("now"); advanceUntilIdle()
        assertEquals(3, vm.state.value.messages.size)
    }

    @Test fun sessionIdPersistedInSavedStateAndRestored() = runTest {
        val repo = FakeRepo().apply { sendResults.add(ok("abc", "x")) }
        val handle = SavedStateHandle()
        val first = vm(repo, null, handle)
        first.send("q"); advanceUntilIdle()
        assertEquals("abc", handle["chat_session_id"])
        // "Process death": a new ViewModel gets the same handle and reloads that session.
        val restored = ChatViewModel(repo, handle)
        assertEquals("abc", restored.state.value.sessionId)
        assertTrue(restored.state.value.loading)
        advanceUntilIdle()
    }

    @Test fun retryableErrorsOfferRetryAndRestoreDraft() = runTest {
        for (f in listOf(
            ApiResult.Failure(FailureKind.Network, "n"),
            ApiResult.Failure(FailureKind.Timeout, "t"),
            ApiResult.Failure(FailureKind.Server(503, null), "s"),
        )) {
            val repo = FakeRepo().apply { sendResults.add(f) }
            val vm = vm(repo, null)
            vm.send("hello"); advanceUntilIdle()
            assertTrue(vm.state.value.canRetry)
            assertEquals("hello", vm.state.value.draft)
        }
    }

    @Test fun clientErrorsHaveNoRetryAndKeepTextForEditing() = runTest {
        for (code in listOf(404 to "session_not_found", 422 to "validation_error")) {
            val repo = FakeRepo().apply { sendResults.add(ApiResult.Failure(FailureKind.Server(code.first, code.second), "bad")) }
            val vm = vm(repo, null)
            vm.send("hello"); advanceUntilIdle()
            val s = vm.state.value
            assertEquals("bad", s.error)
            assertFalse(s.canRetry)
            assertNull(s.failedText)
            assertEquals("hello", s.draft)
            assertTrue(s.messages.isEmpty())
        }
    }

    @Test fun draftCappedAtBackendLimitAndLongSendRejected() = runTest {
        val repo = FakeRepo()
        val vm = vm(repo, null)
        vm.onDraftChange("x".repeat(MAX_QUERY_CHARS + 50))
        assertEquals(MAX_QUERY_CHARS, vm.state.value.draft.length)
        vm.send("y".repeat(MAX_QUERY_CHARS + 1))
        assertTrue(repo.sent.isEmpty())
    }

    @Test fun retryClearsRestoredDraftSoItIsNotSentTwice() = runTest {
        val repo = FakeRepo().apply {
            sendResults.add(ApiResult.Failure(FailureKind.Network, "n")); sendResults.add(ok("a", "ok"))
        }
        val vm = vm(repo, null)
        vm.send("hello"); advanceUntilIdle()
        assertEquals("hello", vm.state.value.draft)
        vm.retry(); advanceUntilIdle()
        assertEquals("", vm.state.value.draft)
    }

    @Test fun voiceFinalSendsSpokenAndSetsAutoSpeakKey() = runTest {
        val repo = FakeRepo().apply { sendResults.add(ok("s", "Answer")) }
        val vm = vm(repo, null)
        vm.onVoiceStart()
        assertTrue(vm.state.value.listening)
        vm.onVoicePartial("need 600")
        assertEquals("need 600", vm.state.value.draft)
        vm.onVoiceFinal("need 600 Nm")
        advanceUntilIdle()
        val s = vm.state.value
        assertFalse(s.listening)
        assertEquals(listOf(null to "need 600 Nm"), repo.sent)
        assertEquals(s.messages.last().key, s.autoSpeakKey)
        vm.onAutoSpoken()
        assertNull(vm.state.value.autoSpeakKey)
    }

    @Test fun typedSendNeverAutoSpeaks() = runTest {
        val repo = FakeRepo().apply { sendResults.add(ok("s", "Answer")) }
        val vm = vm(repo, null)
        vm.send("hello")
        advanceUntilIdle()
        assertNull(vm.state.value.autoSpeakKey)
    }

    @Test fun spokenFailureDoesNotSpeakAndRetryKeepsSpoken() = runTest {
        val repo = FakeRepo().apply {
            sendResults.add(ApiResult.Failure(FailureKind.Network, "offline"))
            sendResults.add(ok("s", "Answer"))
        }
        val vm = vm(repo, null)
        vm.onVoiceFinal("hi there")
        advanceUntilIdle()
        assertNull(vm.state.value.autoSpeakKey)
        vm.retry()
        advanceUntilIdle()
        assertNotNull(vm.state.value.autoSpeakKey)
    }

    @Test fun voiceErrorKeepsTypingUsable() = runTest {
        val repo = FakeRepo()
        val vm = vm(repo, null)
        vm.onDraftChange("partial")
        vm.onVoiceStart()
        vm.onVoiceError("Didn't catch that, try again")
        val s = vm.state.value
        assertFalse(s.listening)
        assertEquals("Didn't catch that, try again", s.error)
        assertFalse(s.canRetry)
        assertEquals("partial", s.draft)
        vm.onVoiceEnded()
        assertFalse(vm.state.value.listening)
    }
}

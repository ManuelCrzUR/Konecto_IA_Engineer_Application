package com.konecto.series76.debug

import com.konecto.series76.data.ApiResult
import com.konecto.series76.data.AssistantRepository
import com.konecto.series76.data.ConversationResponse
import com.konecto.series76.data.FailureKind
import com.konecto.series76.data.MessageOut
import com.konecto.series76.data.SessionOut
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.json.Json
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class DebugViewModelTest {
    private val json = Json { ignoreUnknownKeys = true }
    private val messages: List<MessageOut> = json.decodeFromString(
        ListSerializer(MessageOut.serializer()),
        javaClass.getResource("/contract/messages.json")!!.readText(),
    )

    private class FakeRepo(var next: ApiResult<List<MessageOut>>) : AssistantRepository {
        var calls = 0
        override suspend fun sendMessage(sessionId: String?, query: String): ApiResult<ConversationResponse> =
            error("unused")
        override suspend fun sessions(): ApiResult<List<SessionOut>> = error("unused")
        override suspend fun messages(sessionId: String): ApiResult<List<MessageOut>> {
            calls++
            return next
        }
    }

    @Before fun setUp() = Dispatchers.setMain(UnconfinedTestDispatcher())
    @After fun tearDown() = Dispatchers.resetMain()

    @Test fun nullSessionIsNoSessionAndNeverCallsRepo() = runTest {
        val repo = FakeRepo(ApiResult.Success(messages))
        val vm = DebugViewModel(repo, null)
        assertEquals(DebugUiState.NoSession, vm.state.value)
        vm.refresh()
        assertEquals(DebugUiState.NoSession, vm.state.value)
        assertEquals(0, repo.calls)
    }

    @Test fun successPairsQuestionsWithTraces() = runTest {
        val vm = DebugViewModel(FakeRepo(ApiResult.Success(messages)), "s1")
        val turns = (vm.state.value as DebugUiState.Success).turns
        assertEquals(2, turns.size)
        assertEquals(messages[0].content, turns[0].question)
        assertEquals(messages[1].trace, turns[0].traces)
        assertEquals(messages[2].content, turns[1].question)
        assertEquals(messages[3].trace, turns[1].traces)
        assertEquals("search_actuators", turns[0].traces[0].tool)
    }

    @Test fun errorThenRefreshSucceeds() = runTest {
        val repo = FakeRepo(ApiResult.Failure(FailureKind.Network, "Cannot reach the server"))
        val vm = DebugViewModel(repo, "s1")
        assertEquals(DebugUiState.Error("Cannot reach the server"), vm.state.value)
        repo.next = ApiResult.Success(messages)
        vm.refresh()
        assertTrue(vm.state.value is DebugUiState.Success)
        assertEquals(2, repo.calls)
    }

    @Test fun noAssistantTurnsIsEmptySuccess() = runTest {
        val vm = DebugViewModel(FakeRepo(ApiResult.Success(listOf(messages[0]))), "s1")
        assertEquals(DebugUiState.Success(emptyList()), vm.state.value)
    }

    @Test fun slowOlderResponseCannotOverwriteNewer() = runTest {
        val slow = CompletableDeferred<ApiResult<List<MessageOut>>>()
        val fast = CompletableDeferred<ApiResult<List<MessageOut>>>()
        val queue = ArrayDeque(listOf(slow, fast))
        val repo = object : AssistantRepository {
            override suspend fun sendMessage(sessionId: String?, query: String): ApiResult<ConversationResponse> = error("unused")
            override suspend fun sessions(): ApiResult<List<SessionOut>> = error("unused")
            override suspend fun messages(sessionId: String) = queue.removeFirst().await()
        }
        val vm = DebugViewModel(repo, "s1") // call 1 pending (slow)
        vm.refresh()                         // call 2 pending (fast); call 1 cancelled
        fast.complete(ApiResult.Success(messages))
        slow.complete(ApiResult.Failure(FailureKind.Network, "old"))
        assertTrue(vm.state.value is DebugUiState.Success)
    }
}

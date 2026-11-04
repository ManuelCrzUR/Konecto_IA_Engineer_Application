package com.konecto.series76.conversations

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
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test

private class FakeRepo(var next: suspend () -> ApiResult<List<SessionOut>>) : AssistantRepository {
    var calls = 0
    override suspend fun sessions(): ApiResult<List<SessionOut>> { calls++; return next() }
    override suspend fun sendMessage(sessionId: String?, query: String): ApiResult<ConversationResponse> = error("unused")
    override suspend fun messages(sessionId: String): ApiResult<List<MessageOut>> = error("unused")
}

@OptIn(ExperimentalCoroutinesApi::class)
class ConversationsViewModelTest {
    private val s = SessionOut("a", null, "Title A", "2026-11-04T10:00:00Z", "2026-11-04T10:00:00Z")

    @Before fun setUp() = Dispatchers.setMain(UnconfinedTestDispatcher())
    @After fun tearDown() = Dispatchers.resetMain()

    @Test fun loadingThenSuccess() {
        val gate = CompletableDeferred<ApiResult<List<SessionOut>>>()
        val vm = ConversationsViewModel(FakeRepo { gate.await() })
        assertEquals(ConversationsUiState.Loading, vm.state.value)
        gate.complete(ApiResult.Success(listOf(s)))
        assertEquals(ConversationsUiState.Success(listOf(s)), vm.state.value)
    }

    @Test fun emptyList() {
        val vm = ConversationsViewModel(FakeRepo { ApiResult.Success(emptyList<SessionOut>()) })
        assertEquals(ConversationsUiState.Empty, vm.state.value)
    }

    @Test fun errorThenRefreshSuccess() {
        val repo = FakeRepo { ApiResult.Failure(FailureKind.Network, "No connection") }
        val vm = ConversationsViewModel(repo)
        assertEquals(ConversationsUiState.Error("No connection"), vm.state.value)
        repo.next = { ApiResult.Success(listOf(s)) }
        vm.refresh()
        assertEquals(ConversationsUiState.Success(listOf(s)), vm.state.value)
        assertEquals(2, repo.calls)
    }

    @Test fun resumeReloadsAndPicksUpNewSession() {
        val newer = SessionOut("b", null, "New chat", "2026-11-04T11:00:00Z", "2026-11-04T11:00:00Z")
        val repo = FakeRepo { ApiResult.Success(listOf(s)) }
        val vm = ConversationsViewModel(repo)
        vm.onResume() // first resume: initial load already finished, harmless reload
        repo.next = { ApiResult.Success(listOf(newer, s)) }
        vm.onResume()
        assertEquals(ConversationsUiState.Success(listOf(newer, s)), vm.state.value)
    }

    @Test fun resumeWhileLoadInFlightDoesNotDuplicate() {
        val gate = CompletableDeferred<ApiResult<List<SessionOut>>>()
        val repo = FakeRepo { gate.await() }
        val vm = ConversationsViewModel(repo)
        vm.onResume()
        vm.onResume()
        assertEquals(1, repo.calls)
        gate.complete(ApiResult.Success(listOf(s)))
        vm.onResume()
        assertEquals(2, repo.calls)
    }

    @Test fun isRefreshingResetsAfterFailureAndSuccess() {
        val gate = CompletableDeferred<ApiResult<List<SessionOut>>>()
        val repo = FakeRepo { ApiResult.Failure(FailureKind.Network, "No connection") }
        val vm = ConversationsViewModel(repo)
        repo.next = { gate.await() }
        vm.refresh()
        assertEquals(true, vm.isRefreshing.value)
        gate.complete(ApiResult.Failure(FailureKind.Network, "No connection"))
        assertEquals(ConversationsUiState.Error("No connection"), vm.state.value)
        assertEquals(false, vm.isRefreshing.value)
        val gate2 = CompletableDeferred<ApiResult<List<SessionOut>>>()
        repo.next = { gate2.await() }
        vm.refresh()
        assertEquals(true, vm.isRefreshing.value)
        gate2.complete(ApiResult.Success(listOf(s)))
        assertEquals(false, vm.isRefreshing.value)
    }

    @Test fun refreshKeepsListAndFlagsRefreshing() {
        val repo = FakeRepo { ApiResult.Success(listOf(s)) }
        val vm = ConversationsViewModel(repo)
        val gate = CompletableDeferred<ApiResult<List<SessionOut>>>()
        repo.next = { gate.await() }
        vm.refresh()
        assertEquals(ConversationsUiState.Success(listOf(s)), vm.state.value)
        assertEquals(true, vm.isRefreshing.value)
        gate.complete(ApiResult.Success(emptyList<SessionOut>()))
        assertEquals(ConversationsUiState.Empty, vm.state.value)
        assertEquals(false, vm.isRefreshing.value)
    }
}

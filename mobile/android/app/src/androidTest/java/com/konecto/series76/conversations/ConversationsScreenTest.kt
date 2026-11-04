package com.konecto.series76.conversations

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import com.konecto.series76.data.ApiResult
import com.konecto.series76.data.AssistantRepository
import com.konecto.series76.data.ConversationResponse
import com.konecto.series76.data.FailureKind
import com.konecto.series76.data.MessageOut
import com.konecto.series76.data.SessionOut
import com.konecto.series76.ui.theme.Series76Theme
import androidx.compose.runtime.CompositionLocalProvider
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.LifecycleRegistry
import androidx.lifecycle.compose.LocalLifecycleOwner
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test

private class FakeRepo(var next: ApiResult<List<SessionOut>>) : AssistantRepository {
    override suspend fun sessions() = next
    override suspend fun sendMessage(sessionId: String?, query: String): ApiResult<ConversationResponse> = error("unused")
    override suspend fun messages(sessionId: String): ApiResult<List<MessageOut>> = error("unused")
}

class ConversationsScreenTest {
    @get:Rule val rule = createComposeRule()

    // Titles from mobile/contract/sessions.json
    private val sessions = listOf(
        SessionOut("dcae9457", null, "Specs of the 999Z please", "2026-11-04T14:55:50Z", "2026-11-04T14:55:57Z"),
        SessionOut("e07d8f55", null, "What is the torque of the 761A00-11330C00/A?", "2026-11-04T14:55:41Z", "2026-11-04T14:55:50Z"),
    )

    private fun show(repo: FakeRepo, onOpen: (String?) -> Unit = {}) {
        val vm = ConversationsViewModel(repo)
        rule.setContent { Series76Theme { ConversationsScreen(onOpenChat = onOpen, viewModel = vm) } }
    }

    @Test fun rendersTitlesAndOpensSession() {
        var opened: String? = "unset"
        show(FakeRepo(ApiResult.Success(sessions))) { opened = it }
        rule.onNodeWithTag("conversations_list").assertIsDisplayed()
        rule.onNodeWithText("Specs of the 999Z please").assertIsDisplayed()
        rule.onNodeWithText("What is the torque of the 761A00-11330C00/A?").assertIsDisplayed()
        rule.onNodeWithTag("session_e07d8f55").performClick()
        assertEquals("e07d8f55", opened)
    }

    @Test fun fabOpensNewConversation() {
        var opened: String? = "unset"
        show(FakeRepo(ApiResult.Success(sessions))) { opened = it }
        rule.onNodeWithTag("new_conversation").performClick()
        assertEquals(null, opened)
    }

    @Test fun emptyState() {
        show(FakeRepo(ApiResult.Success(emptyList())))
        rule.onNodeWithTag("empty_state").assertIsDisplayed()
        rule.onNodeWithText("No conversations yet. Start one!").assertIsDisplayed()
    }

    @Test fun errorShowsRetryAndRecovers() {
        val repo = FakeRepo(ApiResult.Failure(FailureKind.Network, "No connection"))
        show(repo)
        rule.onNodeWithText("No connection").assertIsDisplayed()
        rule.onNodeWithTag("error_retry").assertIsDisplayed()
        repo.next = ApiResult.Success(sessions)
        rule.onNodeWithTag("error_retry").performClick()
        rule.waitUntil(5_000) {
            rule.onAllNodesWithTagCount("conversations_list") > 0
        }
    }

    /** Returning from a chat = lifecycle goes ON_PAUSE/ON_STOP then back to RESUMED; the list must reload. */
    @Test fun returningToScreenReloadsList() {
        val repo = FakeRepo(ApiResult.Success(sessions.drop(1)))
        val vm = ConversationsViewModel(repo)
        val owner = object : LifecycleOwner {
            val registry = LifecycleRegistry.createUnsafe(this)
            override val lifecycle: Lifecycle get() = registry
        }
        rule.runOnUiThread { owner.registry.currentState = Lifecycle.State.RESUMED }
        rule.setContent {
            Series76Theme {
                CompositionLocalProvider(LocalLifecycleOwner provides owner) {
                    ConversationsScreen(onOpenChat = {}, viewModel = vm)
                }
            }
        }
        rule.onNodeWithTag("session_e07d8f55").assertIsDisplayed()
        repo.next = ApiResult.Success(sessions)
        rule.runOnUiThread { owner.registry.currentState = Lifecycle.State.CREATED }
        rule.runOnUiThread { owner.registry.currentState = Lifecycle.State.RESUMED }
        rule.waitUntil(5_000) { rule.onAllNodesWithTagCount("session_dcae9457") > 0 }
    }

    private fun androidx.compose.ui.test.junit4.ComposeContentTestRule.onAllNodesWithTagCount(tag: String) =
        onAllNodes(androidx.compose.ui.test.hasTestTag(tag)).fetchSemanticsNodes().size
}

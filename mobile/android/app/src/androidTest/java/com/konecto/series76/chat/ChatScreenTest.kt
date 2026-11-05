package com.konecto.series76.chat

import androidx.compose.ui.test.assertTextEquals
import androidx.compose.ui.test.hasAnyAncestor
import androidx.compose.ui.test.hasTestTag
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.assertCountEquals
import androidx.compose.ui.test.assertIsEnabled
import androidx.compose.ui.test.assertIsNotEnabled
import androidx.compose.ui.test.assertTextContains
import androidx.compose.ui.test.onAllNodesWithTag
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performTextInput
import androidx.test.platform.app.InstrumentationRegistry
import com.konecto.series76.data.ApiResult
import com.konecto.series76.data.StubRepository
import com.konecto.series76.data.ConversationResponse
import com.konecto.series76.data.MessageOut
import com.konecto.series76.data.SessionOut
import com.konecto.series76.data.ApiJson
import androidx.compose.ui.test.assertIsDisplayed
import com.konecto.series76.ui.theme.Series76Theme
import kotlinx.coroutines.CompletableDeferred
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test

class ChatScreenTest {
    @get:Rule val rule = createComposeRule()

    private val response: ConversationResponse = InstrumentationRegistry.getInstrumentation().context.assets
        .open("chat/conversation_recommend.json").bufferedReader().readText()
        .let { ApiJson.decodeFromString(ConversationResponse.serializer(), it) }

    private val sent = mutableListOf<String>()
    private var gate: CompletableDeferred<Unit>? = null

    private val fake = object : StubRepository() {
        override suspend fun sendMessage(sessionId: String?, query: String): ApiResult<ConversationResponse> {
            sent += query
            gate?.await()
            return ApiResult.Success(response)
        }
        override suspend fun sessions() = ApiResult.Success(emptyList<SessionOut>())
        override suspend fun messages(sessionId: String) = ApiResult.Success(emptyList<MessageOut>())
    }

    private fun sendOne(onDebug: (String?) -> Unit = {}) {
        val vm = ChatViewModel(fake, androidx.lifecycle.SavedStateHandle())
        rule.setContent { Series76Theme { ChatRoute(vm, onBack = {}, onOpenDebug = onDebug) } }
        rule.onNodeWithTag("chat_send").assertIsNotEnabled()
        rule.onNodeWithTag("chat_input").performTextInput("at least 600 Nm modulating")
        rule.onNodeWithTag("chat_send").assertIsEnabled().performClick()
        rule.waitUntil(5_000) { vm.state.value.messages.size == 2 }
        // The reply is composed in the lazy list after the state update (and scrolled into view).
        rule.waitUntil(5_000) { rule.onAllNodesWithTag("comparison_table").fetchSemanticsNodes().isNotEmpty() }
        rule.waitForIdle()
    }

    @Test fun cardsShowExactJsonNumbersAndComparisonAppears() {
        sendOne()
        assertEquals(4, response.products.size)
        rule.onNodeWithTag("comparison_table").assertExists()
        response.products.forEach { p ->
            rule.onNodeWithTag("product_card_${p.partNumber}").assertExists()
            p.fields.forEach { (k, v) ->
                rule.onNode(
                    hasTestTag("field_${k}_value") and hasAnyAncestor(hasTestTag("product_card_${p.partNumber}")),
                ).assertTextEquals(v?.content ?: "—")
            }
        }
    }

    @Test fun toolNamesTraceAndDebugNeverShown() {
        sendOne()
        response.debug.forEach { t ->
            rule.onAllNodesWithText(t.tool, substring = true, ignoreCase = true).assertCountEquals(0)
        }
        rule.onAllNodesWithText("trace", substring = true, ignoreCase = true).assertCountEquals(0)
        rule.onAllNodesWithText("debug", substring = true, ignoreCase = true).assertCountEquals(0)
    }

    @Test fun fiveTapsOnTitleOpenDebugWithSessionId() {
        var opened: String? = "unset"
        var calls = 0
        sendOne { opened = it; calls++ }
        repeat(5) { rule.onNodeWithTag("chat_title").performClick() }
        rule.waitForIdle()
        assertEquals(response.sessionId, opened)
        assertEquals(1, calls)
    }

    @Test fun emptyStateShowsSuggestionsAndTapSendsVerbatim() {
        val vm = ChatViewModel(fake, androidx.lifecycle.SavedStateHandle())
        rule.setContent { Series76Theme { ChatRoute(vm, onBack = {}, onOpenDebug = {}) } }
        SUGGESTIONS.forEachIndexed { i, text ->
            rule.onNodeWithTag("suggestion_$i").assertIsDisplayed()
            rule.onNodeWithTag("suggestion_$i").assertTextContains(text)
        }
        rule.onNodeWithTag("suggestion_1").performClick()
        rule.waitUntil(5_000) { vm.state.value.messages.size == 2 }
        assertEquals(listOf(SUGGESTIONS[1]), sent)
        rule.onAllNodesWithTag("suggestion_0").assertCountEquals(0)
    }

    @Test fun typingIndicatorVisibleWhileRequestIsPending() {
        gate = CompletableDeferred()
        val vm = ChatViewModel(fake, androidx.lifecycle.SavedStateHandle())
        rule.setContent { Series76Theme { ChatRoute(vm, onBack = {}, onOpenDebug = {}) } }
        rule.onNodeWithTag("chat_input").performTextInput("hello")
        rule.onNodeWithTag("chat_send").performClick()
        rule.waitUntil(5_000) { rule.onAllNodesWithTag("typing_indicator").fetchSemanticsNodes().isNotEmpty() }
        rule.onNodeWithTag("typing_indicator").assertIsDisplayed()
        rule.onNodeWithTag("chat_send").assertIsNotEnabled()
        gate!!.complete(Unit)
        rule.waitUntil(5_000) { rule.onAllNodesWithTag("typing_indicator").fetchSemanticsNodes().isEmpty() }
    }
}

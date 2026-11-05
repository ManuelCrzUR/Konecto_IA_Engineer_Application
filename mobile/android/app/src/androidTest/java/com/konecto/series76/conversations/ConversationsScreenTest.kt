package com.konecto.series76.conversations

import androidx.compose.ui.test.assertIsDisplayed
import androidx.activity.ComponentActivity
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import com.konecto.series76.data.ApiResult
import com.konecto.series76.data.StubRepository
import com.konecto.series76.data.ConversationResponse
import com.konecto.series76.data.FailureKind
import com.konecto.series76.data.MessageOut
import com.konecto.series76.data.SessionOut
import com.konecto.series76.data.ThemePreferences
import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import java.io.File
import com.konecto.series76.ui.theme.Series76Theme
import androidx.compose.runtime.CompositionLocalProvider
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.LifecycleRegistry
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.test.assertCountEquals
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.SemanticsMatcher
import androidx.compose.ui.test.assert
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.test.assertTextEquals
import androidx.compose.ui.test.onAllNodesWithTag
import androidx.compose.ui.test.performTextInput
import androidx.test.platform.app.InstrumentationRegistry
import com.konecto.series76.data.ApiJson
import com.konecto.series76.ui.theme.ThemeMode
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.builtins.ListSerializer
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test

private class FakeRepo(
    var next: ApiResult<List<SessionOut>>,
    var searchResult: ApiResult<List<SessionOut>> = ApiResult.Success(emptyList()),
) : StubRepository() {
    val searches = mutableListOf<String>()
    override suspend fun sessions() = next
    override suspend fun searchSessions(q: String): ApiResult<List<SessionOut>> { searches += q; return searchResult }
}

class ConversationsScreenTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()

    // Titles from mobile/contract/sessions.json
    private val sessions = listOf(
        SessionOut("dcae9457", null, "Specs of the 999Z please", "2026-11-04T14:55:50Z", "2026-11-04T14:55:57Z"),
        SessionOut("e07d8f55", null, "What is the torque of the 761A00-11330C00/A?", "2026-11-04T14:55:41Z", "2026-11-04T14:55:50Z"),
    )

    private fun tempPrefs() =
        ThemePreferences(PreferenceDataStoreFactory.create { File.createTempFile("theme", ".preferences_pb").also { it.delete() } })

    private fun show(repo: FakeRepo, prefs: ThemePreferences = tempPrefs(), onOpen: (String?) -> Unit = {}) {
        val vm = ConversationsViewModel(repo, prefs)
        rule.setContent {
            // Mirrors MainActivity: the persisted mode drives the theme.
            val mode by prefs.themeMode.collectAsState(ThemeMode.DARK)
            Series76Theme(mode) { ConversationsScreen(onOpenChat = onOpen, viewModel = vm) }
        }
    }

    private val searchFixture: List<SessionOut> = ApiJson.decodeFromString(
        ListSerializer(SessionOut.serializer()),
        InstrumentationRegistry.getInstrumentation().context.assets
            .open("contract/sessions_search.json").bufferedReader().readText(),
    )

    @Test fun themeMenuListsOptionsAndPersistsLight() {
        val prefs = tempPrefs()
        show(FakeRepo(ApiResult.Success(sessions)), prefs)
        rule.onNodeWithTag("theme_button").performClick()
        listOf("DARK", "LIGHT", "SYSTEM").forEach { rule.onNodeWithTag("theme_option_$it").assertIsDisplayed() }
        rule.onNodeWithTag("theme_option_LIGHT").performClick()
        rule.waitUntil(5_000) { runBlocking { prefs.themeMode.first() } == ThemeMode.LIGHT }
        rule.onAllNodesWithTag("theme_option_LIGHT").assertCountEquals(0) // menu closed
        // Reopen: the selected option now carries the check mark.
        rule.onNodeWithTag("theme_button").performClick()
        rule.onNodeWithTag("theme_option_LIGHT").assertIsDisplayed()
    }

    @Test fun searchShowsSectionsAndVerbatimSnippet() {
        val repo = FakeRepo(ApiResult.Success(sessions), ApiResult.Success(searchFixture))
        show(repo)
        rule.onNodeWithTag("search_field").performTextInput("764A00")
        rule.waitUntil(5_000) { rule.onAllNodesWithTag("search_results").fetchSemanticsNodes().isNotEmpty() }
        assertEquals(listOf("764A00"), repo.searches)
        rule.onNodeWithTag("search_count").assertTextEquals("2 results")
        rule.onNodeWithTag("search_section_title").assertIsDisplayed()
        rule.onNodeWithTag("search_section_message").assertIsDisplayed()
        val snippet = searchFixture.single { it.match?.where == "message" }.match!!.snippet
        // Highlighting only styles spans; the text itself must equal the backend snippet.
        rule.onNodeWithText(snippet).assertIsDisplayed()
        rule.onNodeWithTag("search_clear").performClick()
        rule.waitUntil(5_000) { rule.onAllNodesWithTag("conversations_list").fetchSemanticsNodes().isNotEmpty() }
    }

    @Test fun searchWithoutMatchesShowsEmptyMessage() {
        show(FakeRepo(ApiResult.Success(sessions)))
        rule.onNodeWithTag("search_field").performTextInput("zzz")
        rule.waitUntil(5_000) { rule.onAllNodesWithTag("search_empty").fetchSemanticsNodes().isNotEmpty() }
        rule.onNodeWithTag("search_empty").assertTextEquals("No conversations match \"zzz\"")
    }

    @Test fun backInSearchClearsQueryAndShowsList() {
        show(FakeRepo(ApiResult.Success(sessions)))
        rule.onNodeWithTag("search_field").performTextInput("zzz")
        rule.waitUntil(5_000) { rule.onAllNodesWithTag("search_empty").fetchSemanticsNodes().isNotEmpty() }
        rule.runOnUiThread { rule.activity.onBackPressedDispatcher.onBackPressed() }
        rule.waitUntil(5_000) { rule.onAllNodesWithTag("conversations_list").fetchSemanticsNodes().isNotEmpty() }
        rule.onNodeWithTag("search_field").assert(SemanticsMatcher.expectValue(SemanticsProperties.EditableText, AnnotatedString("")))
    }

    @Test fun searchErrorRetryRequeries() {
        val repo = FakeRepo(ApiResult.Success(sessions), ApiResult.Failure(FailureKind.Network, "No connection"))
        show(repo)
        rule.onNodeWithTag("search_field").performTextInput("zzz")
        rule.waitUntil(5_000) { rule.onAllNodesWithTag("search_retry").fetchSemanticsNodes().isNotEmpty() }
        repo.searchResult = ApiResult.Success(emptyList())
        rule.onNodeWithTag("search_retry").performClick()
        rule.waitUntil(5_000) { rule.onAllNodesWithTag("search_empty").fetchSemanticsNodes().isNotEmpty() }
        assertEquals(listOf("zzz", "zzz"), repo.searches)
    }

    @Test fun rendersTitlesAndOpensSession() {
        var opened: String? = "unset"
        show(FakeRepo(ApiResult.Success(sessions)), onOpen = { opened = it })
        rule.onNodeWithTag("conversations_list").assertIsDisplayed()
        rule.onNodeWithText("Specs of the 999Z please").assertIsDisplayed()
        rule.onNodeWithText("What is the torque of the 761A00-11330C00/A?").assertIsDisplayed()
        rule.onNodeWithTag("session_e07d8f55").performClick()
        assertEquals("e07d8f55", opened)
    }

    @Test fun fabOpensNewConversation() {
        var opened: String? = "unset"
        show(FakeRepo(ApiResult.Success(sessions)), onOpen = { opened = it })
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
        val vm = ConversationsViewModel(repo, tempPrefs())
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

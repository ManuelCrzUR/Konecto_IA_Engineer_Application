package com.konecto.series76.conversations

import androidx.compose.ui.text.SpanStyle
import com.konecto.series76.data.ApiResult
import com.konecto.series76.data.StubRepository
import com.konecto.series76.data.ApiJson
import com.konecto.series76.data.ConversationResponse
import com.konecto.series76.data.FailureKind
import com.konecto.series76.data.MessageOut
import com.konecto.series76.data.SessionOut
import com.konecto.series76.ui.theme.ThemeMode
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.launchIn
import kotlinx.coroutines.flow.onEach
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.setMain
import kotlinx.serialization.builtins.ListSerializer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

private class SearchRepo(var result: ApiResult<List<SessionOut>>) : StubRepository() {
    val queries = mutableListOf<String>()
    override suspend fun sessions(): ApiResult<List<SessionOut>> = ApiResult.Success(emptyList())
    override suspend fun searchSessions(q: String): ApiResult<List<SessionOut>> { queries += q; return result }
}

@OptIn(ExperimentalCoroutinesApi::class)
class ConversationsSearchTest {
    private val fixture: List<SessionOut> = ApiJson.decodeFromString(
        ListSerializer(SessionOut.serializer()),
        javaClass.getResource("/contract/sessions_search.json")!!.readText(),
    )

    @Before fun setUp() = Dispatchers.setMain(StandardTestDispatcher())
    @After fun tearDown() = Dispatchers.resetMain()

    private fun TestScope.vm(repo: SearchRepo): ConversationsViewModel {
        val vm = ConversationsViewModel(repo, testThemePreferences())
        vm.search.onEach { }.launchIn(backgroundScope) // keep the WhileSubscribed upstream alive
        runCurrent()
        return vm
    }

    @Test fun onlyLastQueryWithinDebounceHitsRepository() = runTest(StandardTestDispatcher()) {
        val repo = SearchRepo(ApiResult.Success(fixture))
        val vm = vm(repo)
        listOf("7", "76", "764", "764A").forEach { vm.onQueryChange(it); advanceTimeBy(100) }
        assertTrue(repo.queries.isEmpty())
        advanceTimeBy(SEARCH_DEBOUNCE_MS + 1)
        assertEquals(listOf("764A"), repo.queries)
    }

    @Test fun blankQueryReturnsToList() = runTest(StandardTestDispatcher()) {
        val repo = SearchRepo(ApiResult.Success(fixture))
        val vm = vm(repo)
        vm.onQueryChange("764A"); advanceTimeBy(SEARCH_DEBOUNCE_MS + 1); runCurrent()
        assertTrue(vm.search.value is SearchUiState.Results)
        vm.onQueryChange("  "); runCurrent()
        assertEquals(SearchUiState.Inactive, vm.search.value)
        assertEquals(1, repo.queries.size)
    }

    @Test fun resultsSplitIntoTitlesAndMessages() = runTest(StandardTestDispatcher()) {
        val vm = vm(SearchRepo(ApiResult.Success(fixture)))
        vm.onQueryChange("764A"); advanceTimeBy(SEARCH_DEBOUNCE_MS + 1); runCurrent()
        val r = vm.search.value as SearchUiState.Results
        assertEquals(listOf("e37cafb7-4c35-4335-bc04-3ca8c84d8546"), r.titles.map { it.id })
        assertEquals(listOf("f2aaeced-6c13-49e2-9975-7e3e70e1d497"), r.messages.map { it.id })
        assertEquals(2, r.count)
    }

    @Test fun emptyResultsAndError() = runTest(StandardTestDispatcher()) {
        val repo = SearchRepo(ApiResult.Success(emptyList()))
        val vm = vm(repo)
        vm.onQueryChange("zzz"); advanceTimeBy(SEARCH_DEBOUNCE_MS + 1); runCurrent()
        assertEquals(SearchUiState.NoResults("zzz"), vm.search.value)
        repo.result = ApiResult.Failure(FailureKind.Network, "No connection")
        vm.onQueryChange("yyy"); advanceTimeBy(SEARCH_DEBOUNCE_MS + 1); runCurrent()
        assertEquals(SearchUiState.Error("No connection"), vm.search.value)
    }

    @Test fun retryAfterErrorRequeriesSameQuery() = runTest(StandardTestDispatcher()) {
        val repo = SearchRepo(ApiResult.Failure(FailureKind.Network, "No connection"))
        val vm = vm(repo)
        vm.onQueryChange("764A"); advanceTimeBy(SEARCH_DEBOUNCE_MS + 1); runCurrent()
        assertEquals(SearchUiState.Error("No connection"), vm.search.value)
        repo.result = ApiResult.Success(fixture)
        vm.retrySearch(); runCurrent()
        assertEquals(listOf("764A", "764A"), repo.queries)
        assertEquals("764A", (vm.search.value as SearchUiState.Results).query)
    }

    @Test fun refreshWhileSearchingRequeries() = runTest(StandardTestDispatcher()) {
        val repo = SearchRepo(ApiResult.Success(fixture))
        val vm = vm(repo)
        vm.onQueryChange(" 764A "); advanceTimeBy(SEARCH_DEBOUNCE_MS + 1); runCurrent()
        vm.refresh(); runCurrent()
        assertEquals(listOf("764A", "764A"), repo.queries)
    }

    @Test fun refreshWithoutQueryDoesNotSearch() = runTest(StandardTestDispatcher()) {
        val repo = SearchRepo(ApiResult.Success(fixture))
        val vm = vm(repo)
        vm.refresh(); runCurrent()
        assertTrue(repo.queries.isEmpty())
        assertEquals(SearchUiState.Inactive, vm.search.value)
    }

    @Test fun setThemeModePersists() = runTest(StandardTestDispatcher()) {
        val prefs = testThemePreferences()
        val vm = ConversationsViewModel(SearchRepo(ApiResult.Success(emptyList())), prefs)
        vm.themeMode.onEach { }.launchIn(backgroundScope)
        runCurrent()
        assertEquals(ThemeMode.DARK, vm.themeMode.value)
        vm.setThemeMode(ThemeMode.LIGHT); runCurrent()
        assertEquals(ThemeMode.DARK, vm.themeMode.value) // delayed until the menu has closed
        advanceTimeBy(MENU_CLOSE_MS + 1); runCurrent()
        assertEquals(ThemeMode.LIGHT, vm.themeMode.value)
        assertEquals(ThemeMode.LIGHT, prefs.themeMode.first())
    }

    @Test fun highlightKeepsTextAndMatchesCaseInsensitively() {
        val out = highlight("…torque of 764a00 and 764A00…", "764A", SpanStyle())
        assertEquals("…torque of 764a00 and 764A00…", out.text)
        assertEquals(2, out.spanStyles.size)
        assertEquals("764a", out.text.substring(out.spanStyles[0].start, out.spanStyles[0].end))
    }

    @Test fun highlightEdgeCases() {
        val style = SpanStyle()
        assertEquals(0, highlight("abc", "", style).spanStyles.size)
        assertEquals(0, highlight("abc", "   ", style).spanStyles.size)
        assertEquals(0, highlight("abc", "zzz", style).spanStyles.size)
        assertEquals("abc", highlight("abc", "zzz", style).text)
        val trimmed = highlight("xx ab yy", "  ab ", style)
        assertEquals("xx ab yy", trimmed.text)
        assertEquals("ab", trimmed.text.substring(trimmed.spanStyles[0].start, trimmed.spanStyles[0].end))
        val adjacent = highlight("aaaa", "aa", style)
        assertEquals(2, adjacent.spanStyles.size) // non-overlapping
        assertEquals(0, highlight("", "a", style).spanStyles.size)
    }
}

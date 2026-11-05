package com.konecto.series76.conversations

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.konecto.series76.data.ApiResult
import com.konecto.series76.data.AssistantRepository
import com.konecto.series76.data.SessionOut
import com.konecto.series76.data.ThemePreferences
import com.konecto.series76.ui.theme.ThemeMode
import kotlinx.coroutines.FlowPreview
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.debounce
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

const val SEARCH_DEBOUNCE_MS = 300L

sealed interface ConversationsUiState {
    data object Loading : ConversationsUiState
    data object Empty : ConversationsUiState
    data class Success(val sessions: List<SessionOut>) : ConversationsUiState
    data class Error(val message: String) : ConversationsUiState
}

/** Search mode, independent of the list state. [Inactive] means the normal list is shown. */
sealed interface SearchUiState {
    data object Inactive : SearchUiState
    data object Searching : SearchUiState
    /** Backend order is kept inside each group. */
    data class Results(val query: String, val titles: List<SessionOut>, val messages: List<SessionOut>) : SearchUiState {
        val count: Int get() = titles.size + messages.size
    }
    data class NoResults(val query: String) : SearchUiState
    data class Error(val message: String) : SearchUiState
}

internal const val MENU_CLOSE_MS = 120L

@OptIn(FlowPreview::class, kotlinx.coroutines.ExperimentalCoroutinesApi::class)
class ConversationsViewModel(
    private val repo: AssistantRepository,
    private val themePreferences: ThemePreferences,
) : ViewModel() {
    private val _state = MutableStateFlow<ConversationsUiState>(ConversationsUiState.Loading)
    val state: StateFlow<ConversationsUiState> = _state.asStateFlow()

    private val _isRefreshing = MutableStateFlow(false)
    val isRefreshing: StateFlow<Boolean> = _isRefreshing.asStateFlow()

    private val _query = MutableStateFlow("")
    val query: StateFlow<String> = _query.asStateFlow()

    /** Bumped to re-run the current search (Retry, pull-to-refresh, resume) despite distinctUntilChanged. */
    private val refreshTick = MutableStateFlow(0)

    val search: StateFlow<SearchUiState> = _query
        .debounce { if (it.isBlank()) 0L else SEARCH_DEBOUNCE_MS } // clearing the field is instant
        .map { it.trim() }
        .distinctUntilChanged()
        .combine(refreshTick) { q, _ -> q }
        .flatMapLatest { q ->
            if (q.isEmpty()) flowOf<SearchUiState>(SearchUiState.Inactive) else flow<SearchUiState> {
                emit(SearchUiState.Searching)
                emit(searchState(q))
            }
        }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), SearchUiState.Inactive)

    val themeMode: StateFlow<ThemeMode> = themePreferences.themeMode
        .stateIn(viewModelScope, SharingStarted.Eagerly, ThemeMode.DARK)

    private var job: Job? = null

    init {
        load(flagRefreshing = false)
    }

    fun onQueryChange(q: String) { _query.value = q }

    /** Applied after [MENU_CLOSE_MS] so the menu closes first; lives in viewModelScope so leaving the screen can't drop it. */
    fun setThemeMode(mode: ThemeMode) {
        viewModelScope.launch { delay(MENU_CLOSE_MS); themePreferences.setThemeMode(mode) }
    }

    private suspend fun searchState(q: String): SearchUiState = when (val r = repo.searchSessions(q)) {
        is ApiResult.Success -> {
            val (titles, messages) = r.value.partition { it.match?.where == "title" }
            if (r.value.isEmpty()) SearchUiState.NoResults(q) else SearchUiState.Results(q, titles, messages)
        }
        is ApiResult.Failure -> SearchUiState.Error(r.message)
    }

    /**
     * User-driven reload (pull-to-refresh, Retry). Always flips isRefreshing true -> false so the
     * pull indicator is released even when the screen is in Error/Empty state (Material3 keeps the
     * indicator at its threshold if onRefresh never makes isRefreshing true).
     */
    fun refresh() {
        rerunSearch()
        load(flagRefreshing = true)
    }

    /** Re-runs the active search (no-op when the query is blank). Used by Retry, refresh and resume. */
    fun retrySearch() = rerunSearch()

    private fun rerunSearch() {
        if (_query.value.isNotBlank()) refreshTick.value++
    }

    /**
     * Call on every ON_RESUME (returning from a chat). Reloads silently unless a load is already in
     * flight, which also covers the first resume that coincides with the initial load.
     */
    fun onResume() {
        rerunSearch()
        if (job?.isActive != true) load(flagRefreshing = false)
    }

    private fun load(flagRefreshing: Boolean) {
        job?.cancel()
        if (flagRefreshing) _isRefreshing.value = true
        if (_state.value !is ConversationsUiState.Success) _state.value = ConversationsUiState.Loading
        job = viewModelScope.launch {
            _state.value = when (val r = repo.sessions()) {
                is ApiResult.Success ->
                    if (r.value.isEmpty()) ConversationsUiState.Empty else ConversationsUiState.Success(r.value)
                is ApiResult.Failure -> ConversationsUiState.Error(r.message)
            }
            _isRefreshing.value = false
        }
    }

    companion object {
        fun factory(repo: AssistantRepository, themePreferences: ThemePreferences): ViewModelProvider.Factory =
            viewModelFactory { initializer { ConversationsViewModel(repo, themePreferences) } }
    }
}

package com.konecto.series76.conversations

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.konecto.series76.data.ApiResult
import com.konecto.series76.data.AssistantRepository
import com.konecto.series76.data.SessionOut
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

sealed interface ConversationsUiState {
    data object Loading : ConversationsUiState
    data object Empty : ConversationsUiState
    data class Success(val sessions: List<SessionOut>) : ConversationsUiState
    data class Error(val message: String) : ConversationsUiState
}

class ConversationsViewModel(private val repo: AssistantRepository) : ViewModel() {
    private val _state = MutableStateFlow<ConversationsUiState>(ConversationsUiState.Loading)
    val state: StateFlow<ConversationsUiState> = _state.asStateFlow()

    private val _isRefreshing = MutableStateFlow(false)
    val isRefreshing: StateFlow<Boolean> = _isRefreshing.asStateFlow()

    private var job: Job? = null

    init {
        load(flagRefreshing = false)
    }

    /**
     * User-driven reload (pull-to-refresh, Retry). Always flips isRefreshing true -> false so the
     * pull indicator is released even when the screen is in Error/Empty state (Material3 keeps the
     * indicator at its threshold if onRefresh never makes isRefreshing true).
     */
    fun refresh() = load(flagRefreshing = true)

    /**
     * Call on every ON_RESUME (returning from a chat). Reloads silently unless a load is already in
     * flight, which also covers the first resume that coincides with the initial load.
     */
    fun onResume() {
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
        fun factory(repo: AssistantRepository): ViewModelProvider.Factory =
            viewModelFactory { initializer { ConversationsViewModel(repo) } }
    }
}

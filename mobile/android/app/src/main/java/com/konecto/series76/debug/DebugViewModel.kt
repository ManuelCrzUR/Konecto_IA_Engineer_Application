package com.konecto.series76.debug

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.konecto.series76.data.ApiResult
import com.konecto.series76.data.AssistantRepository
import com.konecto.series76.data.MessageOut
import com.konecto.series76.data.ToolTrace
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/** One assistant message: the user question before it and the tools it called. [index] is chronological. */
data class DebugTurn(val index: Int, val question: String, val traces: List<ToolTrace>)

sealed interface DebugUiState {
    data object NoSession : DebugUiState
    data object Loading : DebugUiState
    data class Success(val turns: List<DebugTurn>) : DebugUiState
    data class Error(val message: String) : DebugUiState
}

/** Pairs each assistant message that has a trace with the closest preceding user message. */
fun buildTurns(messages: List<MessageOut>): List<DebugTurn> {
    var question = ""
    val turns = mutableListOf<DebugTurn>()
    for (m in messages) {
        when (m.role) {
            "user" -> question = m.content
            "assistant" -> if (m.trace.isNotEmpty()) turns += DebugTurn(turns.size, question, m.trace)
        }
    }
    return turns
}

class DebugViewModel(
    private val repo: AssistantRepository,
    private val sessionId: String?,
) : ViewModel() {
    private val _state = MutableStateFlow<DebugUiState>(
        if (sessionId == null) DebugUiState.NoSession else DebugUiState.Loading,
    )
    val state: StateFlow<DebugUiState> = _state.asStateFlow()

    private var job: Job? = null

    init { refresh() }

    fun refresh() {
        val id = sessionId ?: return
        job?.cancel()
        _state.value = DebugUiState.Loading
        job = viewModelScope.launch {
            _state.value = when (val r = repo.messages(id)) {
                is ApiResult.Success -> DebugUiState.Success(buildTurns(r.value))
                is ApiResult.Failure -> DebugUiState.Error(r.message)
            }
        }
    }

    companion object {
        fun factory(repo: AssistantRepository, sessionId: String?) = object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T =
                DebugViewModel(repo, sessionId) as T
        }
    }
}

package com.konecto.series76.chat

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.CreationExtras
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import androidx.lifecycle.createSavedStateHandle
import com.konecto.series76.data.ApiResult
import com.konecto.series76.data.AssistantRepository
import com.konecto.series76.data.Product
import com.konecto.series76.voice.speechLocale
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class ChatItem(
    val key: String,
    val role: String,
    val text: String,
    val products: List<Product> = emptyList(),
    /** "es"/"en" as reported by the backend for this answer; null for history and user messages. */
    val language: String? = null,
) {
    val isUser: Boolean get() = role == "user"
}

/** Backend limit for `query` (ConversationRequest.max_length). */
const val MAX_QUERY_CHARS = 2000

private const val SESSION_KEY = "chat_session_id"

data class ChatUiState(
    val sessionId: String? = null,
    val messages: List<ChatItem> = emptyList(),
    val sending: Boolean = false,
    val loading: Boolean = false,
    val error: String? = null,
    /** Whether the error banner offers Retry (transient failures only). */
    val canRetry: Boolean = false,
    val draft: String = "",
    /** Text of the last send that failed; kept so Retry can resend it. */
    val failedText: String? = null,
    /** Whether [failedText] was spoken, so Retry keeps reading the answer aloud. */
    val failedSpoken: Boolean = false,
    /** True while the speech recognizer is listening. */
    val listening: Boolean = false,
    /** True while a recorded question is being transcribed by the backend. */
    val transcribing: Boolean = false,
    /** One informational voice line (e.g. the device recognizer is in use). */
    val notice: String? = null,
    /** Key of the assistant item that must be read aloud once (cleared by [ChatViewModel.onAutoSpoken]). */
    val autoSpeakKey: String? = null,
    /** Spoken answer that arrived but is not shown until its first audio is ready (synchronized voice). */
    val held: ChatItem? = null,
    /** "es" or "en": language of the last question, used for the status label. */
    val statusLang: String = "en",
) {
    /** Something is in flight: the request, or the voice of a held answer. */
    val busy: Boolean get() = sending || held != null

    /** Phase shown by the loading indicator, or null when nothing is pending. */
    val thinkingPhase: ThinkingPhase?
        get() = when {
            transcribing -> ThinkingPhase.Transcribing
            held != null -> ThinkingPhase.Voice
            sending -> ThinkingPhase.Waiting
            else -> null
        }
}

/** Counted from when the speaker starts preparing the held answer; the speaker's own deadline is 10 s. */
const val REVEAL_BACKSTOP_MS = 12_000L

/** Counted from when the answer arrives; only fires if no speaker ever starts preparing it. */
const val SAFETY_BACKSTOP_MS = 30_000L

/**
 * The current session id lives in [savedState] so it survives process death; the nav argument is only
 * the initial value (see [factory]).
 */
class ChatViewModel(
    private val repo: AssistantRepository,
    private val savedState: SavedStateHandle,
    private val revealBackstopMs: Long = REVEAL_BACKSTOP_MS,
    private val safetyBackstopMs: Long = SAFETY_BACKSTOP_MS,
) : ViewModel() {

    private var revealJob: Job? = null

    private val initialSessionId: String? = savedState[SESSION_KEY]

    private val _state = MutableStateFlow(ChatUiState(sessionId = initialSessionId, loading = initialSessionId != null))
    val state: StateFlow<ChatUiState> = _state.asStateFlow()

    private var localCounter = 0L

    init {
        if (initialSessionId != null) load(initialSessionId)
    }

    private fun adoptSession(id: String?) {
        if (id == null) return
        savedState[SESSION_KEY] = id
        _state.update { it.copy(sessionId = id) }
    }

    private fun load(id: String) {
        _state.update { it.copy(loading = true, error = null, canRetry = false) }
        viewModelScope.launch {
            when (val r = repo.messages(id)) {
                is ApiResult.Success -> _state.update { s ->
                    s.copy(
                        loading = false,
                        messages = r.value.map { ChatItem("m${it.id}", it.role, it.content, it.products) },
                    )
                }
                is ApiResult.Failure -> _state.update {
                    it.copy(loading = false, error = r.message, canRetry = r.retryable)
                }
            }
        }
    }

    fun onDraftChange(text: String) = _state.update { it.copy(draft = text.take(MAX_QUERY_CHARS)) }

    /** Ignored while history is loading (a late load must never overwrite local messages) or sending. */
    fun send(text: String, spoken: Boolean = false) {
        val q = text.trim()
        val s = _state.value
        if (q.isEmpty() || q.length > MAX_QUERY_CHARS || s.busy || s.loading) return
        _state.update {
            it.copy(
                messages = it.messages + ChatItem("l${localCounter++}", "user", q),
                statusLang = speechLocale(q).language,
                draft = "",
                error = null,
                canRetry = false,
                failedText = null,
            )
        }
        dispatch(q, spoken)
    }

    fun onVoiceStart() = _state.update { it.copy(listening = true, transcribing = false, error = null, canRetry = false) }

    fun onVoiceTranscribing() = _state.update {
        val last = it.messages.lastOrNull()?.text
        it.copy(listening = false, transcribing = true, statusLang = last?.let { t -> speechLocale(t).language } ?: it.statusLang)
    }

    fun onVoiceNotice(message: String) = _state.update { it.copy(notice = message) }

    fun onVoicePartial(text: String) = onDraftChange(text)

    fun onVoiceFinal(text: String) {
        _state.update { it.copy(listening = false, transcribing = false, notice = null) }
        send(text, spoken = true)
    }

    /** Shown in the error banner without Retry; the draft is kept so typing keeps working. */
    fun onVoiceError(message: String) =
        _state.update { it.copy(listening = false, transcribing = false, notice = null, error = message, canRetry = false) }

    fun onVoiceEnded() = _state.update { it.copy(listening = false, transcribing = false, notice = null) }

    fun onAutoSpoken() = _state.update { it.copy(autoSpeakKey = null) }

    /** First audio is ready (or the device voice took over): show the held answer. No-op for other keys. */
    fun onVoiceReady(key: String) {
        if (_state.value.held?.key != key) return
        revealJob?.cancel()
        _state.update {
            val h = it.held
            // Whatever path reveals it, the one-shot auto-speak flag goes with the held answer.
            if (h == null || h.key != key) it
            else it.copy(held = null, autoSpeakKey = null, messages = it.messages + h)
        }
    }

    /**
     * The speaker started preparing the held answer: restart the reveal backstop from now, so text and
     * voice stay together even when speak() starts late (e.g. the app was in the background).
     */
    fun onVoicePreparing(key: String) {
        if (_state.value.held?.key != key) return
        startReveal(key, revealBackstopMs)
    }

    private fun startReveal(key: String, afterMs: Long) {
        revealJob?.cancel()
        revealJob = viewModelScope.launch {
            delay(afterMs)
            onVoiceReady(key)
        }
    }

    /** Resends the failed text without adding a second user bubble, or reloads history. */
    fun retry() {
        val s = _state.value
        if (s.busy || s.loading) return
        val failed = s.failedText
        if (failed != null) {
            _state.update {
                // The restored draft is the same text; clear it so it is not sent twice.
                it.copy(error = null, canRetry = false, failedText = null, draft = if (it.draft == failed) "" else it.draft)
            }
            dispatch(failed, s.failedSpoken)
        } else if (s.sessionId != null && s.messages.isEmpty()) {
            load(s.sessionId)
        } else {
            _state.update { it.copy(error = null, canRetry = false) }
        }
    }

    private fun dispatch(q: String, spoken: Boolean) {
        _state.update { it.copy(sending = true) }
        viewModelScope.launch {
            when (val r = repo.sendMessage(_state.value.sessionId, q)) {
                is ApiResult.Success -> {
                    adoptSession(r.value.sessionId)
                    val item = ChatItem("l${localCounter++}", "assistant", r.value.answer, r.value.products, r.value.language)
                    _state.update {
                        if (spoken) {
                            it.copy(sending = false, held = item, autoSpeakKey = item.key)
                        } else {
                            it.copy(sending = false, messages = it.messages + item)
                        }
                    }
                    if (spoken) startReveal(item.key, safetyBackstopMs)
                }
                is ApiResult.Failure -> {
                    // Adopt the session the server already created so Retry does not open a second one.
                    adoptSession(r.sessionId)
                    _state.update {
                        val restoredDraft = if (it.draft.isBlank()) q else it.draft
                        if (r.retryable) {
                            it.copy(
                                sending = false, error = r.message, canRetry = true,
                                failedText = q, failedSpoken = spoken, draft = restoredDraft,
                            )
                        } else {
                            // Not retryable: drop the optimistic bubble and give the text back for editing.
                            it.copy(
                                sending = false, error = r.message, canRetry = false, failedText = null,
                                messages = it.messages.dropLast(1), draft = restoredDraft,
                            )
                        }
                    }
                }
            }
        }
    }

    companion object {
        fun factory(repo: AssistantRepository, sessionId: String?): ViewModelProvider.Factory =
            viewModelFactory {
                initializer {
                    val handle = createSavedStateHandle()
                    if (!handle.contains(SESSION_KEY) && sessionId != null) handle[SESSION_KEY] = sessionId
                    ChatViewModel(repo, handle)
                }
            }
    }
}

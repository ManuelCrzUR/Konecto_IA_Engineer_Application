package com.konecto.series76.chat

import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.imeNestedScroll
import androidx.compose.foundation.layout.isImeVisible
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material3.LocalContentColor
import androidx.compose.foundation.layout.consumeWindowInsets
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import android.Manifest
import android.app.Activity
import android.content.Context
import android.content.ContextWrapper
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.core.content.ContextCompat
import com.konecto.series76.voice.AndroidSpeaker
import com.konecto.series76.voice.AndroidVoiceInput
import com.konecto.series76.voice.VoiceEvent
import com.konecto.series76.voice.VoiceIcons
import com.konecto.series76.voice.speakableText
import com.konecto.series76.voice.speechLocale
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.konecto.series76.App

@Composable
fun ChatScreen(sessionId: String?, onBack: () -> Unit, onOpenDebug: (sessionId: String?) -> Unit) {
    val repo = (LocalContext.current.applicationContext as App).container.repository
    val vm: ChatViewModel = viewModel(key = "chat-$sessionId", factory = ChatViewModel.factory(repo, sessionId))
    ChatRoute(vm, onBack, onOpenDebug)
}

@Composable
fun ChatRoute(vm: ChatViewModel, onBack: () -> Unit, onOpenDebug: (sessionId: String?) -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    val context = LocalContext.current
    val voice = remember {
        (context.applicationContext as? App)?.container?.newVoiceInput() ?: AndroidVoiceInput(context)
    }
    val speaker = remember { AndroidSpeaker(context) }
    val speakingKey by speaker.speakingKey.collectAsStateWithLifecycle()
    DisposableEffect(Unit) {
        onDispose {
            voice.release()
            speaker.release()
        }
    }
    LaunchedEffect(voice) {
        voice.events.collect { e ->
            when (e) {
                VoiceEvent.Listening -> vm.onVoiceStart()
                is VoiceEvent.Partial -> vm.onVoicePartial(e.text)
                is VoiceEvent.Final -> vm.onVoiceFinal(e.text)
                is VoiceEvent.Error -> vm.onVoiceError(e.message)
                VoiceEvent.Ended -> vm.onVoiceEnded()
                VoiceEvent.Transcribing -> vm.onVoiceTranscribing()
                is VoiceEvent.Notice -> vm.onVoiceNotice(e.message)
                is VoiceEvent.Unavailable -> vm.onVoiceEnded() // only reaches here without a fallback
            }
        }
    }
    LaunchedEffect(state.autoSpeakKey) {
        val key = state.autoSpeakKey ?: return@LaunchedEffect
        state.messages.firstOrNull { it.key == key }?.let { speaker.speak(key, speakableText(it.text)) }
        vm.onAutoSpoken()
    }

    fun startListening() {
        speaker.stop()
        val lastAnswer = state.messages.lastOrNull { !it.isUser }?.text
        voice.start(lastAnswer?.let { speechLocale(it).toLanguageTag() })
    }
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) {
            startListening()
        } else {
            val activity = context.findActivity()
            val canAskAgain = activity?.let {
                androidx.core.app.ActivityCompat.shouldShowRequestPermissionRationale(it, Manifest.permission.RECORD_AUDIO)
            } ?: false
            vm.onVoiceError(
                if (canAskAgain) "Microphone permission needed \u2014 you can still type"
                else "Microphone permission is off \u2014 enable it in Settings > Apps > Series 76, or type instead",
            )
        }
    }
    ChatContent(
        state = state,
        onDraftChange = vm::onDraftChange,
        onSend = { vm.send(it) },
        onRetry = vm::retry,
        onBack = onBack,
        onTitleTapsFired = { onOpenDebug(vm.state.value.sessionId) },
        onMic = {
            when {
                state.transcribing -> Unit
                state.listening -> voice.stop()
                ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) ==
                    PackageManager.PERMISSION_GRANTED -> startListening()
                else -> permission.launch(Manifest.permission.RECORD_AUDIO)
            }
        },
        speakingKey = speakingKey,
        onSpeak = { item ->
            if (speakingKey == item.key) speaker.stop() else speaker.speak(item.key, speakableText(item.text))
        },
    )
}

private tailrec fun Context.findActivity(): Activity? = when (this) {
    is Activity -> this
    is ContextWrapper -> baseContext.findActivity()
    else -> null
}

@Composable
fun ChatContent(
    state: ChatUiState,
    onDraftChange: (String) -> Unit,
    onSend: (String) -> Unit,
    onRetry: () -> Unit,
    onBack: () -> Unit,
    onTitleTapsFired: () -> Unit,
    onMic: () -> Unit = {},
    speakingKey: String? = null,
    onSpeak: (ChatItem) -> Unit = {},
) {
    // Scaffold's default contentWindowInsets = systemBars (status + nav bar, no IME): inner already clears
    // the nav bar; imePadding() after consumeWindowInsets(inner) adds only the IME's extra height (no double padding).
    Scaffold(topBar = { ChatHeader(onBack, onTitleTapsFired) }) { inner ->
        Column(Modifier.fillMaxSize().padding(inner).consumeWindowInsets(inner).imePadding()) {
            Box(Modifier.weight(1f).fillMaxWidth()) {
                when {
                    state.loading -> CircularProgressIndicator(Modifier.align(Alignment.Center))
                    state.messages.isEmpty() && !state.sending ->
                        EmptyChat(onSend, Modifier.fillMaxSize())
                    else -> MessageList(state, speakingKey, onSpeak)
                }
            }
            if (state.error != null) ErrorBanner(state.error, state.canRetry, onRetry)
            InputRow(state, onDraftChange, onSend, onMic)
        }
    }
}

/**
 * Newest-first list with reverseLayout: index 0 (typing indicator or last message) is anchored to the
 * bottom, so the viewport shrinking with the IME keeps it visible frame by frame.
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun MessageList(state: ChatUiState, speakingKey: String?, onSpeak: (ChatItem) -> Unit) {
    val listState = rememberLazyListState()
    val reversed = remember(state.messages) { state.messages.asReversed() }
    val count = state.messages.size + if (state.sending) 1 else 0
    // reverseLayout: index 0 is the newest item. Follow it only when already near it or after the user's own send.
    val nearNewest = { listState.firstVisibleItemIndex <= 1 }
    LaunchedEffect(count) {
        if (count > 0 && (nearNewest() || state.messages.lastOrNull()?.isUser == true)) listState.animateScrollToItem(0)
    }
    val imeVisible = WindowInsets.isImeVisible
    // Keyed on the IME state: the effect restarts when the keyboard opens (not on first composition).
    var imeSeen by remember { mutableStateOf(imeVisible) }
    LaunchedEffect(imeVisible) {
        if (imeVisible && !imeSeen && nearNewest()) listState.animateScrollToItem(0)
        imeSeen = imeVisible
    }
    // Messages present on first composition (history) never animate; new ones animate once.
    val skip = remember { state.messages.mapTo(mutableSetOf()) { it.key } }
    LazyColumn(
        Modifier.fillMaxSize().imeNestedScroll().testTag("chat_list"),
        state = listState,
        reverseLayout = true,
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        if (state.sending) {
            item(key = "typing", contentType = "typing") { ThinkingRow() }
        }
        items(reversed, key = { it.key }, contentType = { it.role }) { item ->
            MessageItem(item, animate = item.key !in skip, onAnimated = { skip.add(item.key) }, speakingKey = speakingKey, onSpeak = onSpeak)
        }
    }
}

@Composable
private fun InputRow(state: ChatUiState, onDraftChange: (String) -> Unit, onSend: (String) -> Unit, onMic: () -> Unit) {
    Row(Modifier.fillMaxWidth().padding(8.dp), verticalAlignment = Alignment.CenterVertically) {
        OutlinedTextField(
            value = state.draft,
            onValueChange = onDraftChange,
            modifier = Modifier.weight(1f).testTag("chat_input"),
            placeholder = {
                Text(
                    when {
                        state.transcribing -> "Transcribing\u2026"
                        state.listening -> "Listening\u2026"
                        else -> "Message"
                    },
                    Modifier.semantics { liveRegion = LiveRegionMode.Polite },
                )
            },
            supportingText = {
                if (state.notice != null) {
                    Text(state.notice, Modifier.testTag("chat_voice_notice"))
                } else if (state.draft.length >= MAX_QUERY_CHARS - 200) {
                    Text("${state.draft.length}/$MAX_QUERY_CHARS", Modifier.testTag("chat_counter"))
                }
            },
            shape = RoundedCornerShape(24.dp),
            maxLines = 4,
        )
        if (!state.sending && !state.loading) {
            IconButton(
                onClick = onMic, enabled = !state.transcribing,
                modifier = Modifier.size(48.dp).testTag("chat_mic")
                    .semantics { stateDescription = if (state.listening) "Recording" else "Not recording" },
            ) {
                Icon(
                    if (state.listening) VoiceIcons.Stop else VoiceIcons.Mic,
                    contentDescription = if (state.listening) "Stop recording" else "Speak",
                    tint = if (state.listening) MaterialTheme.colorScheme.primary else LocalContentColor.current,
                )
            }
        }
        IconButton(
            onClick = { onSend(state.draft) },
            enabled = !state.sending && !state.loading && state.draft.isNotBlank(),
            modifier = Modifier.size(48.dp).testTag("chat_send"),
        ) {
            Icon(Icons.AutoMirrored.Filled.Send, contentDescription = "Send")
        }
    }
}

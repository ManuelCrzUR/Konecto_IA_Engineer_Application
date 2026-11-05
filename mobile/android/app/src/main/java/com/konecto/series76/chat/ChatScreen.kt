package com.konecto.series76.chat

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
import androidx.compose.runtime.Composable
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
    ChatContent(
        state = state,
        onDraftChange = vm::onDraftChange,
        onSend = vm::send,
        onRetry = vm::retry,
        onBack = onBack,
        onTitleTapsFired = { onOpenDebug(vm.state.value.sessionId) },
    )
}

@Composable
fun ChatContent(
    state: ChatUiState,
    onDraftChange: (String) -> Unit,
    onSend: (String) -> Unit,
    onRetry: () -> Unit,
    onBack: () -> Unit,
    onTitleTapsFired: () -> Unit,
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
                    else -> MessageList(state)
                }
            }
            if (state.error != null) ErrorBanner(state.error, state.canRetry, onRetry)
            InputRow(state, onDraftChange, onSend)
        }
    }
}

/**
 * Newest-first list with reverseLayout: index 0 (typing indicator or last message) is anchored to the
 * bottom, so the viewport shrinking with the IME keeps it visible frame by frame.
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun MessageList(state: ChatUiState) {
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
            MessageItem(item, animate = item.key !in skip, onAnimated = { skip.add(item.key) })
        }
    }
}

@Composable
private fun InputRow(state: ChatUiState, onDraftChange: (String) -> Unit, onSend: (String) -> Unit) {
    Row(Modifier.fillMaxWidth().padding(8.dp), verticalAlignment = Alignment.CenterVertically) {
        OutlinedTextField(
            value = state.draft,
            onValueChange = onDraftChange,
            modifier = Modifier.weight(1f).testTag("chat_input"),
            placeholder = { Text("Message") },
            supportingText = {
                if (state.draft.length >= MAX_QUERY_CHARS - 200) {
                    Text("${state.draft.length}/$MAX_QUERY_CHARS", Modifier.testTag("chat_counter"))
                }
            },
            shape = RoundedCornerShape(24.dp),
            maxLines = 4,
        )
        IconButton(
            onClick = { onSend(state.draft) },
            enabled = !state.sending && !state.loading && state.draft.isNotBlank(),
            modifier = Modifier.testTag("chat_send"),
        ) {
            Icon(Icons.AutoMirrored.Filled.Send, contentDescription = "Send")
        }
    }
}

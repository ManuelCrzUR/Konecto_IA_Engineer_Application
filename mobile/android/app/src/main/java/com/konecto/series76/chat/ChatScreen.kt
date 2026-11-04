package com.konecto.series76.chat

import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.consumeWindowInsets
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.konecto.series76.App
import com.konecto.series76.ui.ComparisonTable
import com.konecto.series76.ui.ProductCard

const val EMPTY_HINT = "Ask about a part number or your requirements, e.g. 'need 200 Nm, 220V, weatherproof'"

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

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatContent(
    state: ChatUiState,
    onDraftChange: (String) -> Unit,
    onSend: (String) -> Unit,
    onRetry: () -> Unit,
    onBack: () -> Unit,
    onTitleTapsFired: () -> Unit,
) {
    val counter = remember { TapCounter() }
    val noRipple = remember { MutableInteractionSource() }
    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        "Series 76 Assistant",
                        Modifier
                            .testTag("chat_title")
                            .clickable(interactionSource = noRipple, indication = null) {
                                if (counter.tap()) onTitleTapsFired()
                            },
                    )
                },
                navigationIcon = {
                    IconButton(onClick = onBack, modifier = Modifier.testTag("chat_back")) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
            )
        },
    ) { inner ->
        Column(Modifier.fillMaxSize().padding(inner).consumeWindowInsets(inner).imePadding()) {
            Box(Modifier.weight(1f).fillMaxWidth()) {
                when {
                    state.loading -> CircularProgressIndicator(Modifier.align(Alignment.Center))
                    state.messages.isEmpty() && !state.sending -> Text(
                        EMPTY_HINT,
                        Modifier.align(Alignment.Center).padding(32.dp).testTag("chat_hint"),
                        style = MaterialTheme.typography.bodyLarge,
                    )
                    else -> MessageList(state)
                }
            }
            if (state.error != null) ErrorBanner(state.error, state.canRetry, onRetry)
            InputRow(state, onDraftChange, onSend)
        }
    }
}

@Composable
private fun MessageList(state: ChatUiState) {
    val listState = rememberLazyListState()
    val count = state.messages.size + if (state.sending) 1 else 0
    LaunchedEffect(count) { if (count > 0) listState.scrollToItem(count - 1) }
    LazyColumn(
        Modifier.fillMaxSize().testTag("chat_list"),
        state = listState,
        contentPadding = androidx.compose.foundation.layout.PaddingValues(12.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        items(state.messages, key = { it.key }, contentType = { it.role }) { item ->
            MessageBubble(item)
        }
        if (state.sending) {
            item(key = "typing", contentType = "typing") {
                Text("Thinking…", Modifier.testTag("typing_indicator"), style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

@Composable
private fun MessageBubble(item: ChatItem) {
    val align = if (item.isUser) Alignment.End else Alignment.Start
    Column(Modifier.fillMaxWidth(), horizontalAlignment = align, verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Surface(
            shape = RoundedCornerShape(16.dp),
            color = if (item.isUser) MaterialTheme.colorScheme.primaryContainer
            else MaterialTheme.colorScheme.surfaceVariant,
        ) {
            Text(plainText(item.text), Modifier.padding(12.dp), style = MaterialTheme.typography.bodyMedium)
        }
        if (!item.isUser) {
            item.products.forEach { ProductCard(it) }
            if (item.products.size >= 2) ComparisonTable(item.products)
        }
    }
}

@Composable
private fun ErrorBanner(message: String, canRetry: Boolean, onRetry: () -> Unit) {
    Surface(color = MaterialTheme.colorScheme.errorContainer, modifier = Modifier.fillMaxWidth().testTag("chat_error")) {
        Row(Modifier.padding(horizontal = 12.dp, vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
            Text(message, Modifier.weight(1f), color = MaterialTheme.colorScheme.onErrorContainer)
            if (canRetry) TextButton(onClick = onRetry, modifier = Modifier.testTag("chat_retry")) { Text("Retry") }
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

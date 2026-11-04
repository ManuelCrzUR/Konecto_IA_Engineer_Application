package com.konecto.series76.conversations

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExtendedFloatingActionButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LifecycleEventEffect
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.konecto.series76.App
import com.konecto.series76.data.SessionOut
import java.time.Instant

/** onOpenChat(null) = new conversation. [viewModel] is overridable for tests. */
@Composable
fun ConversationsScreen(
    onOpenChat: (sessionId: String?) -> Unit,
    viewModel: ConversationsViewModel = defaultViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val refreshing by viewModel.isRefreshing.collectAsStateWithLifecycle()
    LifecycleEventEffect(Lifecycle.Event.ON_RESUME) { viewModel.onResume() }
    ConversationsContent(state, refreshing, viewModel::refresh, onOpenChat)
}

@Composable
private fun defaultViewModel(): ConversationsViewModel {
    val app = LocalContext.current.applicationContext as App
    return viewModel(factory = ConversationsViewModel.factory(app.container.repository))
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ConversationsContent(
    state: ConversationsUiState,
    refreshing: Boolean,
    onRefresh: () -> Unit,
    onOpenChat: (String?) -> Unit,
) {
    Scaffold(
        topBar = { TopAppBar(title = { Text("Conversations") }) },
        floatingActionButton = {
            ExtendedFloatingActionButton(
                onClick = { onOpenChat(null) },
                icon = { Icon(Icons.Default.Add, contentDescription = null) },
                text = { Text("New conversation") },
                modifier = Modifier.testTag("new_conversation"),
            )
        },
    ) { padding ->
        PullToRefreshBox(
            isRefreshing = refreshing,
            onRefresh = onRefresh,
            modifier = Modifier.fillMaxSize().padding(padding),
        ) {
            when (state) {
                ConversationsUiState.Loading -> Box(Modifier.fillMaxSize(), Alignment.Center) {
                    CircularProgressIndicator()
                }
                ConversationsUiState.Empty -> Centered {
                    Text("No conversations yet. Start one!", modifier = Modifier.testTag("empty_state"))
                }
                is ConversationsUiState.Error -> Centered {
                    Text(state.message)
                    Button(onClick = onRefresh, modifier = Modifier.testTag("error_retry")) { Text("Retry") }
                }
                is ConversationsUiState.Success -> SessionList(state.sessions, onOpenChat)
            }
        }
    }
}

@Composable
private fun Centered(content: @Composable () -> Unit) {
    Column(
        modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp, Alignment.CenterVertically),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) { content() }
}

@Composable
private fun SessionList(sessions: List<SessionOut>, onOpenChat: (String?) -> Unit) {
    val now = remember(sessions) { Instant.now() }
    LazyColumn(Modifier.fillMaxSize().testTag("conversations_list")) {
        items(sessions, key = { it.id }, contentType = { "session" }) { s ->
            Column(Modifier.clickable { onOpenChat(s.id) }.testTag("session_${s.id}")) {
                ListItem(
                    headlineContent = { Text(s.title, maxLines = 2, overflow = TextOverflow.Ellipsis) },
                    supportingContent = {
                        Text(formatRelative(s.updatedAt, now), color = MaterialTheme.colorScheme.onSurfaceVariant)
                    },
                )
                HorizontalDivider()
            }
        }
        // Keep the last item clear of the FAB.
        item(contentType = "spacer") { Box(Modifier.padding(bottom = 88.dp)) }
    }
}

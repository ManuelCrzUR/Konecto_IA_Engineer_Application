package com.konecto.series76.conversations

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExtendedFloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalFocusManager
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
import com.konecto.series76.ui.axel.AxelAvatar
import com.konecto.series76.ui.axel.AxelState
import com.konecto.series76.ui.theme.AxelTheme
import com.konecto.series76.ui.theme.ThemeMode
import java.time.Instant

/** onOpenChat(null) = new conversation. [viewModel] is overridable for tests. */
@Composable
fun ConversationsScreen(
    onOpenChat: (sessionId: String?) -> Unit,
    viewModel: ConversationsViewModel = defaultViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val search by viewModel.search.collectAsStateWithLifecycle()
    val query by viewModel.query.collectAsStateWithLifecycle()
    val refreshing by viewModel.isRefreshing.collectAsStateWithLifecycle()
    val themeMode by viewModel.themeMode.collectAsStateWithLifecycle()
    LifecycleEventEffect(Lifecycle.Event.ON_RESUME) { viewModel.onResume() }
    ConversationsContent(
        state, search, query, refreshing, themeMode,
        viewModel::onQueryChange, viewModel::setThemeMode, viewModel::refresh, viewModel::retrySearch, onOpenChat,
    )
}

@Composable
private fun defaultViewModel(): ConversationsViewModel {
    val container = (LocalContext.current.applicationContext as App).container
    return viewModel(factory = ConversationsViewModel.factory(container.repository, container.themePreferences))
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ConversationsContent(
    state: ConversationsUiState,
    search: SearchUiState,
    query: String,
    refreshing: Boolean,
    themeMode: ThemeMode,
    onQueryChange: (String) -> Unit,
    onThemeMode: (ThemeMode) -> Unit,
    onRefresh: () -> Unit,
    onRetrySearch: () -> Unit,
    onOpenChat: (String?) -> Unit,
) {
    val focus = LocalFocusManager.current
    // Back leaves search mode (clears the query) instead of exiting the app.
    BackHandler(enabled = query.isNotEmpty()) {
        onQueryChange("")
        focus.clearFocus()
    }
    Scaffold(
        topBar = { ConversationsHeader(themeMode, onThemeMode, query, onQueryChange) },
        floatingActionButton = {
            ExtendedFloatingActionButton(
                onClick = { onOpenChat(null) },
                icon = { Icon(Icons.Default.Add, contentDescription = null) },
                text = { Text("New conversation") },
                containerColor = MaterialTheme.colorScheme.primary,
                contentColor = MaterialTheme.colorScheme.onPrimary,
                modifier = Modifier.testTag("new_conversation"),
            )
        },
    ) { padding ->
        Box(Modifier.fillMaxSize().padding(padding)) {
            if (search != SearchUiState.Inactive) {
                SearchBody(search, onRetrySearch, onOpenChat)
            } else {
                PullToRefreshBox(isRefreshing = refreshing, onRefresh = onRefresh, modifier = Modifier.fillMaxSize()) {
                    ListBody(state, onRefresh, onOpenChat)
                }
            }
        }
    }
}

@Composable
private fun ListBody(state: ConversationsUiState, onRefresh: () -> Unit, onOpenChat: (String?) -> Unit) {
    when (state) {
        ConversationsUiState.Loading -> Box(Modifier.fillMaxSize(), Alignment.Center) { CircularProgressIndicator() }
        ConversationsUiState.Empty -> Centered {
            AxelAvatar(AxelState.IDLE, size = 96.dp)
            Text("No conversations yet. Start one!", modifier = Modifier.testTag("empty_state"))
        }
        is ConversationsUiState.Error -> Centered {
            AxelAvatar(AxelState.PROBLEM, size = 96.dp)
            Text(state.message)
            Button(onClick = onRefresh, modifier = Modifier.testTag("error_retry")) { Text("Retry") }
        }
        is ConversationsUiState.Success -> SessionList(state.sessions, onOpenChat)
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
    LazyColumn(
        Modifier.fillMaxSize().testTag("conversations_list"),
        contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        items(sessions, key = { it.id }, contentType = { "session" }) { s ->
            Surface(
                color = MaterialTheme.colorScheme.surface,
                shape = RoundedCornerShape(20.dp),
                border = BorderStroke(1.dp, AxelTheme.colors.divider),
                onClick = { onOpenChat(s.id) },
                modifier = Modifier.fillMaxWidth().animateItem().testTag("session_${s.id}"),
            ) {
                Row(Modifier.padding(horizontal = 16.dp, vertical = 14.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(
                        s.title, style = MaterialTheme.typography.titleSmall,
                        maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f),
                    )
                    Text(formatRelative(s.updatedAt, now), style = MaterialTheme.typography.labelSmall, color = AxelTheme.colors.textTertiary)
                }
            }
        }
        // Keep the last item clear of the FAB.
        item(contentType = "spacer") { Spacer(Modifier.height(72.dp)) }
    }
}

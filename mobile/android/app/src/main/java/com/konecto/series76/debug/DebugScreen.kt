package com.konecto.series76.debug

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.konecto.series76.App
import com.konecto.series76.ui.AxelHeader
import com.konecto.series76.ui.theme.AxelTheme

const val NO_SESSION_TEXT =
    "Send a message first: the debug view shows the tool calls of this conversation"

@Composable
fun DebugScreen(sessionId: String?, onBack: () -> Unit) {
    val repo = (LocalContext.current.applicationContext as App).container.repository
    val vm: DebugViewModel = viewModel(factory = DebugViewModel.factory(repo, sessionId))
    val state by vm.state.collectAsStateWithLifecycle()
    DebugContent(state, onBack, vm::refresh)
}

@Composable
fun DebugContent(state: DebugUiState, onBack: () -> Unit, onRefresh: () -> Unit) {
    Scaffold(topBar = { DebugHeader(state, onBack, onRefresh) }) { padding ->
        Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) {
            when (state) {
                DebugUiState.NoSession -> Message(NO_SESSION_TEXT)
                DebugUiState.Loading -> CircularProgressIndicator()
                is DebugUiState.Error -> Column(
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    Message(state.message)
                    Button(onClick = onRefresh, modifier = Modifier.testTag("debug_retry")) { Text("Retry") }
                }
                is DebugUiState.Success ->
                    if (state.turns.isEmpty()) Message("No tool calls yet") else TurnList(state.turns)
            }
        }
    }
}

@Composable
private fun DebugHeader(state: DebugUiState, onBack: () -> Unit, onRefresh: () -> Unit) {
    AxelHeader {
        IconButton(onClick = onBack, modifier = Modifier.testTag("debug_back")) {
            Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
        }
        Text(
            "Debug", Modifier.weight(1f).padding(start = 4.dp),
            style = AxelTheme.typography.title.copy(fontSize = 18.sp, fontWeight = FontWeight.SemiBold),
        )
        if (state is DebugUiState.Success) SummaryChip(summarize(state.turns))
        IconButton(onClick = onRefresh, modifier = Modifier.testTag("debug_refresh")) {
            Icon(Icons.Filled.Refresh, contentDescription = "Refresh")
        }
    }
}

@Composable
private fun SummaryChip(text: String) = Box(
    Modifier
        .testTag("debug_summary")
        .height(28.dp)
        .clip(RoundedCornerShape(14.dp))
        .background(MaterialTheme.colorScheme.surfaceContainer)
        .padding(horizontal = 10.dp),
    contentAlignment = Alignment.Center,
) {
    Text(
        text,
        style = AxelTheme.typography.label.copy(fontSize = 12.sp, fontWeight = FontWeight.Medium),
        color = AxelTheme.colors.accentText,
    )
}

@Composable
private fun Message(text: String) =
    Text(text, modifier = Modifier.padding(24.dp), style = MaterialTheme.typography.bodyLarge)

@Composable
private fun TurnList(turns: List<DebugTurn>) {
    val newestFirst = remember(turns) { turns.asReversed() }
    LazyColumn(
        Modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        items(newestFirst, key = { it.index }, contentType = { "turn" }) { turn ->
            Column(
                Modifier.testTag("debug_turn_${turn.index}"),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                Text(
                    "Turn ${turn.index + 1} · \"${turn.question}\"",
                    style = AxelTheme.typography.label.copy(color = AxelTheme.colors.textTertiary),
                )
                turn.traces.forEachIndexed { i, trace -> TraceCard(turn.index, i, trace) }
            }
        }
    }
}

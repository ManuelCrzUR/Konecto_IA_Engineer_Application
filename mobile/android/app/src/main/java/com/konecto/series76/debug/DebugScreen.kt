package com.konecto.series76.debug

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.konecto.series76.App
import com.konecto.series76.data.ToolTrace

private const val GUARD_TOOL = "number_guard"
private const val COLLAPSED_LINES = 12
const val NO_SESSION_TEXT =
    "Send a message first: the debug view shows the tool calls of this conversation"

@Composable
fun DebugScreen(sessionId: String?, onBack: () -> Unit) {
    val repo = (LocalContext.current.applicationContext as App).container.repository
    val vm: DebugViewModel = viewModel(factory = DebugViewModel.factory(repo, sessionId))
    val state by vm.state.collectAsStateWithLifecycle()
    DebugContent(state, onBack, vm::refresh)
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DebugContent(state: DebugUiState, onBack: () -> Unit, onRefresh: () -> Unit) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Debug") },
                navigationIcon = {
                    IconButton(onClick = onBack, modifier = Modifier.testTag("debug_back")) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
                actions = {
                    IconButton(onClick = onRefresh, modifier = Modifier.testTag("debug_refresh")) {
                        Icon(Icons.Filled.Refresh, contentDescription = "Refresh")
                    }
                },
            )
        },
    ) { padding ->
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
private fun Message(text: String) =
    Text(text, modifier = Modifier.padding(24.dp), style = MaterialTheme.typography.bodyLarge)

@Composable
private fun TurnList(turns: List<DebugTurn>) {
    val newestFirst = remember(turns) { turns.asReversed() }
    LazyColumn(
        Modifier.fillMaxSize(),
        contentPadding = androidx.compose.foundation.layout.PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        items(newestFirst, key = { it.index }, contentType = { "turn" }) { turn ->
            Column(Modifier.testTag("debug_turn_${turn.index}"), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(turn.question, style = MaterialTheme.typography.titleMedium)
                turn.traces.forEachIndexed { i, trace -> TraceCard(turn.index, i, trace) }
            }
        }
    }
}

@Composable
private fun TraceCard(turnIndex: Int, traceIndex: Int, trace: ToolTrace) {
    val guard = trace.tool == GUARD_TOOL
    val params = remember(trace) { prettyJson(trace.params) }
    val result = remember(trace) { prettyJson(trace.result) }
    Card(
        Modifier.fillMaxWidth().testTag("trace_${turnIndex}_$traceIndex"),
        colors = CardDefaults.cardColors(
            containerColor = if (guard) MaterialTheme.colorScheme.errorContainer
            else MaterialTheme.colorScheme.surface,
        ),
    ) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            if (guard) {
                Text(
                    "Number guard fired",
                    modifier = Modifier.testTag("guard_badge"),
                    color = MaterialTheme.colorScheme.error,
                    fontWeight = FontWeight.Bold,
                )
            }
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text(trace.tool, Modifier.testTag("trace_tool"), fontWeight = FontWeight.Bold)
                Text(formatDuration(trace.durationMs), Modifier.testTag("trace_duration"))
            }
            Label("Params")
            Code(params)
            Label("Result")
            CollapsibleCode(result)
        }
    }
}

@Composable
private fun Label(text: String) =
    Text(text, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.secondary)

@Composable
private fun Code(text: String) = Text(
    text,
    modifier = Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()),
    fontFamily = FontFamily.Monospace,
    fontSize = 12.sp,
    softWrap = false,
)

@Composable
private fun CollapsibleCode(text: String) {
    val lines = remember(text) { text.lines() }
    var expanded by rememberSaveable(text) { mutableStateOf(false) }
    val long = lines.size > COLLAPSED_LINES
    Code(if (long && !expanded) lines.take(COLLAPSED_LINES).joinToString("\n") + "\n…" else text)
    if (long) {
        TextButton(onClick = { expanded = !expanded }, modifier = Modifier.testTag("result_toggle")) {
            Text(if (expanded) "Show less" else "Show all")
        }
    }
}

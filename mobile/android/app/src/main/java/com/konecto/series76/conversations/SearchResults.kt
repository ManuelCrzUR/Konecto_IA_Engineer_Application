package com.konecto.series76.conversations

import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.height
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import com.konecto.series76.data.SessionOut
import com.konecto.series76.ui.theme.AxelTheme
import java.time.Instant

/** Same characters as [text], with every case-insensitive occurrence of [query] styled. Never alters the text. */
fun highlight(text: String, query: String, style: SpanStyle): AnnotatedString {
    val q = query.trim()
    if (q.isEmpty()) return AnnotatedString(text)
    return buildAnnotatedString {
        var from = 0
        while (true) {
            val i = text.indexOf(q, from, ignoreCase = true)
            if (i < 0) break
            append(text.substring(from, i))
            withStyle(style) { append(text.substring(i, i + q.length)) }
            from = i + q.length
        }
        append(text.substring(from))
    }
}

@Composable
fun SearchBody(state: SearchUiState, onRetry: () -> Unit, onOpenChat: (String?) -> Unit) {
    when (state) {
        SearchUiState.Inactive -> Unit
        SearchUiState.Searching -> Box(Modifier.fillMaxSize().testTag("search_loading"), Alignment.Center) {
            CircularProgressIndicator()
        }
        is SearchUiState.NoResults -> Message("No conversations match \"${state.query}\"", "search_empty")
        is SearchUiState.Error -> Message(state.message, "search_error") {
            Button(onClick = onRetry, modifier = Modifier.testTag("search_retry")) { Text("Retry") }
        }
        is SearchUiState.Results -> ResultList(state, state.query, onOpenChat)
    }
}

@Composable
private fun Message(text: String, tag: String, action: @Composable () -> Unit = {}) {
    Box(Modifier.fillMaxSize().padding(24.dp), Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(16.dp)) {
            Text(text, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.testTag(tag))
            action()
        }
    }
}

@Composable
private fun ResultList(r: SearchUiState.Results, q: String, onOpenChat: (String?) -> Unit) {
    val now = remember(r) { Instant.now() }
    LazyColumn(Modifier.fillMaxSize().testTag("search_results"), contentPadding = PaddingValues(horizontal = 8.dp)) {
        item(key = "count") {
            Text(
                if (r.count == 1) "1 result" else "${r.count} results",
                style = AxelTheme.typography.label, color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(start = 12.dp, top = 8.dp).testTag("search_count"),
            )
        }
        section("In titles", "search_section_title", r.titles, q, now, onOpenChat)
        section("In messages", "search_section_message", r.messages, q, now, onOpenChat)
        item(key = "spacer") { Spacer(Modifier.height(88.dp)) }
    }
}

private fun LazyListScope.section(
    label: String, tag: String, rows: List<SessionOut>, q: String, now: Instant, onOpenChat: (String?) -> Unit,
) {
    if (rows.isEmpty()) return
    item(key = tag) {
        Text(
            label, style = AxelTheme.typography.label, color = AxelTheme.colors.accentText,
            modifier = Modifier.padding(start = 12.dp, top = 14.dp, bottom = 4.dp).testTag(tag).semantics { heading() },
        )
    }
    items(rows, key = { "$tag-${it.id}" }) { s -> ResultRow(s, q, now, onOpenChat, Modifier.animateItem()) }
}

@Composable
private fun ResultRow(s: SessionOut, q: String, now: Instant, onOpenChat: (String?) -> Unit, modifier: Modifier) {
    val hl = SpanStyle(color = MaterialTheme.colorScheme.primary, fontWeight = FontWeight.SemiBold)
    val snippet = s.match?.snippet?.takeUnless { it == s.title }
    val titleText = remember(s.title, q, hl.color) { highlight(s.title, q, hl) }
    val snippetText = remember(snippet, q, hl.color) { snippet?.let { highlight(it, q, hl) } }
    Column(
        modifier.fillMaxWidth().heightIn(min = 48.dp).clip(RoundedCornerShape(20.dp))
            .clickable { onOpenChat(s.id) }.padding(12.dp).testTag("search_result_${s.id}"),
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(
                titleText, style = MaterialTheme.typography.titleSmall,
                maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f),
            )
            Text(formatRelative(s.updatedAt, now), style = MaterialTheme.typography.labelSmall, color = AxelTheme.colors.textTertiary)
        }
        if (snippetText != null) {
            Text(
                snippetText, style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 2, overflow = TextOverflow.Ellipsis,
            )
        }
    }
}

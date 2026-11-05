package com.konecto.series76.debug

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.konecto.series76.data.ToolTrace
import com.konecto.series76.ui.theme.AxelTheme

private const val GUARD_TOOL = "number_guard"
private const val COLLAPSED_LINES = 6
private val CardShape = RoundedCornerShape(24.dp)
private val CodeShape = RoundedCornerShape(14.dp)

/** One tool call: name, duration, Params and Result. The number guard gets a caution border. */
@Composable
fun TraceCard(turnIndex: Int, traceIndex: Int, trace: ToolTrace) {
    val guard = trace.tool == GUARD_TOOL
    val colors = AxelTheme.colors
    val params = remember(trace) { prettyJson(trace.params) }
    val result = remember(trace) { prettyJson(trace.result) }
    Card(
        modifier = Modifier.fillMaxWidth().testTag("trace_${turnIndex}_$traceIndex"),
        shape = CardShape,
        colors = CardDefaults.cardColors(
            containerColor = if (guard) colors.cautionContainer else MaterialTheme.colorScheme.surface,
        ),
        border = when {
            guard -> BorderStroke(1.dp, colors.caution)
            else -> BorderStroke(1.dp, colors.cardBorder)
        },
    ) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            if (guard) GuardHeader()
            Row(
                Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    trace.tool,
                    Modifier.testTag("trace_tool"),
                    style = AxelTheme.typography.code.copy(fontSize = 15.sp, fontWeight = FontWeight.Bold),
                    color = MaterialTheme.colorScheme.primary,
                )
                Text(
                    formatDuration(trace.durationMs),
                    Modifier.testTag("trace_duration"),
                    style = MaterialTheme.typography.bodySmall.copy(fontFeatureSettings = "tnum"),
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            SectionLabel("Params")
            CodeBlock(params, colors.accentText)
            SectionLabel("Result")
            CollapsibleCode(result)
        }
    }
}

@Composable
private fun GuardHeader() = Row(
    Modifier.fillMaxWidth(),
    horizontalArrangement = Arrangement.spacedBy(8.dp),
    verticalAlignment = Alignment.CenterVertically,
) {
    Icon(
        Icons.Filled.Warning,
        contentDescription = null,
        tint = AxelTheme.colors.caution,
        modifier = Modifier.size(18.dp),
    )
    Text(
        "Number guard fired",
        modifier = Modifier.testTag("guard_badge"),
        color = AxelTheme.colors.caution,
        style = MaterialTheme.typography.bodyLarge.copy(fontSize = 14.sp, fontWeight = FontWeight.Bold),
    )
}

@Composable
private fun SectionLabel(text: String) = Text(
    text,
    style = AxelTheme.typography.label.copy(fontSize = 12.sp, fontWeight = FontWeight.SemiBold),
    color = AxelTheme.colors.textTertiary,
)

/** Monospace block on codeBackground. Scrolls sideways instead of wrapping. */
@Composable
private fun CodeBlock(text: String, color: Color) = Text(
    text,
    modifier = Modifier
        .fillMaxWidth()
        .clip(CodeShape)
        .background(AxelTheme.colors.codeBackground)
        .horizontalScroll(rememberScrollState())
        .padding(12.dp),
    style = AxelTheme.typography.code.copy(lineHeight = 19.sp),
    color = color,
    // softWrap=false + Ellipsis makes Compose force a single line ("{…"), so clip and cut lines ourselves.
    softWrap = false,
    overflow = TextOverflow.Clip,
)

@Composable
private fun CollapsibleCode(text: String) {
    val lineCount = remember(text) { text.lines().size }
    var expanded by rememberSaveable(text) { mutableStateOf(false) }
    val long = lineCount > COLLAPSED_LINES
    CodeBlock(
        if (long && !expanded) collapsedLines(text, COLLAPSED_LINES) else text,
        MaterialTheme.colorScheme.onSurface,
    )
    if (long) {
        TextButton(
            onClick = { expanded = !expanded },
            modifier = Modifier.testTag("result_toggle").defaultMinSize(minHeight = 44.dp),
        ) {
            Text(
                if (expanded) "Show less" else "Show all $lineCount lines",
                style = AxelTheme.typography.label.copy(fontSize = 14.sp, fontWeight = FontWeight.Medium),
                color = MaterialTheme.colorScheme.primary,
            )
        }
    }
}

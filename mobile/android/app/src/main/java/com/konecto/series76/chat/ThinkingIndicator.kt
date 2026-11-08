package com.konecto.series76.chat

import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.semantics
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.StartOffset
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.keyframes
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import com.konecto.series76.ui.axel.AxelAvatar
import com.konecto.series76.ui.axel.AxelState
import com.konecto.series76.ui.theme.AxelTheme

private const val DOT_CYCLE_MS = 1200
private const val DOT_STAGGER_MS = 150

@Composable
fun ThinkingRow(phase: ThinkingPhase, lang: String, modifier: Modifier = Modifier) {
    Row(
        // Announced when the phase changes (the description is the phase's first label), not on rotation.
        modifier.testTag("typing_indicator").semantics {
            liveRegion = LiveRegionMode.Polite
            contentDescription = phaseDescription(phase, lang)
        },
        verticalAlignment = Alignment.Bottom,
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        AxelAvatar(AxelState.THINKING, size = 28.dp)
        Surface(shape = AssistantShape, color = AxelTheme.colors.surfaceViolet) {
            Row(
                Modifier.padding(horizontal = 16.dp, vertical = 12.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) { repeat(3) { PulsingDot(it) } }
                StatusLabel(phase, lang)
            }
        }
    }
}

@Composable
private fun PulsingDot(index: Int) {
    val transition = rememberInfiniteTransition(label = "dot$index")
    val phase = transition.animateFloat(
        initialValue = 0f, targetValue = 1f,
        animationSpec = infiniteRepeatable(
            keyframes {
                durationMillis = DOT_CYCLE_MS
                0f at 0; 1f at (DOT_CYCLE_MS * 0.4f).toInt(); 0f at DOT_CYCLE_MS
            },
            RepeatMode.Restart, StartOffset(index * DOT_STAGGER_MS),
        ),
        label = "dotPhase",
    )
    val color = MaterialTheme.colorScheme.primary
    Box(
        Modifier
            .size(6.dp)
            .graphicsLayer {
                alpha = 0.25f + 0.75f * phase.value
                translationY = -3.dp.toPx() * phase.value
            }
            .background(color, CircleShape),
    )
}

@Composable
fun ErrorBanner(message: String, canRetry: Boolean, onRetry: () -> Unit) {
    val colors = AxelTheme.colors
    Surface(
        Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 4.dp).testTag("chat_error")
            .semantics { liveRegion = LiveRegionMode.Polite },
        shape = RoundedCornerShape(20.dp),
        color = colors.cautionContainer,
        border = BorderStroke(1.dp, colors.caution),
    ) {
        Row(
            Modifier.padding(start = 12.dp, end = 4.dp, top = 8.dp, bottom = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            AxelAvatar(AxelState.PROBLEM, size = 32.dp)
            Text(message, Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium)
            if (canRetry) TextButton(onClick = onRetry, modifier = Modifier.testTag("chat_retry")) { Text("Retry") }
        }
    }
}

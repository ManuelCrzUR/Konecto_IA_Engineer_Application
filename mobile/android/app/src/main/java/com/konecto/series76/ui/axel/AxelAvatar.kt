package com.konecto.series76.ui.axel

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import com.konecto.series76.ui.theme.AxelTheme
import com.konecto.series76.ui.theme.LocalAnimationsEnabled
import kotlinx.coroutines.delay
import kotlin.random.Random

/**
 * Axel, the assistant avatar. Animation phase (0..1) lives in an [Animatable] that is only read
 * inside the draw lambda, so frames redraw without recomposing.
 */
@Composable
fun AxelAvatar(
    state: AxelState,
    modifier: Modifier = Modifier,
    size: Dp = 32.dp,
    colors: AxelPalette = if (AxelTheme.colors.isDark) AxelPalette.dark else AxelPalette.light,
) {
    val animate = LocalAnimationsEnabled.current
    val phase = remember { Animatable(0f) }

    LaunchedEffect(state, animate) {
        phase.snapTo(0f)
        if (!animate) return@LaunchedEffect
        when (state) {
            AxelState.IDLE -> while (true) { // blink every ~4 s with jitter
                delay(Random.nextLong(3200, 4800))
                phase.snapTo(0f)
                phase.animateTo(1f, tween(320, easing = LinearEasing))
            }
            AxelState.THINKING -> phase.loop(1800)
            AxelState.READY -> phase.loop(1600)
            AxelState.PROBLEM -> Unit
        }
    }

    Canvas(
        modifier
            .size(size)
            .semantics { contentDescription = "Axel, ${state.name.lowercase()}" },
    ) {
        val t = phase.value
        val frame = when (state) {
            AxelState.IDLE -> AxelFrame(blink = blinkScale(t))
            AxelState.THINKING -> AxelFrame(knobDeg = knobAngle(t), glance = glanceOffset(t))
            AxelState.READY -> AxelFrame(bounce = bounceOffset(t))
            AxelState.PROBLEM -> AxelFrame()
        }
        drawAxel(state, colors, frame)
    }
}

private suspend fun Animatable<Float, *>.loop(durationMs: Int) =
    animateTo(1f, infiniteRepeatable(tween(durationMs, easing = LinearEasing), RepeatMode.Restart))

@Preview(name = "Axel dark", showBackground = true, backgroundColor = 0xFF0E0E0E)
@Composable
private fun AxelDarkPreview() = PreviewRow(AxelPalette.dark)

@Preview(name = "Axel light", showBackground = true, backgroundColor = 0xFFFAF8FC)
@Composable
private fun AxelLightPreview() = PreviewRow(AxelPalette.light)

@Composable
private fun PreviewRow(palette: AxelPalette) {
    Row {
        AxelState.entries.forEach { AxelAvatar(it, Modifier.padding(8.dp), 64.dp, palette) }
    }
}

package com.konecto.series76.chat

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.SizeTransform
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.animation.core.snap
import androidx.compose.animation.core.tween
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.platform.testTag
import com.konecto.series76.ui.theme.LocalAnimationsEnabled
import kotlinx.coroutines.delay

/** What the loading indicator is waiting for; the label changes with the phase. */
enum class ThinkingPhase { Transcribing, Waiting, Voice }

private const val ROTATE_MS = 1_800L
private const val FADE_MS = 180

/** Labels of [phase] in [lang] ("es" or anything else = English). Only Waiting has several (rotated in order). */
fun statusLabels(phase: ThinkingPhase, lang: String): List<String> {
    val es = lang == "es"
    return when (phase) {
        ThinkingPhase.Transcribing -> listOf(if (es) "Transcribiendo…" else "Transcribing…")
        ThinkingPhase.Voice -> listOf(if (es) "Generando voz…" else "Generating voice…")
        ThinkingPhase.Waiting -> if (es) {
            listOf("Pensando…", "Revisando el catálogo…", "Organizando la respuesta…")
        } else {
            listOf("Thinking…", "Checking the catalog…", "Organizing the answer…")
        }
    }
}

/**
 * The announced text of a phase: its first label. Rotating sub-labels share it, so a screen reader hears
 * the label only when the phase changes.
 */
fun phaseDescription(phase: ThinkingPhase, lang: String): String = statusLabels(phase, lang).first()

/**
 * Cross-fading status text. Only this composable recomposes when the label rotates; with animations
 * off the label switches instantly. Hidden from accessibility: the parent row announces the phase.
 */
@Composable
fun StatusLabel(phase: ThinkingPhase, lang: String, modifier: Modifier = Modifier) {
    val labels = remember(phase, lang) { statusLabels(phase, lang) }
    var index by remember(phase, lang) { mutableIntStateOf(0) }
    LaunchedEffect(phase, lang) {
        for (i in 1 until labels.size) {
            delay(ROTATE_MS)
            index = i
        }
    }
    val animated = LocalAnimationsEnabled.current
    val style = MaterialTheme.typography.bodyLarge
    AnimatedContent(
        targetState = labels[index],
        modifier = modifier.testTag("typing_label").clearAndSetSemantics {},
        transitionSpec = {
            if (animated) {
                (fadeIn(tween(FADE_MS)) togetherWith fadeOut(tween(FADE_MS))).using(SizeTransform(clip = false) { _, _ -> snap() })
            } else {
                (fadeIn(snap()) togetherWith fadeOut(snap())).using(SizeTransform(clip = false) { _, _ -> snap() })
            }
        },
        label = "statusLabel",
    ) { Text(it, style = style) }
}

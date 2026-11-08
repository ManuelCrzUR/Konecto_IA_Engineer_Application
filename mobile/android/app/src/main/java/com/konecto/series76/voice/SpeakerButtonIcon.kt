package com.konecto.series76.voice

import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.unit.dp
import androidx.compose.foundation.layout.size
import com.konecto.series76.ui.theme.LocalAnimationsEnabled

enum class SpeakerButtonState { Idle, Preparing, Reading }

/** Preparing wins: a message is Preparing until its first audio plays, then Reading, then Idle. */
fun voiceButtonState(key: String, speakingKey: String?, preparingKey: String?): SpeakerButtonState = when (key) {
    preparingKey -> SpeakerButtonState.Preparing
    speakingKey -> SpeakerButtonState.Reading
    else -> SpeakerButtonState.Idle
}

fun speakerContentDescription(state: SpeakerButtonState): String = when (state) {
    SpeakerButtonState.Idle -> "Read aloud"
    SpeakerButtonState.Preparing -> "Preparing voice"
    SpeakerButtonState.Reading -> "Stop reading"
}

/** Icon of the speaker button. While the voice is prepared the waves pulse (alpha and scale, draw phase only). */
@Composable
fun SpeakerButtonIcon(state: SpeakerButtonState) {
    val description = speakerContentDescription(state)
    if (state == SpeakerButtonState.Reading) {
        Icon(VoiceIcons.Stop, description, Modifier.size(20.dp))
        return
    }
    if (state == SpeakerButtonState.Idle || !LocalAnimationsEnabled.current) {
        Icon(VoiceIcons.VolumeUp, description, Modifier.size(20.dp))
        return
    }
    val pulse = rememberInfiniteTransition(label = "voicePulse").animateFloat(
        initialValue = 0f, targetValue = 1f,
        animationSpec = infiniteRepeatable(tween(700, easing = FastOutSlowInEasing), RepeatMode.Reverse),
        label = "voicePulsePhase",
    )
    Icon(
        VoiceIcons.VolumeUp, description,
        Modifier.size(20.dp).graphicsLayer {
            alpha = 0.4f + 0.6f * pulse.value
            val s = 0.9f + 0.2f * pulse.value
            scaleX = s; scaleY = s
        },
        tint = MaterialTheme.colorScheme.primary,
    )
}

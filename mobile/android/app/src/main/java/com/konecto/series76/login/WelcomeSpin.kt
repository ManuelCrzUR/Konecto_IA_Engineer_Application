package com.konecto.series76.login

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.tween
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.Stable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.setValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.graphicsLayer
import com.konecto.series76.ui.theme.LocalAnimationsEnabled
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.launch

/**
 * Login to chats transition. Input: [active] (sign-in succeeded) and the final [onFinished].
 * Sequence: form fades out (200 ms, FastOutSlowIn) while Axel spins 360 degrees with scale
 * 1.0 -> 1.15 -> 1.0 (700 ms, FastOutSlowIn), then Axel shrinks to 0.6 and fades out (300 ms),
 * then [onFinished] runs exactly once. Reduced motion (animator scale 0, via
 * [LocalAnimationsEnabled]) and a restored instance (rotation) skip straight to [onFinished].
 * Values are read only in graphicsLayer lambdas, so frames do not recompose.
 */
@Stable
class WelcomeSpin {
    internal val form = Animatable(1f)
    internal val rotation = Animatable(0f)
    internal val bump = Animatable(0f) // 0..1..0 drives the scale-up during the spin
    internal val exit = Animatable(0f) // 0 -> 1 shrink and fade

    /** Fade for the form widgets; apply to everything except the avatar. */
    fun Modifier.formFade(): Modifier = graphicsLayer { alpha = form.value }

    /** Spin, scale and exit for the avatar. */
    fun Modifier.avatarMotion(): Modifier = graphicsLayer {
        val s = (1f + 0.15f * bump.value) * (1f - 0.4f * exit.value)
        scaleX = s
        scaleY = s
        rotationZ = rotation.value
        alpha = 1f - exit.value
    }

    internal suspend fun play() = coroutineScope {
        val ease = FastOutSlowInEasing
        launch { form.animateTo(0f, tween(200, easing = ease)) }
        launch { rotation.animateTo(360f, tween(700, easing = ease)) }
        launch { bump.animateTo(1f, tween(350, easing = ease)); bump.animateTo(0f, tween(350, easing = ease)) }
    }.also { exit.animateTo(1f, tween(300, easing = FastOutSlowInEasing)) }
}

/** Runs the sequence once when [active] turns true; see the class contract. */
@Composable
fun rememberWelcomeSpin(active: Boolean, onFinished: () -> Unit): WelcomeSpin {
    val spin = remember { WelcomeSpin() }
    val animate = LocalAnimationsEnabled.current
    val finish by rememberUpdatedState(onFinished)
    var started by rememberSaveable { mutableStateOf(false) }
    LaunchedEffect(active) {
        if (!active) return@LaunchedEffect
        val replay = started // true after a configuration change: just finish
        started = true
        if (animate && !replay) spin.play()
        finish()
    }
    return spin
}

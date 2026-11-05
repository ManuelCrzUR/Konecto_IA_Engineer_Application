package com.konecto.series76.ui.theme

import androidx.compose.animation.EnterTransition
import androidx.compose.animation.ExitTransition
import androidx.compose.animation.core.CubicBezierEasing
import androidx.compose.animation.core.FastOutLinearInEasing
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.LinearOutSlowInEasing
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.scaleIn
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.runtime.staticCompositionLocalOf

/** Material 3 emphasized-decelerate style curve used by screen and message transitions. */
val Emphasized = CubicBezierEasing(0.05f, 0.7f, 0.1f, 1f)

/** False when the system animator duration scale is 0; read once in [Series76Theme]. */
val LocalAnimationsEnabled = staticCompositionLocalOf { true }

/** Navigation transition specs, defined once (Material 3 shared axis X and fade-through). */
object NavMotion {
    private const val SLIDE_MS = 400
    private const val FADE_IN_MS = 210
    private const val FADE_OUT_MS = 90
    private const val SCALE_MS = 300

    private fun slideIn(dir: Int) = slideInHorizontally(tween(SLIDE_MS, easing = FastOutSlowInEasing)) { dir * it / 4 }
    private fun slideOut(dir: Int) = slideOutHorizontally(tween(SLIDE_MS, easing = FastOutSlowInEasing)) { dir * it / 4 }
    private fun axisFadeIn() = fadeIn(tween(FADE_IN_MS, FADE_OUT_MS, LinearOutSlowInEasing))
    private fun axisFadeOut() = fadeOut(tween(FADE_OUT_MS, easing = FastOutLinearInEasing))

    fun forwardIn(): EnterTransition = slideIn(1) + axisFadeIn()
    fun forwardOut(): ExitTransition = slideOut(-1) + axisFadeOut()
    fun backIn(): EnterTransition = slideIn(-1) + axisFadeIn()
    fun backOut(): ExitTransition = slideOut(1) + axisFadeOut()

    fun fadeThroughIn(): EnterTransition =
        fadeIn(tween(FADE_IN_MS, FADE_OUT_MS)) +
            scaleIn(tween(SCALE_MS, easing = FastOutSlowInEasing), initialScale = 0.92f)
    fun fadeThroughOut(): ExitTransition = fadeOut(tween(FADE_OUT_MS))

    fun splashFade(): EnterTransition = fadeIn(tween(300))
    fun splashFadeOut(): ExitTransition = fadeOut(tween(300))
}

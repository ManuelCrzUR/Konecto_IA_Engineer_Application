package com.konecto.series76.ui.theme

import android.app.Activity
import android.provider.Settings
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.snap
import androidx.compose.animation.core.tween
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowCompat

enum class ThemeMode { SYSTEM, LIGHT, DARK }

/** Resolves SYSTEM against the device setting; the result is always dark or light. */
@Composable
fun ThemeMode.isDark(): Boolean = when (this) {
    ThemeMode.SYSTEM -> isSystemInDarkTheme()
    ThemeMode.LIGHT -> false
    ThemeMode.DARK -> true
}

/**
 * Dynamic color is intentionally off: the Axel palette is fixed (DESIGN.md section 2).
 * A single 0..1 fraction is animated and every token is blended from it, so a theme
 * switch is one 300 ms cross-fade instead of a one-frame cut.
 */
@Composable
fun Series76Theme(themeMode: ThemeMode = ThemeMode.DARK, content: @Composable () -> Unit) {
    val dark = themeMode.isDark()
    val resolver = LocalContext.current.contentResolver
    val animations = remember {
        Settings.Global.getFloat(resolver, Settings.Global.ANIMATOR_DURATION_SCALE, 1f) != 0f
    }
    val fraction by animateFloatAsState(
        targetValue = if (dark) 1f else 0f,
        animationSpec = if (animations) tween(300, easing = FastOutSlowInEasing) else snap(),
        label = "themeFraction",
    )
    SystemBarIcons(fraction)
    CompositionLocalProvider(
        LocalAxelColors provides blendAxelColors(fraction, dark),
        LocalAnimationsEnabled provides animations,
    ) {
        MaterialTheme(colorScheme = blendScheme(fraction, dark), typography = Series76Typography) {
            Surface(color = MaterialTheme.colorScheme.background, content = content)
        }
    }
}

/** Keeps status/navigation bar icon contrast in step with the theme (idempotent). */
@Composable
private fun SystemBarIcons(darkFraction: Float) {
    val view = LocalView.current
    if (view.isInEditMode) return
    SideEffect {
        val window = (view.context as? Activity)?.window ?: return@SideEffect
        val controller = WindowCompat.getInsetsController(window, view)
        controller.isAppearanceLightStatusBars = darkFraction < 0.5f
        controller.isAppearanceLightNavigationBars = darkFraction < 0.5f
    }
}

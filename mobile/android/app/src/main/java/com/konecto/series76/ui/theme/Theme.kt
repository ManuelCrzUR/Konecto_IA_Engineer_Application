package com.konecto.series76.ui.theme

import android.provider.Settings
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.remember
import androidx.compose.ui.platform.LocalContext

enum class ThemeMode { SYSTEM, LIGHT, DARK }

/** Resolves SYSTEM against the device setting; the result is always dark or light. */
@Composable
fun ThemeMode.isDark(): Boolean = when (this) {
    ThemeMode.SYSTEM -> isSystemInDarkTheme()
    ThemeMode.LIGHT -> false
    ThemeMode.DARK -> true
}

/** Dynamic color is intentionally off: the Axel palette is fixed (DESIGN.md section 2). */
@Composable
fun Series76Theme(themeMode: ThemeMode = ThemeMode.DARK, content: @Composable () -> Unit) {
    val dark = themeMode.isDark()
    val resolver = LocalContext.current.contentResolver
    val animations = remember {
        Settings.Global.getFloat(resolver, Settings.Global.ANIMATOR_DURATION_SCALE, 1f) != 0f
    }
    CompositionLocalProvider(
        LocalAxelColors provides if (dark) DarkAxelColors else LightAxelColors,
        LocalAnimationsEnabled provides animations,
    ) {
        MaterialTheme(
            colorScheme = if (dark) DarkScheme else LightScheme,
            typography = Series76Typography,
        ) {
            Surface(color = MaterialTheme.colorScheme.background, content = content)
        }
    }
}

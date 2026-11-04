package com.konecto.series76.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

// Industrial look: neutral greys, one steel-blue accent. Dynamic color is intentionally off.
private val Accent = Color(0xFF1F5F8B)
private val AccentDark = Color(0xFF8CC4EC)

private val LightColors = lightColorScheme(
    primary = Accent,
    onPrimary = Color.White,
    primaryContainer = Color(0xFFD6E8F5),
    onPrimaryContainer = Color(0xFF0B2A3F),
    secondary = Color(0xFF55606A),
    background = Color(0xFFF4F5F6),
    onBackground = Color(0xFF1B1D1F),
    surface = Color(0xFFFFFFFF),
    onSurface = Color(0xFF1B1D1F),
    surfaceVariant = Color(0xFFE6E8EA),
    onSurfaceVariant = Color(0xFF454B50),
    outline = Color(0xFF8A9096),
    error = Color(0xFFB3261E),
)

private val DarkColors = darkColorScheme(
    primary = AccentDark,
    onPrimary = Color(0xFF06283D),
    primaryContainer = Color(0xFF184A6B),
    onPrimaryContainer = Color(0xFFD6E8F5),
    secondary = Color(0xFFB4BEC7),
    background = Color(0xFF121415),
    onBackground = Color(0xFFE3E5E7),
    surface = Color(0xFF1B1E20),
    onSurface = Color(0xFFE3E5E7),
    surfaceVariant = Color(0xFF2A2E31),
    onSurfaceVariant = Color(0xFFC2C7CB),
    outline = Color(0xFF8A9096),
    error = Color(0xFFF2B8B5),
)

@Composable
fun Series76Theme(darkTheme: Boolean = isSystemInDarkTheme(), content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = if (darkTheme) DarkColors else LightColors) {
        Surface(color = MaterialTheme.colorScheme.background, content = content)
    }
}

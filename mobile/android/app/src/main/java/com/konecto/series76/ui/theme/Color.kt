package com.konecto.series76.ui.theme

import androidx.compose.material3.ColorScheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.ReadOnlyComposable
import androidx.compose.runtime.compositionLocalOf
import androidx.compose.ui.graphics.Color

/** Tokens from DESIGN.md section 2 that Material 3 has no slot for. */
data class AxelColors(
    val textTertiary: Color,
    val caution: Color,
    val cautionContainer: Color,
    val codeBackground: Color,
    val accentText: Color,
    val surfaceViolet: Color,
    val divider: Color,
    /** Shadow color of the dark glow; fully transparent in light (alpha 0 keeps the tween clean). */
    val glow: Color,
    /** Header band: background in dark, white surface in light. */
    val headerBand: Color,
    /** Bottom divider of the header band; transparent in light, where the band is a raised surface. */
    val headerDivider: Color,
    /** Outline colour of plain cards (consumers draw it as 1 dp): transparent in dark. */
    val cardBorder: Color,
    /** Target theme flag (not animated). */
    val isDark: Boolean,
    /** Animated blend: 0 = light palette, 1 = dark palette. */
    val darkFraction: Float = if (isDark) 1f else 0f,
)

val DarkAxelColors = AxelColors(
    textTertiary = Color(0xFF8A8A8A),
    caution = Color(0xFFFFB86B),
    cautionContainer = Color(0xFF1D1D1D),
    codeBackground = Color(0xFF141414),
    accentText = Color(0xFFD0ACE5),
    surfaceViolet = Color(0xFF20152A),
    divider = Color(0xFF2A2A2A),
    glow = Color(0xFF412C64),
    headerBand = Color(0xFF0E0E0E),
    headerDivider = Color(0xFF2A2A2A),
    cardBorder = Color(0x00E7E2EE),
    isDark = true,
)

val LightAxelColors = AxelColors(
    textTertiary = Color(0xFF6E6878),
    caution = Color(0xFFA15C00),
    cautionContainer = Color(0xFFFFF7EC),
    codeBackground = Color(0xFFF6F3FA),
    accentText = Color(0xFF6A3FA0),
    surfaceViolet = Color(0xFFF3EAFE),
    divider = Color(0xFFE7E2EE),
    glow = Color(0x00412C64),
    headerBand = Color(0xFFFFFFFF),
    headerDivider = Color(0x002A2A2A),
    cardBorder = Color(0xFFE7E2EE),
    isDark = false,
)

val DarkScheme: ColorScheme = darkColorScheme(
    primary = Color(0xFFBD7BFF),
    onPrimary = Color(0xFF0E0E0E),
    background = Color(0xFF0E0E0E),
    onBackground = Color(0xFFFFFFFF),
    surface = Color(0xFF1D1D1D),
    onSurface = Color(0xFFFFFFFF),
    onSurfaceVariant = Color(0xFFCCCCCC),
    surfaceContainer = DarkAxelColors.surfaceViolet,
    outline = DarkAxelColors.divider,
    outlineVariant = DarkAxelColors.divider,
    error = DarkAxelColors.caution,
)

val LightScheme: ColorScheme = lightColorScheme(
    primary = Color(0xFF7B2CBF),
    onPrimary = Color(0xFFFFFFFF),
    background = Color(0xFFFAF8FC),
    onBackground = Color(0xFF16121C),
    surface = Color(0xFFFFFFFF),
    onSurface = Color(0xFF16121C),
    onSurfaceVariant = Color(0xFF4A4458),
    surfaceContainer = LightAxelColors.surfaceViolet,
    outline = LightAxelColors.divider,
    outlineVariant = LightAxelColors.divider,
    error = LightAxelColors.caution,
)

val LocalAxelColors = compositionLocalOf { DarkAxelColors }

object AxelTheme {
    val colors: AxelColors
        @Composable @ReadOnlyComposable get() = LocalAxelColors.current
    val typography: AxelTypography get() = DefaultAxelTypography
}

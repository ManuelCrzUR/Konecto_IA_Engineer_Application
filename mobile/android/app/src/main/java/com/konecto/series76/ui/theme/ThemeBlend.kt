package com.konecto.series76.ui.theme

import androidx.compose.material3.ColorScheme
import androidx.compose.ui.graphics.lerp

/** Pure colour blending for the theme cross-fade; fraction 0 = light, 1 = dark. */
fun blendAxelColors(f: Float, dark: Boolean): AxelColors {
    val l = LightAxelColors
    val d = DarkAxelColors
    return when {
        f <= 0f && !dark -> l
        f >= 1f && dark -> d
        else -> AxelColors(
            textTertiary = lerp(l.textTertiary, d.textTertiary, f),
            caution = lerp(l.caution, d.caution, f),
            cautionContainer = lerp(l.cautionContainer, d.cautionContainer, f),
            codeBackground = lerp(l.codeBackground, d.codeBackground, f),
            accentText = lerp(l.accentText, d.accentText, f),
            surfaceViolet = lerp(l.surfaceViolet, d.surfaceViolet, f),
            divider = lerp(l.divider, d.divider, f),
            glow = lerp(l.glow, d.glow, f),
            headerBand = lerp(l.headerBand, d.headerBand, f),
            headerDivider = lerp(l.headerDivider, d.headerDivider, f),
            cardBorder = lerp(l.cardBorder, d.cardBorder, f),
            isDark = dark,
            darkFraction = f,
        )
    }
}

/** Blends every ColorScheme token (Material 3 1.4), so components never mix palettes mid cross-fade. */
fun blendScheme(f: Float, dark: Boolean): ColorScheme {
    val l = LightScheme
    val d = DarkScheme
    if (f <= 0f) return l
    if (f >= 1f) return d
    return l.copy(
        primary = lerp(l.primary, d.primary, f),
        onPrimary = lerp(l.onPrimary, d.onPrimary, f),
        primaryContainer = lerp(l.primaryContainer, d.primaryContainer, f),
        onPrimaryContainer = lerp(l.onPrimaryContainer, d.onPrimaryContainer, f),
        inversePrimary = lerp(l.inversePrimary, d.inversePrimary, f),
        secondary = lerp(l.secondary, d.secondary, f),
        onSecondary = lerp(l.onSecondary, d.onSecondary, f),
        secondaryContainer = lerp(l.secondaryContainer, d.secondaryContainer, f),
        onSecondaryContainer = lerp(l.onSecondaryContainer, d.onSecondaryContainer, f),
        tertiary = lerp(l.tertiary, d.tertiary, f),
        onTertiary = lerp(l.onTertiary, d.onTertiary, f),
        tertiaryContainer = lerp(l.tertiaryContainer, d.tertiaryContainer, f),
        onTertiaryContainer = lerp(l.onTertiaryContainer, d.onTertiaryContainer, f),
        background = lerp(l.background, d.background, f),
        onBackground = lerp(l.onBackground, d.onBackground, f),
        surface = lerp(l.surface, d.surface, f),
        onSurface = lerp(l.onSurface, d.onSurface, f),
        surfaceVariant = lerp(l.surfaceVariant, d.surfaceVariant, f),
        onSurfaceVariant = lerp(l.onSurfaceVariant, d.onSurfaceVariant, f),
        surfaceTint = lerp(l.surfaceTint, d.surfaceTint, f),
        inverseSurface = lerp(l.inverseSurface, d.inverseSurface, f),
        inverseOnSurface = lerp(l.inverseOnSurface, d.inverseOnSurface, f),
        error = lerp(l.error, d.error, f),
        onError = lerp(l.onError, d.onError, f),
        errorContainer = lerp(l.errorContainer, d.errorContainer, f),
        onErrorContainer = lerp(l.onErrorContainer, d.onErrorContainer, f),
        outline = lerp(l.outline, d.outline, f),
        outlineVariant = lerp(l.outlineVariant, d.outlineVariant, f),
        scrim = lerp(l.scrim, d.scrim, f),
        surfaceBright = lerp(l.surfaceBright, d.surfaceBright, f),
        surfaceDim = lerp(l.surfaceDim, d.surfaceDim, f),
        surfaceContainer = lerp(l.surfaceContainer, d.surfaceContainer, f),
        surfaceContainerHigh = lerp(l.surfaceContainerHigh, d.surfaceContainerHigh, f),
        surfaceContainerHighest = lerp(l.surfaceContainerHighest, d.surfaceContainerHighest, f),
        surfaceContainerLow = lerp(l.surfaceContainerLow, d.surfaceContainerLow, f),
        surfaceContainerLowest = lerp(l.surfaceContainerLowest, d.surfaceContainerLowest, f),
        primaryFixed = lerp(l.primaryFixed, d.primaryFixed, f),
        primaryFixedDim = lerp(l.primaryFixedDim, d.primaryFixedDim, f),
        onPrimaryFixed = lerp(l.onPrimaryFixed, d.onPrimaryFixed, f),
        onPrimaryFixedVariant = lerp(l.onPrimaryFixedVariant, d.onPrimaryFixedVariant, f),
        secondaryFixed = lerp(l.secondaryFixed, d.secondaryFixed, f),
        secondaryFixedDim = lerp(l.secondaryFixedDim, d.secondaryFixedDim, f),
        onSecondaryFixed = lerp(l.onSecondaryFixed, d.onSecondaryFixed, f),
        onSecondaryFixedVariant = lerp(l.onSecondaryFixedVariant, d.onSecondaryFixedVariant, f),
        tertiaryFixed = lerp(l.tertiaryFixed, d.tertiaryFixed, f),
        tertiaryFixedDim = lerp(l.tertiaryFixedDim, d.tertiaryFixedDim, f),
        onTertiaryFixed = lerp(l.onTertiaryFixed, d.onTertiaryFixed, f),
        onTertiaryFixedVariant = lerp(l.onTertiaryFixedVariant, d.onTertiaryFixedVariant, f),
    )
}

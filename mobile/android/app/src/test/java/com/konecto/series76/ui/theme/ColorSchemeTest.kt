package com.konecto.series76.ui.theme

import androidx.compose.ui.graphics.Color
import org.junit.Assert.assertEquals
import org.junit.Test

class ColorSchemeTest {
    @Test fun darkMatchesDesignTokens() {
        assertEquals(Color(0xFFBD7BFF), DarkScheme.primary)
        assertEquals(Color(0xFF0E0E0E), DarkScheme.background)
        assertEquals(Color(0xFF1D1D1D), DarkScheme.surface)
        assertEquals(Color(0xFF20152A), DarkScheme.surfaceContainer)
    }

    @Test fun lightMatchesDesignTokens() {
        assertEquals(Color(0xFF7B2CBF), LightScheme.primary)
        assertEquals(Color(0xFFFAF8FC), LightScheme.background)
        assertEquals(Color(0xFFFFFFFF), LightScheme.surface)
        assertEquals(Color(0xFFF3EAFE), LightScheme.surfaceContainer)
    }
}

class ThemeBlendTest {
    @Test fun endpointsReturnExactPalettes() {
        assertEquals(DarkAxelColors, blendAxelColors(1f, true))
        assertEquals(LightAxelColors, blendAxelColors(0f, false))
        assertEquals(DarkScheme.primary, blendScheme(1f, true).primary)
    }

    @Test fun mismatchedEndpointsStillReportTargetIsDark() {
        assertEquals(true, blendAxelColors(0f, true).isDark)
        assertEquals(false, blendAxelColors(1f, false).isDark)
    }

    @Test fun midpointIsBetweenAndKeepsTargetFlag() {
        val mid = blendAxelColors(0.5f, true)
        assertEquals(true, mid.isDark)
        assertEquals(0.5f, mid.darkFraction)
        assert(mid.headerBand.red in 0.1f..0.95f)
        assert(blendScheme(0.5f, false).background != LightScheme.background)
    }

    @Test fun endpointsAreTheExactSchemeObjects() {
        assert(blendScheme(0f, false) === LightScheme)
        assert(blendScheme(1f, true) === DarkScheme)
    }

    @Test fun midpointBlendsTokensBeyondTheCoreOnes() {
        val mid = blendScheme(0.5f, true)
        assertEquals(androidx.compose.ui.graphics.lerp(LightScheme.surfaceContainerHigh, DarkScheme.surfaceContainerHigh, 0.5f), mid.surfaceContainerHigh)
        assertEquals(androidx.compose.ui.graphics.lerp(LightScheme.inverseSurface, DarkScheme.inverseSurface, 0.5f), mid.inverseSurface)
        assertEquals(androidx.compose.ui.graphics.lerp(LightScheme.scrim, DarkScheme.scrim, 0.5f), mid.scrim)
    }

    @Test fun structuralTokensAreColors() {
        assertEquals(0f, DarkAxelColors.cardBorder.alpha)
        assertEquals(0f, LightAxelColors.headerDivider.alpha)
    }
}

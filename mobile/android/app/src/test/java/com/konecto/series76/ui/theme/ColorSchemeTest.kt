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

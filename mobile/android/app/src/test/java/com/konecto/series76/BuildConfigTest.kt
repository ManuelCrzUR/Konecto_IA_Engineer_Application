package com.konecto.series76

import org.junit.Assert.assertTrue
import org.junit.Test

class BuildConfigTest {
    @Test
    fun baseUrlEndsWithSlash() {
        assertTrue(BuildConfig.API_BASE_URL.endsWith("/"))
    }
}

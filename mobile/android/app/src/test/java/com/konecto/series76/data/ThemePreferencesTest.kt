package com.konecto.series76.data

import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import com.konecto.series76.ui.theme.ThemeMode
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

class ThemePreferencesTest {
    @get:Rule val tmp = TemporaryFolder()

    private fun store() = PreferenceDataStoreFactory.create(
        scope = CoroutineScope(UnconfinedTestDispatcher() + Job()),
        produceFile = { tmp.newFile("settings.preferences_pb").also { it.delete() } },
    )

    @Test fun defaultIsDark() = runTest {
        val prefs = ThemePreferences(store())
        assertEquals(ThemeMode.DARK, prefs.themeMode.first())
    }

    @Test fun roundTripsEveryMode() = runTest {
        val prefs = ThemePreferences(store())
        for (mode in ThemeMode.entries) {
            prefs.setThemeMode(mode)
            assertEquals(mode, prefs.themeMode.first())
        }
    }

    @Test fun unknownValueFallsBackToDark() = runTest {
        val store = store()
        store.edit { it[stringPreferencesKey("theme_mode")] = "SEPIA" }
        assertEquals(ThemeMode.DARK, ThemePreferences(store).themeMode.first())
    }
}

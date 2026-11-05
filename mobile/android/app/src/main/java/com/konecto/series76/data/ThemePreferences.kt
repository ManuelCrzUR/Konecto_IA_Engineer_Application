package com.konecto.series76.data

import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import com.konecto.series76.ui.theme.ThemeMode
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

/** Persists the user's theme choice. Unknown or missing values fall back to DARK. */
class ThemePreferences(private val store: DataStore<Preferences>) {
    val themeMode: Flow<ThemeMode> = store.data.map { prefs ->
        ThemeMode.entries.firstOrNull { it.name == prefs[KEY] } ?: ThemeMode.DARK
    }

    suspend fun setThemeMode(mode: ThemeMode) {
        store.edit { it[KEY] = mode.name }
    }

    private companion object {
        val KEY = stringPreferencesKey("theme_mode")
    }
}

package com.konecto.series76.conversations

import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import com.konecto.series76.data.ThemePreferences
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import java.io.File

/** Real DataStore on a throw-away file, so tests exercise the actual persistence path. */
internal fun testThemePreferences(): ThemePreferences {
    val dir = kotlin.io.path.createTempDirectory("theme").toFile().apply { deleteOnExit() }
    return ThemePreferences(
        PreferenceDataStoreFactory.create(
            scope = CoroutineScope(UnconfinedTestDispatcher() + Job()),
            produceFile = { File(dir, "settings.preferences_pb") },
        ),
    )
}

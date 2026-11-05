package com.konecto.series76

import android.app.Application
import android.content.Context
import androidx.datastore.preferences.preferencesDataStore
import com.konecto.series76.data.ApiClient
import com.konecto.series76.data.AssistantRepository
import com.konecto.series76.data.Repository
import com.konecto.series76.data.ThemePreferences

/**
 * Manual DI root (no Hilt, KISS). Screens get the repository through
 * `(LocalContext.current.applicationContext as App).container.repository`
 * and pass it to their ViewModel factory; tests build ViewModels with a fake.
 */
private val Context.settingsStore by preferencesDataStore(name = "settings")

class AppContainer(
    context: Context,
    val baseUrl: String = BuildConfig.API_BASE_URL,
) {
    val themePreferences: ThemePreferences by lazy { ThemePreferences(context.settingsStore) }
    val repository: AssistantRepository by lazy { Repository(ApiClient.create(baseUrl)) }
}

class App : Application() {
    lateinit var container: AppContainer
        private set

    override fun onCreate() {
        super.onCreate()
        container = AppContainer(this)
    }
}

package com.konecto.series76

import android.app.Application
import com.konecto.series76.data.ApiClient
import com.konecto.series76.data.AssistantRepository
import com.konecto.series76.data.Repository

/**
 * Manual DI root (no Hilt, KISS). Screens get the repository through
 * `(LocalContext.current.applicationContext as App).container.repository`
 * and pass it to their ViewModel factory; tests build ViewModels with a fake.
 */
class AppContainer(val baseUrl: String = BuildConfig.API_BASE_URL) {
    val repository: AssistantRepository by lazy { Repository(ApiClient.create(baseUrl)) }
}

class App : Application() {
    lateinit var container: AppContainer
        private set

    override fun onCreate() {
        super.onCreate()
        container = AppContainer()
    }
}

package com.konecto.series76

import android.app.Application
import android.content.Context
import androidx.datastore.preferences.preferencesDataStore
import com.konecto.series76.data.ApiClient
import com.konecto.series76.data.AssistantRepository
import com.konecto.series76.data.AuthInterceptor
import com.konecto.series76.data.AuthRepository
import com.konecto.series76.data.HttpAuthRepository
import com.konecto.series76.data.Repository
import com.konecto.series76.data.SessionStore
import com.konecto.series76.data.ThemePreferences
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

/**
 * Manual DI root (no Hilt, KISS). Screens get the repository through
 * `(LocalContext.current.applicationContext as App).container.repository`
 * and pass it to their ViewModel factory; tests build ViewModels with a fake.
 */
private val Context.settingsStore by preferencesDataStore(name = "settings")
private val Context.authStore by preferencesDataStore(name = "auth")

class AppContainer(
    context: Context,
    val baseUrl: String = BuildConfig.API_BASE_URL,
) {
    val themePreferences: ThemePreferences by lazy { ThemePreferences(context.settingsStore) }
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)

    val sessionStore: SessionStore by lazy { SessionStore(context.authStore) }

    // One shared API: the interceptor adds the token and clears the session on any 401 (except login).
    private val api by lazy {
        val auth = AuthInterceptor(
            tokenProvider = { sessionStore.token() },
            // Only when signed in: dedupes parallel 401s and skips a 401 after sign-out.
            onUnauthorized = { if (sessionStore.current != null) scope.launch { sessionStore.clear() } },
        )
        ApiClient.create(baseUrl, interceptor = auth)
    }

    val repository: AssistantRepository by lazy { Repository(api) }
    val authRepository: AuthRepository by lazy { HttpAuthRepository(api, sessionStore) }
}

class App : Application() {
    lateinit var container: AppContainer
        private set

    override fun onCreate() {
        super.onCreate()
        container = AppContainer(this)
    }
}

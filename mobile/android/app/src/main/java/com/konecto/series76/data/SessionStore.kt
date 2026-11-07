package com.konecto.series76.data

import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.runBlocking

/**
 * Persists the signed-in session. [current] mirrors it in memory so the OkHttp interceptor
 * never blocks on DataStore; it is set by [load], [save] and [clear].
 */
class SessionStore(private val store: DataStore<Preferences>) {
    @Volatile
    var current: AuthSession? = null
        private set

    /** True once [current] reflects the store (after [load], [save] or [clear]). */
    @Volatile
    private var primed = false

    val session: Flow<AuthSession?> = store.data.map { read(it) }

    /** Reads the stored session once and primes [current]. */
    suspend fun load(): AuthSession? = read(store.data.first()).also { current = it; primed = true }

    /**
     * The token for the OkHttp interceptor (runs on OkHttp's threads, never the main thread).
     * After process death Android restores the screen without the splash, so nothing has
     * called [load] yet: read the store once here instead of sending requests without a token.
     */
    fun token(): String? {
        if (!primed) runBlocking { load() }
        return current?.token
    }

    suspend fun save(s: AuthSession) {
        store.edit {
            it[TOKEN] = s.token
            it[EMAIL] = s.email
            it[ROLE] = s.role
        }
        current = s
        primed = true
    }

    suspend fun clear() {
        current = null // before the write, so requests stop carrying the token immediately
        primed = true // and token() must not reload the old one while the write is pending
        store.edit { it.clear() }
    }

    private fun read(p: Preferences): AuthSession? {
        val token = p[TOKEN] ?: return null
        return AuthSession(token, p[EMAIL].orEmpty(), p[ROLE] ?: "user")
    }

    private companion object {
        val TOKEN = stringPreferencesKey("token")
        val EMAIL = stringPreferencesKey("email")
        val ROLE = stringPreferencesKey("role")
    }
}

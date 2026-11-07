package com.konecto.series76.data

import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map

/**
 * Persists the signed-in session. [current] mirrors it in memory so the OkHttp interceptor
 * never blocks on DataStore; it is set by [load], [save] and [clear].
 */
class SessionStore(private val store: DataStore<Preferences>) {
    @Volatile
    var current: AuthSession? = null
        private set

    val session: Flow<AuthSession?> = store.data.map { read(it) }

    /** Reads the stored session once and primes [current]. */
    suspend fun load(): AuthSession? = read(store.data.first()).also { current = it }

    suspend fun save(s: AuthSession) {
        store.edit {
            it[TOKEN] = s.token
            it[EMAIL] = s.email
            it[ROLE] = s.role
        }
        current = s
    }

    suspend fun clear() {
        current = null // before the write, so requests stop carrying the token immediately
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

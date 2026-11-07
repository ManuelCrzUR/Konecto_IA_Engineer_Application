package com.konecto.series76.data

import kotlinx.coroutines.flow.Flow

/** Sign-in state. [HttpAuthRepository] is the real one, tests use fakes. */
interface AuthRepository {
    /** The stored session; emits null after sign-out or when the server rejects the token. */
    val session: Flow<AuthSession?>

    /** Reads the stored session once (primes the in-memory token for the interceptor). */
    suspend fun restore(): AuthSession?

    suspend fun login(email: String, password: String): ApiResult<AuthSession>

    /** Best-effort server call, then always clears the local session. */
    suspend fun logout()
}

class HttpAuthRepository(
    private val api: ApiService,
    private val store: SessionStore,
) : AuthRepository {

    override val session: Flow<AuthSession?> = store.session

    override suspend fun restore(): AuthSession? = store.load()

    override suspend fun login(email: String, password: String): ApiResult<AuthSession> =
        when (val r = apiCall { api.login(LoginRequest(email, password)) }) {
            is ApiResult.Success -> {
                val s = AuthSession(r.value.token, r.value.user.email, r.value.user.role)
                store.save(s)
                ApiResult.Success(s)
            }
            is ApiResult.Failure -> if ((r.kind as? FailureKind.Server)?.status == 401) {
                ApiResult.Failure(FailureKind.Server(401, "invalid_credentials"), "Wrong email or password")
            } else {
                r
            }
        }

    override suspend fun logout() {
        apiCall { api.logout() } // result ignored: the local session is cleared either way
        store.clear()
    }
}

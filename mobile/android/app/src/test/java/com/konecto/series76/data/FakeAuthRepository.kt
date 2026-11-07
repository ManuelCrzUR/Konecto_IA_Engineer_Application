package com.konecto.series76.data

import kotlinx.coroutines.flow.MutableStateFlow

/** Test fake: [onLogin] decides the result; [stored] is what restore() returns. */
class FakeAuthRepository(
    stored: AuthSession? = null,
    var onLogin: suspend (String, String) -> ApiResult<AuthSession> = { e, _ -> ApiResult.Success(AuthSession("t", e, "user")) },
) : AuthRepository {
    private val state = MutableStateFlow(stored)
    var loginCalls = 0
    override val session = state
    override suspend fun restore(): AuthSession? = state.value
    override suspend fun login(email: String, password: String): ApiResult<AuthSession> {
        loginCalls++
        return onLogin(email, password).also { if (it is ApiResult.Success) state.value = it.value }
    }
    override suspend fun logout() { state.value = null }
}

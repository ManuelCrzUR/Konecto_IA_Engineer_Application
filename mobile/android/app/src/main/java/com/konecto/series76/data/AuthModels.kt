package com.konecto.series76.data

import kotlinx.serialization.Serializable

@Serializable
data class LoginRequest(val email: String, val password: String)

@Serializable
data class UserOut(val email: String, val role: String)

@Serializable
data class LoginResponse(val token: String, val user: UserOut)

/** The signed-in user as kept on the device. */
data class AuthSession(val token: String, val email: String, val role: String) {
    val isDeveloper: Boolean get() = role == "developer"
}

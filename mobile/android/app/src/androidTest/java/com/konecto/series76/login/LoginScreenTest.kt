package com.konecto.series76.login

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsEnabled
import androidx.compose.ui.test.assertIsNotEnabled
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performTextInput
import com.konecto.series76.data.ApiResult
import com.konecto.series76.data.AuthRepository
import com.konecto.series76.data.AuthSession
import com.konecto.series76.data.FailureKind
import com.konecto.series76.ui.theme.Series76Theme
import com.konecto.series76.ui.theme.ThemeMode
import kotlinx.coroutines.flow.flowOf
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test

class LoginScreenTest {
    @get:Rule val rule = createComposeRule()

    private class FakeAuth(val result: ApiResult<AuthSession>) : AuthRepository {
        override val session = flowOf<AuthSession?>(null)
        override suspend fun restore(): AuthSession? = null
        override suspend fun login(email: String, password: String) = result
        override suspend fun logout() {}
    }

    private var loggedIn = 0

    private fun show(result: ApiResult<AuthSession>) {
        val vm = LoginViewModel(FakeAuth(result)) // built outside composition (lint: ViewModelConstructorInComposable)
        rule.setContent { Series76Theme(ThemeMode.DARK) { LoginScreen(onLoggedIn = { loggedIn++ }, viewModel = vm) } }
    }

    @Test fun submitIsDisabledWhenBlank() {
        show(ApiResult.Failure(FailureKind.Network, "x"))
        rule.onNodeWithTag("login_submit").assertIsNotEnabled()
        rule.onNodeWithTag("login_email").performTextInput("ana@konecto.test")
        rule.onNodeWithTag("login_submit").assertIsNotEnabled()
        rule.onNodeWithTag("login_password").performTextInput("pw")
        rule.onNodeWithTag("login_submit").assertIsEnabled()
    }

    @Test fun showsErrorAfterFailedSignIn() {
        show(ApiResult.Failure(FailureKind.Server(401, "invalid_credentials"), "Wrong email or password"))
        rule.onNodeWithTag("login_email").performTextInput("ana@konecto.test")
        rule.onNodeWithTag("login_password").performTextInput("bad")
        rule.onNodeWithTag("login_submit").performClick()
        rule.onNodeWithTag("login_error").assertIsDisplayed()
    }

    @Test fun navigatesOnceAfterWelcomeAnimation() {
        show(ApiResult.Success(AuthSession("tok", "ana@konecto.test", "user")))
        rule.mainClock.autoAdvance = false
        rule.onNodeWithTag("login_email").performTextInput("ana@konecto.test")
        rule.onNodeWithTag("login_password").performTextInput("pw")
        rule.onNodeWithTag("login_submit").performClick()
        // viewModelScope runs on the real main dispatcher: give it real time, advance the test clock in small steps.
        var tries = 0
        while (tries++ < 50 && runCatching { rule.onNodeWithTag("login_submit").assertIsNotEnabled() }.isFailure) {
            Thread.sleep(50)
            rule.mainClock.advanceTimeBy(16)
        }
        rule.onNodeWithTag("login_submit").assertIsNotEnabled() // no double submit while animating
        assertEquals(0, loggedIn)
        rule.mainClock.advanceTimeBy(2_000)
        rule.waitForIdle()
        assertEquals(1, loggedIn)
    }
}

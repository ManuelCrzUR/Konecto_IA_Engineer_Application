package com.konecto.series76.splash

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import com.konecto.series76.data.ApiResult
import com.konecto.series76.data.AuthRepository
import com.konecto.series76.data.AuthSession
import kotlinx.coroutines.flow.flowOf
import com.konecto.series76.data.StubRepository
import com.konecto.series76.data.ConversationResponse
import com.konecto.series76.data.MessageOut
import com.konecto.series76.data.SessionOut
import com.konecto.series76.ui.theme.Series76Theme
import com.konecto.series76.ui.theme.ThemeMode
import org.junit.Rule
import org.junit.Test

class SplashScreenTest {
    @get:Rule val rule = createComposeRule()

    private val noSession = object : AuthRepository {
        override val session = flowOf<AuthSession?>(null)
        override suspend fun restore(): AuthSession? = null
        override suspend fun login(email: String, password: String): ApiResult<AuthSession> = error("unused")
        override suspend fun logout() {}
    }

    private val repo = object : StubRepository() {
        override suspend fun sessions() = ApiResult.Success(emptyList<SessionOut>())
        override suspend fun health(): Boolean = true
    }

    private fun check(mode: ThemeMode) {
        val vm = SplashViewModel(repo, noSession) // built outside composition (lint: ViewModelConstructorInComposable)
        rule.setContent { Series76Theme(mode) { SplashScreen(onDone = {}, viewModel = vm) } }
        rule.onNodeWithTag("splash").assertIsDisplayed()
        rule.onNodeWithText("Axel").assertIsDisplayed()
        rule.onNodeWithText("Series 76 actuator assistant").assertIsDisplayed()
    }

    @Test fun showsAxelNameAndTaglineInDark() = check(ThemeMode.DARK)
    @Test fun showsAxelNameAndTaglineInLight() = check(ThemeMode.LIGHT)
}

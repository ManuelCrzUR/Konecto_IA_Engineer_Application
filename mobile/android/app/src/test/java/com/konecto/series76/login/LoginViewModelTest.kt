package com.konecto.series76.login

import com.konecto.series76.data.ApiResult
import com.konecto.series76.data.AuthSession
import com.konecto.series76.data.FailureKind
import com.konecto.series76.data.FakeAuthRepository
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class LoginViewModelTest {
    private val dispatcher = StandardTestDispatcher()

    @Before fun setUp() = Dispatchers.setMain(dispatcher)
    @After fun tearDown() = Dispatchers.resetMain()

    private fun filled(repo: FakeAuthRepository) = LoginViewModel(repo).also {
        it.onEmail("ana@konecto.test"); it.onPassword("ana-series76")
    }

    @Test fun successMarksDone() = runTest(dispatcher) {
        val repo = FakeAuthRepository()
        val vm = filled(repo)
        vm.submit(); advanceUntilIdle()
        assertTrue(vm.state.value.done); assertFalse(vm.state.value.loading); assertNull(vm.state.value.error)
    }

    @Test fun wrongPasswordShowsServerMessage() = runTest(dispatcher) {
        val repo = FakeAuthRepository(onLogin = { _, _ ->
            ApiResult.Failure(FailureKind.Server(401, "invalid_credentials"), "Wrong email or password")
        })
        val vm = filled(repo)
        vm.submit(); advanceUntilIdle()
        assertEquals("Wrong email or password", vm.state.value.error)
        assertFalse(vm.state.value.done); assertFalse(vm.state.value.loading)
    }

    @Test fun networkErrorShowsMessage() = runTest(dispatcher) {
        val repo = FakeAuthRepository(onLogin = { _, _ -> ApiResult.Failure(FailureKind.Network, "Cannot reach the server") })
        val vm = filled(repo)
        vm.submit(); advanceUntilIdle()
        assertEquals("Cannot reach the server", vm.state.value.error)
    }

    @Test fun editingClearsError() = runTest(dispatcher) {
        val repo = FakeAuthRepository(onLogin = { _, _ -> ApiResult.Failure(FailureKind.Network, "x") })
        val vm = filled(repo)
        vm.submit(); advanceUntilIdle()
        vm.onPassword("y")
        assertNull(vm.state.value.error)
    }

    @Test fun blankInputIsIgnored() = runTest(dispatcher) {
        val repo = FakeAuthRepository()
        val vm = LoginViewModel(repo)
        vm.submit(); vm.onEmail("  "); vm.onPassword("pw"); vm.submit(); advanceUntilIdle()
        assertEquals(0, repo.loginCalls)
        assertFalse(vm.state.value.canSubmit)
    }

    @Test fun doubleSubmitIsIgnored() = runTest(dispatcher) {
        val gate = CompletableDeferred<Unit>()
        val repo = FakeAuthRepository(onLogin = { e, _ -> gate.await(); ApiResult.Success(AuthSession("t", e, "user")) })
        val vm = filled(repo)
        vm.submit(); vm.submit(); advanceUntilIdle()
        assertTrue(vm.state.value.loading)
        gate.complete(Unit); advanceUntilIdle()
        assertEquals(1, repo.loginCalls)
    }
}

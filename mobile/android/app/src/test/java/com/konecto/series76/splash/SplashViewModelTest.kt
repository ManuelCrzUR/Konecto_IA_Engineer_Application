package com.konecto.series76.splash

import com.konecto.series76.data.ApiResult
import com.konecto.series76.data.StubRepository
import com.konecto.series76.data.ConversationResponse
import com.konecto.series76.data.MessageOut
import com.konecto.series76.data.SessionOut
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.delay
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class SplashViewModelTest {
    private val dispatcher = StandardTestDispatcher()

    @Before fun setUp() = Dispatchers.setMain(dispatcher)
    @After fun tearDown() = Dispatchers.resetMain()

    private class FakeRepo(val onHealth: suspend () -> Boolean) : StubRepository() {
        override suspend fun health(): Boolean = onHealth()
    }

    private fun vm(health: suspend () -> Boolean) = SplashViewModel(FakeRepo(health), 600, 1500)

    @Test fun doneAtMinimumWhenHealthIsFast() = runTest(dispatcher) {
        val vm = vm { delay(50); true }
        advanceTimeBy(599); assertFalse(vm.done.value)
        advanceTimeBy(2); assertTrue(vm.done.value)
    }

    @Test fun doneAtHealthTimeWhenBetween() = runTest(dispatcher) {
        val vm = vm { delay(1000); true }
        advanceTimeBy(999); assertFalse(vm.done.value)
        advanceTimeBy(2); assertTrue(vm.done.value)
    }

    @Test fun doneAtMaximumWhenHealthHangs() = runTest(dispatcher) {
        val vm = vm { awaitCancellation() }
        advanceTimeBy(1499); assertFalse(vm.done.value)
        advanceTimeBy(2); assertTrue(vm.done.value)
    }

    @Test fun doneEvenIfServerIsOffline() = runTest(dispatcher) {
        val vm = vm { false }
        advanceTimeBy(599); assertFalse(vm.done.value)
        advanceTimeBy(2); assertTrue(vm.done.value)
    }
}

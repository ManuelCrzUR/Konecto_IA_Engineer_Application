package com.konecto.series76.chat

import androidx.lifecycle.SavedStateHandle
import com.konecto.series76.data.ApiResult
import com.konecto.series76.data.ConversationResponse
import com.konecto.series76.data.MessageOut
import com.konecto.series76.data.SessionOut
import com.konecto.series76.data.StubRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class SynchronizedRevealTest {
    private class Repo(val answer: ConversationResponse) : StubRepository() {
        override suspend fun sendMessage(sessionId: String?, query: String) = ApiResult.Success(answer)
        override suspend fun sessions(): ApiResult<List<SessionOut>> = ApiResult.Success(emptyList())
        override suspend fun messages(sessionId: String): ApiResult<List<MessageOut>> = ApiResult.Success(emptyList())
    }

    @Before fun setUp() = Dispatchers.setMain(StandardTestDispatcher())
    @After fun tearDown() = Dispatchers.resetMain()

    private fun vm(language: String? = "en") =
        ChatViewModel(Repo(ConversationResponse("s", "Answer", language = language)), SavedStateHandle(), revealBackstopMs = 12_000, safetyBackstopMs = 30_000)

    @Test fun spokenAnswerIsHeldUntilFirstAudio() = runTest {
        val vm = vm()
        vm.send("need 600 Nm", spoken = true); runCurrent()
        var s = vm.state.value
        assertEquals(listOf("user"), s.messages.map { it.role })
        val held = s.held!!
        assertEquals(held.key, s.autoSpeakKey)
        assertEquals(ThinkingPhase.Voice, s.thinkingPhase)
        assertTrue(s.busy)
        vm.onVoiceReady("other"); // wrong key: still held
        assertEquals(held, vm.state.value.held)
        vm.onVoiceReady(held.key)
        s = vm.state.value
        assertNull(s.held)
        assertNull(s.thinkingPhase)
        assertEquals(held, s.messages.last())
    }

    @Test fun backstopRevealsWhenNobodyPreparesTheVoice() = runTest {
        val vm = vm()
        vm.send("need 600 Nm", spoken = true); runCurrent()
        testScheduler.advanceTimeBy(29_999)
        assertTrue(vm.state.value.held != null)
        testScheduler.advanceTimeBy(2)
        assertNull(vm.state.value.held)
        assertNull(vm.state.value.autoSpeakKey)
        assertEquals(2, vm.state.value.messages.size)
    }

    @Test fun backstopCountsFromWhenTheSpeakerStartsPreparing() = runTest {
        val vm = vm()
        vm.send("need 600 Nm", spoken = true); runCurrent()
        val key = vm.state.value.held!!.key
        testScheduler.advanceTimeBy(20_000) // speak() starts late (app was in the background)
        assertTrue(vm.state.value.held != null)
        vm.onVoicePreparing(key)
        testScheduler.advanceTimeBy(11_999)
        assertTrue(vm.state.value.held != null)
        testScheduler.advanceTimeBy(2)
        assertNull(vm.state.value.held)
        assertNull(vm.state.value.autoSpeakKey)
        // The old safety timer must not fire a second reveal.
        testScheduler.advanceTimeBy(60_000)
        assertEquals(2, vm.state.value.messages.size)
    }

    @Test fun voiceReadyClearsAutoSpeakKeyAndCancelsTimers() = runTest {
        val vm = vm()
        vm.send("need 600 Nm", spoken = true); runCurrent()
        val key = vm.state.value.held!!.key
        vm.onVoicePreparing(key)
        vm.onVoiceReady(key)
        assertNull(vm.state.value.autoSpeakKey)
        testScheduler.advanceTimeBy(60_000)
        assertEquals(2, vm.state.value.messages.size)
    }

    @Test fun typedAnswerIsRevealedImmediately() = runTest {
        val vm = vm()
        vm.send("hello"); advanceUntilIdle()
        val s = vm.state.value
        assertNull(s.held)
        assertNull(s.autoSpeakKey)
        assertEquals(listOf("user", "assistant"), s.messages.map { it.role })
    }

    @Test fun newSendIsBlockedWhileAnswerIsHeld() = runTest {
        val vm = vm()
        vm.send("one", spoken = true); runCurrent()
        vm.send("two"); runCurrent()
        assertEquals(1, vm.state.value.messages.size)
    }

    @Test fun backendLanguageIsKeptOnTheItem() = runTest {
        val vm = vm("es")
        vm.send("hello"); advanceUntilIdle()
        assertEquals("es", vm.state.value.messages.last().language)
        val none = vm(null)
        none.send("hello"); advanceUntilIdle()
        assertNull(none.state.value.messages.last().language)
    }

    @Test fun phasesFollowTheState() = runTest {
        val vm = vm()
        assertNull(vm.state.value.thinkingPhase)
        vm.onVoiceTranscribing()
        assertEquals(ThinkingPhase.Transcribing, vm.state.value.thinkingPhase)
        vm.onVoiceEnded()
        vm.send("hola, qué actuador necesito"); 
        assertEquals(ThinkingPhase.Waiting, vm.state.value.thinkingPhase)
        assertEquals("es", vm.state.value.statusLang)
    }
}

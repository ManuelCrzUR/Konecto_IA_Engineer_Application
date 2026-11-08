package com.konecto.series76.chat

import com.konecto.series76.data.ConversationResponse
import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class StatusLabelTest {
    @Test fun transcribingAndVoiceLabelsAreLocalized() {
        assertEquals(listOf("Transcribiendo…"), statusLabels(ThinkingPhase.Transcribing, "es"))
        assertEquals(listOf("Transcribing…"), statusLabels(ThinkingPhase.Transcribing, "en"))
        assertEquals(listOf("Generando voz…"), statusLabels(ThinkingPhase.Voice, "es"))
        assertEquals(listOf("Generating voice…"), statusLabels(ThinkingPhase.Voice, "en"))
    }

    @Test fun waitingRotatesThroughThreeLabels() {
        assertEquals(
            listOf("Pensando…", "Revisando el catálogo…", "Organizando la respuesta…"),
            statusLabels(ThinkingPhase.Waiting, "es"),
        )
        assertEquals(
            listOf("Thinking…", "Checking the catalog…", "Organizing the answer…"),
            statusLabels(ThinkingPhase.Waiting, "en"),
        )
    }

    @Test fun unknownLanguageFallsBackToEnglish() {
        assertEquals("Thinking…", statusLabels(ThinkingPhase.Waiting, "fr").first())
    }

    @Test fun announcedTextIsStableAcrossRotation() {
        // The live region carries only the phase's first label, so rotating sub-labels are not re-announced.
        assertEquals("Pensando…", phaseDescription(ThinkingPhase.Waiting, "es"))
        assertEquals("Generating voice…", phaseDescription(ThinkingPhase.Voice, "en"))
    }

    @Test fun languageFieldIsOptionalInTheResponse() {
        val json = Json { ignoreUnknownKeys = true }
        val with = json.decodeFromString<ConversationResponse>("""{"session_id":"s","answer":"a","language":"es","extra":1}""")
        val without = json.decodeFromString<ConversationResponse>("""{"session_id":"s","answer":"a"}""")
        assertEquals("es", with.language)
        assertNull(without.language)
    }
}

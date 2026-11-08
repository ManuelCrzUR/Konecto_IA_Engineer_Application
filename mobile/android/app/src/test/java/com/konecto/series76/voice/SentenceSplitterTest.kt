package com.konecto.series76.voice

import org.junit.Assert.assertEquals
import org.junit.Test

class SentenceSplitterTest {
    @Test fun splitsAfterTerminatorsFollowedBySpace() {
        assertEquals(listOf("One.", "Two?", "Three!", "Four"), splitSentences("One. Two? Three! Four"))
    }

    @Test fun neverSplitsInsidePartNumbersOrDecimals() {
        val text = "Part 764A00-11300000/A has 1.1 s speed. It is explosionproof."
        assertEquals(
            listOf("Part 764A00-11300000/A has 1.1 s speed.", "It is explosionproof."),
            splitSentences(text),
        )
    }

    @Test fun partNumberAtSentenceEndStillEndsTheSentence() {
        assertEquals(listOf("Use 764A00-11300000/A.", "Next"), splitSentences("Use 764A00-11300000/A. Next"))
    }

    @Test fun keepsSpanishOpeners() {
        assertEquals(listOf("¿Cuál necesitas?", "¡Perfecto!", "Gracias."), splitSentences("¿Cuál necesitas? ¡Perfecto! Gracias."))
    }

    @Test fun lineBreaksSplitAndBlankInputIsEmpty() {
        assertEquals(listOf("Line one", "Line two"), splitSentences("Line one\nLine two"))
        assertEquals(emptyList<String>(), splitSentences("  \n "))
    }

    @Test fun backendLanguageBeatsGuessing() {
        assertEquals("es", resolveLocale("es", "Hello there").language)
        assertEquals("en", resolveLocale("en", "Hola, qué tal").language)
        assertEquals("es", resolveLocale(null, "Hola, qué tal").language)
    }
}

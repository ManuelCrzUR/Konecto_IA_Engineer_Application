package com.konecto.series76.voice

import org.junit.Assert.assertEquals
import org.junit.Test

class SpeechLanguageTest {
    @Test fun spanishByAccent() = assertEquals("es", speechLocale("¿Cuánto torque?").language)
    @Test fun spanishByWord() = assertEquals("es", speechLocale("necesito un actuador para 220V").language)
    @Test fun spanishGreeting() = assertEquals("es", speechLocale("hola").language)
    @Test fun englishDefault() = assertEquals("en", speechLocale("I need 600 Nm modulating").language)
    @Test fun partNumberIsEnglish() = assertEquals("en", speechLocale("761A00").language)

    @Test fun digitsAndPartNumbersUnchanged() {
        val out = speakableText("**761A00** delivers 1,250 in-lbs at 60 Hz.")
        assertEquals("761A00 delivers 1,250 in-lbs at 60 Hz.", out)
    }

    @Test fun stripsMarkdownAndDropsTables() {
        val md = "## Result\n- First 764X30\n* Second `code`\n1. Third 1,250\n| a | b |\n|---|---|\nDone"
        assertEquals("Result\nFirst 764X30\nSecond code\nThird 1,250\nDone", speakableText(md))
    }
}

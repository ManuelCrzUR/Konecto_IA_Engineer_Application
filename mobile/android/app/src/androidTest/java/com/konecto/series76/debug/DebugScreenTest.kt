package com.konecto.series76.debug

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.hasText
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onAllNodesWithTag
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.assertCountEquals
import androidx.test.platform.app.InstrumentationRegistry
import com.konecto.series76.data.MessageOut
import com.konecto.series76.data.ToolTrace
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import com.konecto.series76.ui.theme.Series76Theme
import org.junit.Rule
import org.junit.Test

class DebugScreenTest {
    @get:Rule val rule = createComposeRule()

    private val messages: List<MessageOut> = Json { ignoreUnknownKeys = true }.decodeFromString(
        ListSerializer(MessageOut.serializer()),
        InstrumentationRegistry.getInstrumentation().context.assets
            .open("debug/messages.json").bufferedReader().readText(),
    )

    @Test fun showsToolNamesAndDurations() {
        val turns = buildTurns(messages)
        rule.setContent { Series76Theme { DebugContent(DebugUiState.Success(turns), {}, {}) } }
        rule.onNodeWithTag("debug_turn_0").assertIsDisplayed()
        rule.onNodeWithTag("trace_0_0").assertIsDisplayed()
        rule.onNodeWithText("search_actuators").assertIsDisplayed()
        rule.onNodeWithText(formatDuration(turns[0].traces[0].durationMs)).assertIsDisplayed()
        rule.onNodeWithText(turns[1].question, substring = true).assertIsDisplayed()
        rule.onNodeWithText("get_actuator").assertIsDisplayed()
        rule.onAllNodesWithTag("guard_badge").assertCountEquals(0)
    }

    @Test fun numberGuardTraceIsHighlighted() {
        val guard = ToolTrace("number_guard", JsonObject(emptyMap()), JsonPrimitive("replaced"), 1.0)
        rule.setContent {
            Series76Theme { DebugContent(DebugUiState.Success(listOf(DebugTurn(0, "q", listOf(guard)))), {}, {}) }
        }
        rule.onNodeWithTag("guard_badge").assertIsDisplayed()
        rule.onNode(hasText("Number guard fired")).assertIsDisplayed()
    }

    @Test fun noSessionText() {
        rule.setContent { Series76Theme { DebugContent(DebugUiState.NoSession, {}, {}) } }
        rule.onNodeWithText(NO_SESSION_TEXT).assertIsDisplayed()
    }

    @Test fun errorShowsRetry() {
        rule.setContent { Series76Theme { DebugContent(DebugUiState.Error("Cannot reach the server"), {}, {}) } }
        rule.onNodeWithText("Cannot reach the server").assertIsDisplayed()
        rule.onNodeWithText("Retry").assertIsDisplayed()
    }
}

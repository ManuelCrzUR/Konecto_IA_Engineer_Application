package com.konecto.series76.a11y

import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.semantics.getOrNull
import androidx.compose.ui.test.SemanticsMatcher
import androidx.compose.ui.test.assert
import androidx.compose.ui.test.assertContentDescriptionEquals
import androidx.compose.ui.test.assertHeightIsAtLeast
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.unit.dp
import com.konecto.series76.chat.ChatContent
import com.konecto.series76.chat.ChatItem
import com.konecto.series76.chat.ChatUiState
import com.konecto.series76.data.Product
import com.konecto.series76.ui.ProductCard
import com.konecto.series76.ui.theme.Series76Theme
import kotlinx.serialization.json.JsonPrimitive
import org.junit.Rule
import org.junit.Test

class AccessibilityTest {
    @get:Rule val rule = createComposeRule()

    private val product = Product(
        partNumber = "764X30-11320000/A", enclosure = "weatherproof", voltage = "220V", phase = 1,
        service = "on_off", csaCertified = false, hasData = true,
        fields = mapOf("onoff_torque_nm" to JsonPrimitive(800)),
    )

    private fun chatState() = ChatUiState(
        messages = listOf(
            ChatItem("u1", "user", "hello"),
            ChatItem("a1", "assistant", "Hi there"),
        ),
        draft = "hello",
    )

    private fun setChat() = rule.setContent {
        Series76Theme {
            ChatContent(
                state = chatState(), onDraftChange = {}, onSend = {}, onRetry = {}, onBack = {}, onTitleTapsFired = {},
            )
        }
    }

    @Test fun micAndSendHaveContentDescriptions() {
        setChat()
        rule.onNodeWithTag("chat_mic").assertContentDescriptionEquals("Speak")
        rule.onNodeWithTag("chat_send").assertContentDescriptionEquals("Send")
    }

    @Test fun productCardIsOneItemStartingWithProduct() {
        rule.setContent { Series76Theme { ProductCard(product) } }
        rule.onNodeWithTag("product_card_${product.partNumber}").assert(
            SemanticsMatcher("merged description starts with \"Product\"") { node ->
                node.config.getOrNull(SemanticsProperties.ContentDescription)?.firstOrNull()?.startsWith("Product") == true
            },
        )
    }

    @Test fun chatTitleIsAHeading() {
        setChat()
        rule.onNodeWithTag("chat_title").assert(SemanticsMatcher.keyIsDefined(SemanticsProperties.Heading))
    }

    @Test fun micSendAndSpeakerMeetTouchTargetMinimum() {
        setChat()
        rule.onNodeWithTag("chat_mic").assertHeightIsAtLeast(48.dp)
        rule.onNodeWithTag("chat_send").assertHeightIsAtLeast(48.dp)
        rule.onNodeWithTag("speak_a1").assertHeightIsAtLeast(48.dp)
        rule.onNodeWithContentDescription("Read aloud").assertHeightIsAtLeast(48.dp)
    }
}

package com.konecto.series76.chat

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.konecto.series76.ui.axel.AxelAvatar
import com.konecto.series76.ui.axel.AxelState
import com.konecto.series76.ui.theme.AxelTheme

const val EMPTY_HINT = "Ask for a part number, or describe torque, voltage, enclosure and service. Every figure comes from the Series 76 tables."

/** Starter queries (from the design board); sent verbatim as the user's message. */
val SUGGESTIONS = listOf(
    "On/off torque of 764A00-11300000/A",
    "Need 200 Nm, 220V, weatherproof, modulating",
    "Which voltages and enclosures exist?",
)

@Composable
fun EmptyChat(onSuggestion: (String) -> Unit, modifier: Modifier = Modifier) {
    // Centered when it fits; scrolls in landscape or with the IME open.
    BoxWithConstraints(modifier.fillMaxWidth()) {
        Column(
            Modifier.fillMaxWidth().heightIn(min = maxHeight).verticalScroll(rememberScrollState())
                .padding(horizontal = 24.dp, vertical = 12.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(12.dp, Alignment.CenterVertically),
        ) {
            AxelAvatar(AxelState.IDLE, size = 96.dp)
            Text("Ask about Series 76 actuators", style = MaterialTheme.typography.titleLarge, textAlign = TextAlign.Center)
            Text(
                EMPTY_HINT, Modifier.testTag("chat_hint"),
                style = MaterialTheme.typography.bodyMedium, textAlign = TextAlign.Center,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            SUGGESTIONS.forEachIndexed { i, text ->
                Surface(
                    onClick = { onSuggestion(text) },
                    modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp).testTag("suggestion_$i"),
                    shape = RoundedCornerShape(50),
                    color = AxelTheme.colors.surfaceViolet,
                ) {
                    Text(
                        text, Modifier.padding(horizontal = 16.dp, vertical = 12.dp),
                        style = MaterialTheme.typography.bodyMedium, color = AxelTheme.colors.accentText,
                    )
                }
            }
        }
    }
}

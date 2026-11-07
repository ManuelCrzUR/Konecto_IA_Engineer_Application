package com.konecto.series76.chat

import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import com.konecto.series76.ui.AxelHeader
import com.konecto.series76.ui.axel.AxelAvatar
import com.konecto.series76.ui.axel.AxelState
import com.konecto.series76.ui.theme.AxelTheme

/** Five taps on the title fire [onTitleTapsFired]. */
@Composable
fun ChatHeader(onBack: () -> Unit, onTitleTapsFired: () -> Unit, modifier: Modifier = Modifier) {
    val counter = remember { TapCounter() }
    val noRipple = remember { MutableInteractionSource() }
    AxelHeader(modifier) {
        IconButton(onClick = onBack, modifier = Modifier.size(48.dp).testTag("chat_back")) {
            Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
        }
        AxelAvatar(AxelState.IDLE, size = 32.dp)
        Column(Modifier.padding(start = 12.dp)) {
            Text(
                "Axel",
                Modifier.testTag("chat_title").semantics { heading() }.clickable(interactionSource = noRipple, indication = null) {
                    if (counter.tap()) onTitleTapsFired()
                },
                style = MaterialTheme.typography.titleMedium,
            )
            Text(
                "Series 76 actuator assistant",
                style = AxelTheme.typography.label,
                color = AxelTheme.colors.textTertiary,
            )
        }
    }
}

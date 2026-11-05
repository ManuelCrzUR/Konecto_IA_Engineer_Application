package com.konecto.series76.chat

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.tween
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.unit.dp
import com.konecto.series76.ui.ComparisonTable
import com.konecto.series76.ui.ProductCard
import com.konecto.series76.ui.axel.AxelAvatar
import com.konecto.series76.ui.axel.AxelState
import com.konecto.series76.ui.theme.AxelTheme
import com.konecto.series76.ui.theme.Emphasized

internal val UserShape = RoundedCornerShape(20.dp, 20.dp, 6.dp, 20.dp)
internal val AssistantShape = RoundedCornerShape(20.dp, 20.dp, 20.dp, 6.dp)
private val BubbleMaxWidth = 300.dp

/** Fades in and rises 12 dp once; only alpha and translation are animated (read in the draw phase). */
@Composable
fun AnimatedMessage(animate: Boolean, onDone: () -> Unit = {}, content: @Composable () -> Unit) {
    if (!animate) {
        content()
        return
    }
    val progress = remember { Animatable(0f) }
    LaunchedEffect(Unit) {
        progress.animateTo(1f, tween(300, easing = Emphasized))
        onDone()
    }
    Column(
        Modifier.graphicsLayer {
            alpha = progress.value
            translationY = (1f - progress.value) * 12.dp.toPx()
        },
    ) { content() }
}

@Composable
fun MessageItem(item: ChatItem, animate: Boolean, onAnimated: () -> Unit) {
    AnimatedMessage(animate, onAnimated) {
        if (item.isUser) UserBubble(item.text) else AssistantMessage(item)
    }
}

@Composable
private fun UserBubble(text: String) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
        Surface(
            Modifier.widthIn(max = BubbleMaxWidth),
            shape = UserShape,
            color = MaterialTheme.colorScheme.primary.copy(alpha = 0.22f),
        ) {
            Text(
                plainText(text), Modifier.padding(horizontal = 16.dp, vertical = 12.dp),
                style = MaterialTheme.typography.bodyLarge,
            )
        }
    }
}

@Composable
private fun AssistantMessage(item: ChatItem) {
    Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Row(verticalAlignment = Alignment.Bottom, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            AxelAvatar(AxelState.IDLE, size = 28.dp)
            Surface(Modifier.widthIn(max = BubbleMaxWidth), shape = AssistantShape, color = AxelTheme.colors.surfaceViolet) {
                Text(
                    plainText(item.text), Modifier.padding(horizontal = 16.dp, vertical = 12.dp),
                    style = MaterialTheme.typography.bodyLarge,
                )
            }
        }
        item.products.forEach { ProductCard(it) }
        if (item.products.size >= 2) ComparisonTable(item.products)
    }
}

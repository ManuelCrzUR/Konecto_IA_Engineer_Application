package com.konecto.series76.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.IntrinsicSize
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.clickable
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.tween
import androidx.compose.animation.expandVertically
import androidx.compose.animation.shrinkVertically
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Surface
import com.konecto.series76.ui.theme.AxelTheme
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.konecto.series76.data.Product
import kotlinx.serialization.json.JsonPrimitive

internal fun serviceLabel(service: String): String = when (service) {
    "on_off_and_modulating" -> "On/off & modulating"
    "on_off" -> "On/off"
    "modulating" -> "Modulating"
    "unspecified" -> "Service not specified"
    else -> service
}

@Composable
fun ProductCard(product: Product, modifier: Modifier = Modifier) {
    var notesOpen by remember { mutableStateOf(false) }
    Surface(
        modifier = modifier.fillMaxWidth().testTag("product_card_${product.partNumber}"),
        shape = RoundedCornerShape(28.dp),
        color = MaterialTheme.colorScheme.surface,
    ) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text(product.partNumber, style = AxelTheme.typography.partNumber)
            ProductChips(product)
            if (!product.hasData) {
                Text(
                    "No data in the catalog", style = MaterialTheme.typography.bodyMedium,
                    color = AxelTheme.colors.caution,
                )
            } else {
                val (figures, rest) = remember(product.fields) { splitKeyFigures(orderedFields(product.fields)) }
                if (figures.isNotEmpty()) {
                    Row(Modifier.fillMaxWidth().height(IntrinsicSize.Max), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        figures.forEach { KeyFigureTile(it, Modifier.weight(1f)) }
                        repeat(MAX_KEY_FIGURES - figures.size) { Spacer(Modifier.weight(1f)) }
                    }
                }
                rest.forEach { row ->
                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                        Text(row.label, Modifier.weight(1f), style = AxelTheme.typography.label)
                        Text(
                            row.value,
                            Modifier.testTag("field_${row.key}_value"),
                            style = MaterialTheme.typography.bodyMedium.copy(fontFeatureSettings = "tnum"),
                            fontWeight = FontWeight.SemiBold,
                        )
                        Text(
                            if (row.unit.isEmpty()) "" else " ${row.unit}",
                            style = MaterialTheme.typography.bodySmall,
                        )
                    }
                }
            }
            if (product.notes.isNotEmpty()) {
                HorizontalDivider(color = AxelTheme.colors.divider)
                Box(
                    Modifier.fillMaxWidth().heightIn(min = 48.dp)
                        .clickable { notesOpen = !notesOpen }.testTag("notes_toggle"),
                    contentAlignment = Alignment.CenterStart,
                ) {
                    Text(
                        if (notesOpen) "Notes ▲" else "Notes ▼",
                        style = MaterialTheme.typography.labelLarge,
                        color = MaterialTheme.colorScheme.primary,
                    )
                }
                AnimatedVisibility(
                    notesOpen,
                    enter = expandVertically(tween(250, easing = FastOutSlowInEasing)),
                    exit = shrinkVertically(tween(250, easing = FastOutSlowInEasing)),
                ) {
                    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        product.notes.forEach { Text(it, style = MaterialTheme.typography.bodySmall) }
                    }
                }
            }
        }
    }
}

@Preview(showBackground = true)
@Composable
private fun ProductCardPreview() {
    ProductCard(
        Product(
            partNumber = "764X30-11320000/A", enclosure = "explosionproof", voltage = "220V", phase = 1,
            service = "on_off_and_modulating", csaCertified = false, hasData = true,
            fields = mapOf(
                "onoff_torque_nm" to JsonPrimitive(800),
                "speed_sec_60hz" to JsonPrimitive(34),
                "fla_60hz_a" to JsonPrimitive(2.4),
                "motor_power_w" to null,
            ),
            notes = listOf("3. Allowable motor voltage tolerance: +/- 10%"),
        ),
    )
}

package com.konecto.series76.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import com.konecto.series76.data.Product
import com.konecto.series76.data.displayValue
import com.konecto.series76.ui.theme.AxelTheme

internal const val MAX_KEY_FIGURES = 3

/** Splits rows (already in contract order) into key-figure tiles and plain rows. Order is kept. */
internal fun splitKeyFigures(rows: List<FieldRow>, max: Int = MAX_KEY_FIGURES): Pair<List<FieldRow>, List<FieldRow>> {
    val empty = displayValue(null)
    val figures = rows.filter { it.value != empty }.take(max)
    return figures to rows.filter { it !in figures }
}

internal fun enclosureLabel(enclosure: String): String = enclosure.replaceFirstChar { it.uppercase() }

@Composable
internal fun KeyFigureTile(row: FieldRow, modifier: Modifier = Modifier) {
    Surface(modifier, shape = RoundedCornerShape(16.dp), color = AxelTheme.colors.surfaceViolet) {
        Column(Modifier.fillMaxHeight().padding(12.dp)) {
            Text(row.label, style = AxelTheme.typography.label, color = MaterialTheme.colorScheme.onSurfaceVariant)
            ValueWithUnit(
                value = { Text(row.value, Modifier.testTag("field_${row.key}_value"), style = AxelTheme.typography.keyFigure) },
                unit = if (row.unit.isEmpty()) null else {
                    {
                        Text(
                            row.unit, softWrap = false, style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                },
            )
        }
    }
}

@Composable
internal fun InfoChip(text: String, modifier: Modifier = Modifier, caution: Boolean = false) {
    val colors = AxelTheme.colors
    Surface(
        modifier,
        shape = RoundedCornerShape(50),
        color = if (caution) colors.cautionContainer else colors.surfaceViolet,
        border = if (caution) BorderStroke(1.dp, colors.caution) else null,
    ) {
        Text(
            text, Modifier.padding(horizontal = 10.dp, vertical = 4.dp),
            style = AxelTheme.typography.label,
            color = if (caution) colors.caution else colors.accentText,
        )
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
internal fun ProductChips(p: Product) {
    FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        InfoChip(listOfNotNull(p.voltage, p.phase?.let { "${it}φ" }).joinToString(" · "))
        InfoChip(enclosureLabel(p.enclosure))
        InfoChip(serviceLabel(p.service))
        if (!p.csaCertified) InfoChip("Not CSA certified", Modifier.testTag("csa_chip"), caution = true)
    }
}

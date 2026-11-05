package com.konecto.series76.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.IntrinsicSize
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import com.konecto.series76.data.Product
import com.konecto.series76.data.displayValue
import com.konecto.series76.ui.theme.AxelTheme

private val LabelWidth = 160.dp
private val ColWidth = 132.dp
private val Gap = 4.dp
private val MinHeaderHeight = 64.dp
private val MinRowHeight = 44.dp
private val ColShape = RoundedCornerShape(16.dp)

/**
 * Column 0 is the best match: recommendations arrive ordered tightest-fit first.
 * Laid out row by row so a wrapping label and its values share the row's height.
 */
@Composable
fun ComparisonTable(products: List<Product>, modifier: Modifier = Modifier) {
    if (products.isEmpty()) return
    val perProduct = remember(products) { products.map { p -> orderedFields(p.fields).associateBy { it.key } } }
    // Union of rows in contract order (label/unit taken from the first product that has the key).
    val rows = remember(perProduct) {
        orderedKeys(perProduct.flatMap { it.keys }).map { key -> perProduct.firstNotNullOf { it[key] } }
    }
    Surface(modifier, shape = RoundedCornerShape(20.dp), color = MaterialTheme.colorScheme.surface) {
        Box(Modifier.horizontalScroll(rememberScrollState()).padding(12.dp).testTag("comparison_table")) {
            BestFrame()
            Column {
                Row(Modifier.height(IntrinsicSize.Min), horizontalArrangement = Arrangement.spacedBy(Gap)) {
                    Spacer(Modifier.width(LabelWidth).heightIn(min = MinHeaderHeight))
                    products.forEachIndexed { i, p -> HeaderCell(p, best = i == 0) }
                }
                rows.forEach { row ->
                    Row(Modifier.height(IntrinsicSize.Min), horizontalArrangement = Arrangement.spacedBy(Gap)) {
                        Cell(LabelWidth, Alignment.CenterStart) {
                            Text(
                                if (row.unit.isEmpty()) row.label else "${row.label} (${row.unit})",
                                style = AxelTheme.typography.label,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                        products.forEachIndexed { i, p ->
                            Cell(ColWidth, Alignment.CenterStart, Modifier.padding(horizontal = 8.dp)) {
                                Text(
                                    perProduct[i][row.key]?.value ?: displayValue(null),
                                    Modifier.testTag("compare_${p.partNumber}_${row.key}"),
                                    style = MaterialTheme.typography.bodyMedium.copy(fontFeatureSettings = "tnum"),
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

/** Highlight behind column 0, as tall as the rows drawn over it. */
@Composable
private fun BestFrame() {
    val colors = AxelTheme.colors
    var m = Modifier
        .offset(x = LabelWidth + Gap).width(ColWidth).fillMaxHeight()
        .shadow(12.dp, ColShape, ambientColor = colors.glow, spotColor = colors.glow)
        .background(MaterialTheme.colorScheme.surface, ColShape)
    // Border fades out as the theme goes dark (the glow takes over); glow is already a blended colour.
    val borderAlpha = 1f - colors.darkFraction
    if (borderAlpha > 0f) m = m.border(BorderStroke(1.dp, MaterialTheme.colorScheme.primary.copy(alpha = borderAlpha)), ColShape)
    Spacer(m)
}

@Composable
private fun Cell(width: Dp, align: Alignment, modifier: Modifier = Modifier, content: @Composable () -> Unit) {
    Box(Modifier.width(width).heightIn(min = MinRowHeight).fillMaxHeight().then(modifier), align) { content() }
}

@Composable
private fun HeaderCell(p: Product, best: Boolean) {
    Column(
        Modifier.width(ColWidth).heightIn(min = MinHeaderHeight).padding(horizontal = 8.dp),
        verticalArrangement = Arrangement.Center,
    ) {
        if (best) InfoChip("Best match", Modifier.padding(bottom = 4.dp))
        // A hyphen before a digit is not a line-break opportunity, so the text breaker split
        // the part number mid-digits ("1132000" / "0/A"). A zero-width space after the hyphen
        // lets it wrap only there; the characters shown are unchanged.
        Text(
            p.partNumber.replace("-", "-​"), Modifier.testTag("compare_header_${p.partNumber}"),
            style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold, maxLines = 2,
        )
    }
}

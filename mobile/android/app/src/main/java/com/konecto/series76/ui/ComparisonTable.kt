package com.konecto.series76.ui

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.IntrinsicSize
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.konecto.series76.data.Product
import com.konecto.series76.data.displayValue

private val LabelWidth = 150.dp
private val ColWidth = 130.dp

@Composable
fun ComparisonTable(products: List<Product>, modifier: Modifier = Modifier) {
    if (products.isEmpty()) return
    val perProduct = remember(products) { products.map { p -> orderedFields(p.fields).associateBy { it.key } } }
    // Union of rows in contract order (label/unit taken from the first product that has the key).
    val rows = remember(perProduct) {
        orderedKeys(perProduct.flatMap { it.keys }).map { key -> perProduct.firstNotNullOf { it[key] } }
    }
    Column(
        modifier.horizontalScroll(rememberScrollState()).width(IntrinsicSize.Max).testTag("comparison_table"),
    ) {
        Row {
            Text("", Modifier.width(LabelWidth))
            products.forEach {
                Text(
                    it.partNumber,
                    Modifier.width(ColWidth).padding(horizontal = 4.dp).testTag("compare_header_${it.partNumber}"),
                    style = MaterialTheme.typography.labelMedium,
                    fontWeight = FontWeight.Bold,
                )
            }
        }
        HorizontalDivider()
        rows.forEach { row ->
            Row(Modifier.padding(vertical = 4.dp)) {
                Text(
                    if (row.unit.isEmpty()) row.label else "${row.label} (${row.unit})",
                    Modifier.width(LabelWidth),
                    style = MaterialTheme.typography.bodySmall,
                )
                products.forEachIndexed { i, p ->
                    val v = perProduct[i][row.key]?.value ?: displayValue(null)
                    Text(
                        v,
                        Modifier.width(ColWidth).padding(horizontal = 4.dp).testTag("compare_${p.partNumber}_${row.key}"),
                        style = MaterialTheme.typography.bodyMedium,
                    )
                }
            }
        }
    }
}

package com.konecto.series76.ui

import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.IntrinsicMeasurable
import androidx.compose.ui.layout.IntrinsicMeasureScope
import androidx.compose.ui.layout.Layout
import androidx.compose.ui.layout.Measurable
import androidx.compose.ui.layout.MeasurePolicy
import androidx.compose.ui.layout.MeasureResult
import androidx.compose.ui.layout.MeasureScope
import androidx.compose.ui.unit.Constraints
import androidx.compose.ui.unit.dp

private val Gap = 4.dp

/**
 * A value with its unit beside it, baseline-aligned. When both do not fit the width, the whole unit
 * goes on its own line below the value; the unit never breaks. Intrinsics are exact so that a parent
 * Row using IntrinsicSize.Max sizes its tiles to the wrapped height.
 */
@Composable
internal fun ValueWithUnit(value: @Composable () -> Unit, unit: (@Composable () -> Unit)?, modifier: Modifier = Modifier) {
    Layout({ value(); unit?.invoke() }, modifier, ValueUnitPolicy)
}

private object ValueUnitPolicy : MeasurePolicy {
    private fun stacked(vw: Int, uw: Int, gap: Int, maxW: Int) = uw > 0 && vw + gap + uw > maxW

    override fun MeasureScope.measure(measurables: List<Measurable>, constraints: Constraints): MeasureResult {
        val loose = constraints.copy(minWidth = 0, minHeight = 0)
        val v = measurables[0].measure(loose)
        val u = measurables.getOrNull(1)?.measure(loose)
        val gap = Gap.roundToPx()
        val uw = u?.width ?: 0
        val below = stacked(v.width, uw, gap, constraints.maxWidth)
        val w = if (below) maxOf(v.width, uw) else v.width + (if (u != null) gap + uw else 0)
        val h = if (below) v.height + u!!.height else maxOf(v.height, u?.height ?: 0)
        return layout(w.coerceIn(constraints.minWidth, constraints.maxWidth), h.coerceIn(constraints.minHeight, constraints.maxHeight)) {
            v.placeRelative(0, if (below || u == null) 0 else h - v.height)
            u?.placeRelative(if (below) 0 else v.width + gap, if (below) v.height else h - u.height)
        }
    }

    override fun IntrinsicMeasureScope.minIntrinsicWidth(m: List<IntrinsicMeasurable>, height: Int) =
        maxOf(m[0].minIntrinsicWidth(height), m.getOrNull(1)?.minIntrinsicWidth(height) ?: 0)

    override fun IntrinsicMeasureScope.maxIntrinsicWidth(m: List<IntrinsicMeasurable>, height: Int) =
        m[0].maxIntrinsicWidth(height) + (m.getOrNull(1)?.let { Gap.roundToPx() + it.maxIntrinsicWidth(height) } ?: 0)

    override fun IntrinsicMeasureScope.minIntrinsicHeight(m: List<IntrinsicMeasurable>, width: Int) = heightFor(m, width)
    override fun IntrinsicMeasureScope.maxIntrinsicHeight(m: List<IntrinsicMeasurable>, width: Int) = heightFor(m, width)

    private fun IntrinsicMeasureScope.heightFor(m: List<IntrinsicMeasurable>, width: Int): Int {
        val vh = m[0].maxIntrinsicHeight(Int.MAX_VALUE)
        val u = m.getOrNull(1) ?: return vh
        val uh = u.maxIntrinsicHeight(Int.MAX_VALUE)
        val vw = m[0].maxIntrinsicWidth(Int.MAX_VALUE)
        val uw = u.maxIntrinsicWidth(Int.MAX_VALUE)
        return if (stacked(vw, uw, Gap.roundToPx(), width)) vh + uh else maxOf(vh, uh)
    }
}

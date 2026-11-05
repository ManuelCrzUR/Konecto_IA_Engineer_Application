package com.konecto.series76.ui.axel

import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.graphics.drawscope.scale
import androidx.compose.ui.graphics.drawscope.translate

enum class AxelState { IDLE, THINKING, READY, PROBLEM }

/** Colors are local on purpose: the avatar does not depend on the app theme. */
data class AxelPalette(
    val body: Color,
    val stroke: Color,
    val knob: Color,
    val slot: Color,
    val eyes: Color,
    val mouth: Color,
    val caution: Color,
) {
    companion object {
        val dark = AxelPalette(
            body = Color(0xFF20152A), stroke = Color(0xFFBD7BFF), knob = Color(0xFFBD7BFF),
            slot = Color(0xFF0E0E0E), eyes = Color(0xFFFFFFFF), mouth = Color(0xFFD0ACE5),
            caution = Color(0xFFFFB86B),
        )
        val light = AxelPalette(
            body = Color(0xFFF3EAFE), stroke = Color(0xFF7B2CBF), knob = Color(0xFF7B2CBF),
            slot = Color(0xFFFFFFFF), eyes = Color(0xFF16121C), mouth = Color(0xFF7B2CBF),
            caution = Color(0xFFA15C00),
        )
    }
}

/** Per-frame animated values, in viewBox (64x64) units. */
internal class AxelFrame(
    val knobDeg: Float = 0f,
    val glance: Float = 0f,
    val bounce: Float = 0f,
    val blink: Float = 1f,
)

// Size-independent: both live in the 64-unit viewBox and are scaled by the canvas transform.
private val NeutralSmile = Path().apply { moveTo(23f, 45f); quadraticTo(32f, 52f, 41f, 45f) }
private val WideSmile = Path().apply { moveTo(21f, 44f); quadraticTo(32f, 56f, 43f, 44f) }

/** Draws Axel in a 64x64 viewBox scaled to the canvas width. */
internal fun DrawScope.drawAxel(
    state: AxelState,
    p: AxelPalette,
    frame: AxelFrame,
) {
    scale(size.width / 64f, pivot = Offset.Zero) {
        translate(top = frame.bounce) {
            drawRoundRect(p.body, Offset(8f, 16f), Size(48f, 40f), CornerRadius(16f))
            drawRoundRect(p.stroke, Offset(8f, 16f), Size(48f, 40f), CornerRadius(16f), style = Stroke(2.5f))
            rotate(frame.knobDeg, pivot = Offset(32f, 10f)) {
                drawRoundRect(p.knob, Offset(26f, 5f), Size(12f, 11f), CornerRadius(3f))
                drawRoundRect(p.slot, Offset(31f, 3f), Size(2f, 6f), CornerRadius(1f))
            }
            drawFace(state, p, frame)
        }
    }
}

private fun DrawScope.drawFace(state: AxelState, p: AxelPalette, f: AxelFrame) {
    val line = Stroke(3f, cap = StrokeCap.Round)
    if (state == AxelState.PROBLEM) {
        drawLine(p.eyes, Offset(19.5f, 34f), Offset(28.5f, 34f), 3f, StrokeCap.Round)
        drawLine(p.eyes, Offset(35.5f, 34f), Offset(44.5f, 34f), 3f, StrokeCap.Round)
        drawLine(p.caution, Offset(24f, 47f), Offset(40f, 47f), 3f, StrokeCap.Round)
        return
    }
    translate(f.glance, -f.glance) {
        for (cx in floatArrayOf(24f, 40f)) {
            scale(1f, f.blink, pivot = Offset(cx, 34f)) { drawCircle(p.eyes, 4.5f, Offset(cx, 34f)) }
        }
    }
    if (state == AxelState.READY) {
        drawCircle(p.stroke.copy(alpha = .35f), 3f, Offset(16f, 43f))
        drawCircle(p.stroke.copy(alpha = .35f), 3f, Offset(48f, 43f))
    }
    drawPath(if (state == AxelState.READY) WideSmile else NeutralSmile, p.mouth, style = line)
}

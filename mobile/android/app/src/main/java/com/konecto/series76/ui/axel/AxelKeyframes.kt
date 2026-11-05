package com.konecto.series76.ui.axel

/** One keyframe stop: [fraction] of the cycle (0..1) and the value reached there. */
internal data class Stop(val fraction: Float, val value: Float)

/** Piecewise interpolation with ease-in-out per segment (mirrors CSS keyframes). */
internal fun keyframeValue(t: Float, vararg stops: Stop): Float {
    if (t <= stops.first().fraction) return stops.first().value
    for (i in 1 until stops.size) {
        val a = stops[i - 1]
        val b = stops[i]
        if (t <= b.fraction) {
            if (b.fraction == a.fraction) return b.value
            val u = (t - a.fraction) / (b.fraction - a.fraction)
            val eased = u * u * (3f - 2f * u) // smoothstep ~ cubic-bezier(.42,0,.58,1)
            return a.value + (b.value - a.value) * eased
        }
    }
    return stops.last().value
}

/** ax-stroke: knob rotation in degrees. */
internal fun knobAngle(t: Float) = keyframeValue(
    t, Stop(0f, 0f), Stop(.12f, 0f), Stop(.42f, 90f), Stop(.58f, 90f), Stop(.88f, 0f), Stop(1f, 0f),
)

/** ax-glance: eye offset in viewBox units (x = +v, y = -v). */
internal fun glanceOffset(t: Float) = keyframeValue(
    t, Stop(0f, 0f), Stop(.08f, 0f), Stop(.22f, 1.6f), Stop(.78f, 1.6f), Stop(1f, 0f),
)

/** ax-bounce: vertical offset in viewBox units (negative is up). */
internal fun bounceOffset(t: Float) = keyframeValue(
    t, Stop(0f, 0f), Stop(.2f, -5f), Stop(.35f, 0f), Stop(.45f, -2f), Stop(.55f, 0f), Stop(1f, 0f),
)

/** ax-blink over one blink (~320 ms): eye scaleY, 1 -> 0.1 (120 ms) -> 1 (200 ms). */
internal fun blinkScale(t: Float) = keyframeValue(t, Stop(0f, 1f), Stop(.375f, .1f), Stop(1f, 1f))

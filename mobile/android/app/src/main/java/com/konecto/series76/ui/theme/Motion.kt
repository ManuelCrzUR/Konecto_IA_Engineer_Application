package com.konecto.series76.ui.theme

import androidx.compose.animation.core.CubicBezierEasing
import androidx.compose.runtime.staticCompositionLocalOf

/** Material 3 emphasized-decelerate style curve used by screen and message transitions. */
val Emphasized = CubicBezierEasing(0.05f, 0.7f, 0.1f, 1f)

/** False when the system animator duration scale is 0; read once in [Series76Theme]. */
val LocalAnimationsEnabled = staticCompositionLocalOf { true }

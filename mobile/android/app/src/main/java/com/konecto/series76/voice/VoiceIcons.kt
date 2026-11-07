package com.konecto.series76.voice

import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.graphics.vector.addPathNodes
import androidx.compose.ui.unit.dp

// Material icons live in the extended icon set, which is not a dependency; these are the same 24dp paths.
private fun icon(name: String, path: String): ImageVector =
    ImageVector.Builder(name, 24.dp, 24.dp, 24f, 24f).addPath(
        pathData = addPathNodes(path), fill = SolidColor(Color.Black),
    ).build()

object VoiceIcons {
    val Mic: ImageVector by lazy {
        icon(
            "Mic",
            "M12,14c1.66,0 3,-1.34 3,-3V5c0,-1.66 -1.34,-3 -3,-3S9,3.34 9,5v6c0,1.66 1.34,3 3,3zM17.91,11c-0.49,0 -0.9,0.36 -0.98,0.85C16.52,14.2 14.47,16 12,16s-4.52,-1.8 -4.93,-4.15c-0.08,-0.49 -0.49,-0.85 -0.98,-0.85 -0.61,0 -1.09,0.54 -1,1.14 0.49,3 2.89,5.35 5.91,5.78V20c0,0.55 0.45,1 1,1s1,-0.45 1,-1v-2.08c3.02,-0.43 5.42,-2.78 5.91,-5.78 0.1,-0.6 -0.39,-1.14 -1,-1.14z",
        )
    }
    val Stop: ImageVector by lazy { icon("Stop", "M6,6h12v12H6z") }
    val VolumeUp: ImageVector by lazy {
        icon(
            "VolumeUp",
            "M3,9v6h4l5,5V4L7,9H3zM16.5,12c0,-1.77 -1.02,-3.29 -2.5,-4.03v8.05c1.48,-0.73 2.5,-2.25 2.5,-4.02zM14,3.23v2.06c2.89,0.86 5,3.54 5,6.71s-2.11,5.85 -5,6.71v2.06c4.01,-0.91 7,-4.49 7,-8.77s-2.99,-7.86 -7,-8.77z",
        )
    }
}

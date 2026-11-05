package com.konecto.series76.ui.theme

import androidx.compose.material3.Typography
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontVariation
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.em
import androidx.compose.ui.unit.sp
import com.konecto.series76.R

private fun dmSans(weight: FontWeight) = Font(
    resId = R.font.dm_sans,
    weight = weight,
    variationSettings = FontVariation.Settings(FontVariation.weight(weight.weight)),
)

/** DM Sans (OFL), bundled variable font; minSdk 26 supports variation settings. */
val DmSans = FontFamily(
    dmSans(FontWeight.Normal),
    dmSans(FontWeight.Medium),
    dmSans(FontWeight.SemiBold),
    dmSans(FontWeight.Bold),
)

private const val TNUM = "tnum"

/** Extra roles from DESIGN.md section 3 that Material 3 has no slot for. */
data class AxelTypography(
    val title: TextStyle,
    val partNumber: TextStyle,
    val keyFigure: TextStyle,
    val label: TextStyle,
    val code: TextStyle,
)

val DefaultAxelTypography = AxelTypography(
    title = TextStyle(fontFamily = DmSans, fontSize = 28.sp, fontWeight = FontWeight.Bold, letterSpacing = (-0.01).em),
    partNumber = TextStyle(
        fontFamily = DmSans, fontSize = 20.sp, fontWeight = FontWeight.Bold,
        letterSpacing = (-0.01).em, fontFeatureSettings = TNUM,
    ),
    keyFigure = TextStyle(
        fontFamily = DmSans, fontSize = 24.sp, fontWeight = FontWeight.Bold, fontFeatureSettings = TNUM,
    ),
    label = TextStyle(fontFamily = DmSans, fontSize = 13.sp, fontWeight = FontWeight.Medium),
    code = TextStyle(fontFamily = FontFamily.Monospace, fontSize = 12.sp, fontWeight = FontWeight.Normal),
)

private val Base = Typography()

val Series76Typography = Typography(
    displayLarge = Base.displayLarge.copy(fontFamily = DmSans),
    displayMedium = Base.displayMedium.copy(fontFamily = DmSans),
    displaySmall = Base.displaySmall.copy(fontFamily = DmSans),
    headlineLarge = Base.headlineLarge.copy(fontFamily = DmSans),
    headlineMedium = Base.headlineMedium.copy(fontFamily = DmSans),
    headlineSmall = DefaultAxelTypography.title.copy(fontSize = 24.sp),
    titleLarge = DefaultAxelTypography.title,
    titleMedium = DefaultAxelTypography.partNumber,
    titleSmall = Base.titleSmall.copy(fontFamily = DmSans),
    bodyLarge = TextStyle(fontFamily = DmSans, fontSize = 16.sp, lineHeight = 24.sp, fontWeight = FontWeight.Normal),
    bodyMedium = Base.bodyMedium.copy(fontFamily = DmSans),
    bodySmall = Base.bodySmall.copy(fontFamily = DmSans),
    labelLarge = DefaultAxelTypography.label,
    labelMedium = DefaultAxelTypography.label,
    labelSmall = Base.labelSmall.copy(fontFamily = DmSans),
)

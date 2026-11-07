package com.konecto.series76.ui

import androidx.compose.ui.test.assertTextEquals
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.assertIsDisplayed
import androidx.test.platform.app.InstrumentationRegistry
import com.konecto.series76.data.Product
import com.konecto.series76.data.displayValue
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import androidx.compose.ui.test.onAllNodesWithTag
import androidx.compose.ui.test.assertCountEquals
import com.konecto.series76.ui.theme.Series76Theme
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.ui.Modifier
import org.junit.Rule
import org.junit.Test

class ProductCardTest {
    @get:Rule val rule = createComposeRule()

    private val json = Json { ignoreUnknownKeys = true }

    private fun products(file: String): List<Product> {
        val text = InstrumentationRegistry.getInstrumentation().context.assets
            .open("ui/$file").bufferedReader().readText()
        return json.parseToJsonElement(text).jsonObject["products"]!!.jsonArray
            .map { json.decodeFromJsonElement(Product.serializer(), it) }
    }

    @Test fun valuesEqualJsonLiterals() {
        val p = products("conversation_recommend.json")[0]
        rule.setContent { Series76Theme { Column(Modifier.verticalScroll(rememberScrollState())) { ProductCard(p) } } }
        rule.onNodeWithTag("product_card_${p.partNumber}").assertIsDisplayed()
        p.fields.forEach { (k, v) ->
            rule.onNodeWithTag("field_${k}_value", useUnmergedTree = true).assertTextEquals(v?.content ?: "—")
        }
        rule.onNodeWithTag("field_onoff_torque_nm_value", useUnmergedTree = true).assertTextEquals("800")
        rule.onNodeWithTag("field_fla_60hz_a_value", useUnmergedTree = true).assertTextEquals("2.4")
    }

    @Test fun noDataProductShowsNA() {
        val p = products("conversation_no_data.json")[0]
        rule.setContent { Series76Theme { Column(Modifier.verticalScroll(rememberScrollState())) { ProductCard(p) } } }
        rule.onNodeWithText("No data in the catalog").assertIsDisplayed()
    }

    @Test fun comparisonHasColumnPerProductAndDashForMissing() {
        val list = products("conversation_recommend.json").take(2) +
            products("conversation_no_data.json")
        rule.setContent { Series76Theme { ComparisonTable(list) } }
        list.forEach { rule.onNodeWithTag("compare_header_${it.partNumber}").assertExists() }
        rule.onNodeWithTag("compare_${list[0].partNumber}_onoff_torque_nm").assertTextEquals("800")
        rule.onNodeWithTag("compare_${list[2].partNumber}_onoff_torque_nm").assertTextEquals("—")
    }

    @Test fun csaChipShownOnlyWhenNotCertified() {
        val p = products("conversation_recommend.json")[0]
        rule.setContent { Series76Theme { ProductCard(p.copy(csaCertified = false)) } }
        rule.onNodeWithTag("csa_chip", useUnmergedTree = true).assertIsDisplayed()
        rule.onNodeWithText("Not CSA certified").assertIsDisplayed()
    }

    @Test fun csaChipAbsentWhenCertified() {
        val p = products("conversation_recommend.json")[0]
        rule.setContent { Series76Theme { Column(Modifier.verticalScroll(rememberScrollState())) { ProductCard(p) } } }
        rule.onAllNodesWithTag("csa_chip", useUnmergedTree = true).assertCountEquals(0)
    }

    @Test fun keyFigureTilesKeepJsonLiteralsInContractOrder() {
        val p = products("conversation_recommend.json")[0]
        val (figures, _) = splitKeyFigures(orderedFields(p.fields))
        rule.setContent { Series76Theme { Column(Modifier.verticalScroll(rememberScrollState())) { ProductCard(p) } } }
        figures.forEach { f ->
            rule.onNodeWithTag("field_${f.key}_value", useUnmergedTree = true).assertTextEquals(displayValue(p.fields[f.key]))
        }
        rule.onNodeWithTag("field_onoff_torque_nm_value", useUnmergedTree = true).assertTextEquals("800")
    }
}

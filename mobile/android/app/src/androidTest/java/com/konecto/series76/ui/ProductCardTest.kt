package com.konecto.series76.ui

import androidx.compose.ui.test.assertTextEquals
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.assertIsDisplayed
import androidx.test.platform.app.InstrumentationRegistry
import com.konecto.series76.data.Product
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
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
        rule.setContent { ProductCard(p) }
        rule.onNodeWithTag("product_card_${p.partNumber}").assertIsDisplayed()
        p.fields.forEach { (k, v) ->
            rule.onNodeWithTag("field_${k}_value").assertTextEquals(v?.content ?: "—")
        }
        rule.onNodeWithTag("field_onoff_torque_nm_value").assertTextEquals("800")
        rule.onNodeWithTag("field_fla_60hz_a_value").assertTextEquals("2.4")
    }

    @Test fun noDataProductShowsNA() {
        val p = products("conversation_no_data.json")[0]
        rule.setContent { ProductCard(p) }
        rule.onNodeWithText("No data (N/A)").assertIsDisplayed()
    }

    @Test fun comparisonHasColumnPerProductAndDashForMissing() {
        val list = products("conversation_recommend.json").take(2) +
            products("conversation_no_data.json")
        rule.setContent { ComparisonTable(list) }
        list.forEach { rule.onNodeWithTag("compare_header_${it.partNumber}").assertExists() }
        rule.onNodeWithTag("compare_${list[0].partNumber}_onoff_torque_nm").assertTextEquals("800")
        rule.onNodeWithTag("compare_${list[2].partNumber}_onoff_torque_nm").assertTextEquals("—")
    }
}

package com.konecto.series76.nav

import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.background
import androidx.compose.material3.Text
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.getUnclippedBoundsInRoot
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.konecto.series76.ui.theme.NavMotion
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class NavTransitionTest {
    @get:Rule val rule = createComposeRule()
    private lateinit var nav: NavHostController

    private fun host() {
        rule.setContent {
            nav = rememberNavController()
            NavHost(nav, startDestination = "a") {
                composable(
                    "a",
                    exitTransition = { NavMotion.forwardOut() },
                    popEnterTransition = { NavMotion.backIn() },
                ) { Text("A", Modifier.fillMaxSize().background(Color.White).testTag("a")) }
                composable(
                    "b",
                    enterTransition = { NavMotion.forwardIn() },
                    popExitTransition = { NavMotion.backOut() },
                ) { Text("B", Modifier.fillMaxSize().background(Color.White).testTag("b")) }
            }
        }
    }

    @Test
    fun forwardTransitionRunsThenSettles() {
        rule.mainClock.autoAdvance = false
        host()
        rule.waitForIdle()
        rule.runOnUiThread { nav.navigate("b") }
        rule.mainClock.advanceTimeByFrame()
        rule.mainClock.advanceTimeBy(120)
        // Mid-transition both destinations are composed.
        rule.onNodeWithTag("a").assertIsDisplayed()
        rule.onNodeWithTag("b").assertIsDisplayed()
        val left = rule.onNodeWithTag("b").getUnclippedBoundsInRoot().left
        assertTrue("incoming should still be offset, left=$left", left > 0.dp)
        rule.mainClock.advanceTimeBy(600)
        rule.onNodeWithTag("a").assertDoesNotExist()
        rule.onNodeWithTag("b").assertIsDisplayed()
        assertTrue(rule.onNodeWithTag("b").getUnclippedBoundsInRoot().left == 0.dp)
    }
}

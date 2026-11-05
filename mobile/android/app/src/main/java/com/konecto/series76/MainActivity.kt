package com.konecto.series76

import android.graphics.Color
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import androidx.compose.animation.fadeIn
import androidx.compose.animation.scaleIn
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.animation.fadeOut
import androidx.compose.animation.core.tween
import com.konecto.series76.splash.SplashScreen
import androidx.activity.SystemBarStyle
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.getValue
import androidx.compose.runtime.LaunchedEffect
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.konecto.series76.ui.theme.Emphasized
import com.konecto.series76.ui.theme.ThemeMode
import com.konecto.series76.ui.theme.isDark
import androidx.compose.runtime.Composable
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.launch
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.konecto.series76.chat.ChatScreen
import com.konecto.series76.conversations.ConversationsScreen
import com.konecto.series76.debug.DebugScreen
import com.konecto.series76.ui.theme.Series76Theme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        val splash = installSplashScreen()
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        // null = stored theme not loaded yet: the system splash stays up so no frame uses a wrong theme.
        val stored = MutableStateFlow<ThemeMode?>(null)
        splash.setKeepOnScreenCondition { stored.value == null }
        val prefs = (application as App).container.themePreferences
        lifecycleScope.launch { prefs.themeMode.collect { stored.value = it } }
        setContent {
            val loaded by stored.collectAsStateWithLifecycle()
            val mode = loaded ?: return@setContent
            val dark = mode.isDark()
            LaunchedEffect(dark) {
                // Bar icons follow the resolved theme, not the system one.
                val bars = if (dark) SystemBarStyle.dark(Color.TRANSPARENT)
                else SystemBarStyle.light(Color.TRANSPARENT, Color.TRANSPARENT)
                enableEdgeToEdge(statusBarStyle = bars, navigationBarStyle = bars)
            }
            Series76Theme(themeMode = mode) {
                AppNav()
            }
        }
    }
}

@Composable
private fun AppNav() {
    val nav = rememberNavController()
    NavHost(navController = nav, startDestination = "splash") {
        composable(
            "splash",
            exitTransition = { fadeOut(tween(300)) },
        ) {
            SplashScreen(onDone = {
                nav.navigate("conversations") { popUpTo("splash") { inclusive = true } }
            })
        }
        composable(
            "conversations",
            enterTransition = { if (initialState.destination.route == "splash") fadeIn(tween(300)) else sharedAxisIn(1) },
            exitTransition = { sharedAxisOut(-1) },
            popEnterTransition = { sharedAxisIn(-1) },
            popExitTransition = { sharedAxisOut(1) },
        ) {
            ConversationsScreen(
                onOpenChat = { id -> nav.navigate(if (id == null) "chat" else "chat?sessionId=$id") },
            )
        }
        composable(
            route = "chat?sessionId={sessionId}",
            arguments = listOf(
                navArgument("sessionId") {
                    type = NavType.StringType
                    nullable = true
                    defaultValue = null
                },
            ),
            enterTransition = { sharedAxisIn(1) },
            exitTransition = {
                if (targetState.destination.route?.startsWith("debug") == true) fadeThroughOut() else sharedAxisOut(-1)
            },
            popEnterTransition = {
                if (initialState.destination.route?.startsWith("debug") == true) fadeThroughIn() else sharedAxisIn(-1)
            },
            popExitTransition = { sharedAxisOut(1) },
        ) { entry ->
            ChatScreen(
                sessionId = entry.arguments?.getString("sessionId"),
                onBack = { nav.popBackStack() },
                // Debug shows the stored traces of this session (null = nothing sent yet).
                onOpenDebug = { id -> nav.navigate(if (id == null) "debug" else "debug?sessionId=$id") },
            )
        }
        composable(
            route = "debug?sessionId={sessionId}",
            arguments = listOf(
                navArgument("sessionId") {
                    type = NavType.StringType
                    nullable = true
                    defaultValue = null
                },
            ),
            enterTransition = { fadeThroughIn() },
            exitTransition = { fadeThroughOut() },
            popEnterTransition = { fadeThroughIn() },
            popExitTransition = { fadeThroughOut() },
        ) { entry ->
            DebugScreen(
                sessionId = entry.arguments?.getString("sessionId"),
                onBack = { nav.popBackStack() },
            )
        }
    }
}

// Shared X axis: dir = 1 moves forward (enter from the right), -1 reverses it.
private fun sharedAxisIn(dir: Int) =
    slideInHorizontally(tween(300, easing = Emphasized)) { dir * it / 3 } +
        fadeIn(tween(300, easing = Emphasized))

private fun sharedAxisOut(dir: Int) =
    slideOutHorizontally(tween(300, easing = Emphasized)) { dir * it / 3 } + fadeOut(tween(200))

// Fade-through: the outgoing screen leaves first, the incoming one scales in after 90 ms.
private fun fadeThroughOut() = fadeOut(tween(90))

private fun fadeThroughIn() =
    fadeIn(tween(210, delayMillis = 90)) + scaleIn(tween(210, delayMillis = 90), initialScale = 0.92f)

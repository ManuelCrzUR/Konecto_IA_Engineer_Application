package com.konecto.series76

import android.graphics.Color
import android.os.Build
import android.os.Bundle
import androidx.activity.SystemBarStyle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import com.konecto.series76.splash.SplashScreen
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.getValue
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.konecto.series76.nav.Routes
import com.konecto.series76.ui.theme.NavMotion
import com.konecto.series76.ui.theme.ThemeMode
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
        // Transparent scrims: SystemBarIcons (app theme) alone decides icon contrast, so a system-night
        // scrim can't clash with it. Contrast enforcement off so 3-button nav stays transparent (API 29+).
        enableEdgeToEdge(
            statusBarStyle = SystemBarStyle.auto(Color.TRANSPARENT, Color.TRANSPARENT),
            navigationBarStyle = SystemBarStyle.auto(Color.TRANSPARENT, Color.TRANSPARENT),
        )
        if (Build.VERSION.SDK_INT >= 29) window.isNavigationBarContrastEnforced = false
        // null = stored theme not loaded yet: the system splash stays up so no frame uses a wrong theme.
        val stored = MutableStateFlow<ThemeMode?>(null)
        splash.setKeepOnScreenCondition { stored.value == null }
        val prefs = (application as App).container.themePreferences
        lifecycleScope.launch { prefs.themeMode.collect { stored.value = it } }
        setContent {
            val loaded by stored.collectAsStateWithLifecycle()
            val mode = loaded ?: return@setContent
            // System bar icons follow the resolved theme inside Series76Theme (SystemBarIcons).
            Series76Theme(themeMode = mode) {
                AppNav()
            }
        }
    }
}

@Composable
private fun AppNav() {
    val nav = rememberNavController()
    NavHost(navController = nav, startDestination = Routes.SPLASH) {
        composable(
            Routes.SPLASH,
            exitTransition = { NavMotion.splashFadeOut() },
        ) {
            SplashScreen(onDone = {
                nav.navigate(Routes.CONVERSATIONS) { popUpTo(Routes.SPLASH) { inclusive = true } }
            })
        }
        composable(
            Routes.CONVERSATIONS,
            enterTransition = {
                if (initialState.destination.route == Routes.SPLASH) NavMotion.splashFade() else NavMotion.forwardIn()
            },
            exitTransition = { NavMotion.forwardOut() },
            popEnterTransition = { NavMotion.backIn() },
            popExitTransition = { NavMotion.backOut() },
        ) {
            ConversationsScreen(
                onOpenChat = { id -> nav.navigate(Routes.chat(id)) },
            )
        }
        composable(
            route = Routes.CHAT_PATTERN,
            arguments = listOf(
                navArgument(Routes.SESSION_ARG) {
                    type = NavType.StringType
                    nullable = true
                    defaultValue = null
                },
            ),
            enterTransition = { NavMotion.forwardIn() },
            exitTransition = {
                if (targetState.destination.route?.startsWith(Routes.DEBUG) == true) NavMotion.fadeThroughOut() else NavMotion.forwardOut()
            },
            popEnterTransition = {
                if (initialState.destination.route?.startsWith(Routes.DEBUG) == true) NavMotion.fadeThroughIn() else NavMotion.backIn()
            },
            popExitTransition = { NavMotion.backOut() },
        ) { entry ->
            ChatScreen(
                sessionId = entry.arguments?.getString(Routes.SESSION_ARG),
                onBack = { nav.popBackStack() },
                // Debug shows the stored traces of this session (null = nothing sent yet).
                onOpenDebug = { id -> nav.navigate(Routes.debug(id)) },
            )
        }
        composable(
            route = Routes.DEBUG_PATTERN,
            arguments = listOf(
                navArgument(Routes.SESSION_ARG) {
                    type = NavType.StringType
                    nullable = true
                    defaultValue = null
                },
            ),
            enterTransition = { NavMotion.fadeThroughIn() },
            exitTransition = { NavMotion.fadeThroughOut() },
            popEnterTransition = { NavMotion.fadeThroughIn() },
            popExitTransition = { NavMotion.fadeThroughOut() },
        ) { entry ->
            DebugScreen(
                sessionId = entry.arguments?.getString(Routes.SESSION_ARG),
                onBack = { nav.popBackStack() },
            )
        }
    }
}

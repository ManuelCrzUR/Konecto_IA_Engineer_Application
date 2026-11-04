package com.konecto.series76

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.Composable
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
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            Series76Theme {
                AppNav()
            }
        }
    }
}

@Composable
private fun AppNav() {
    val nav = rememberNavController()
    NavHost(navController = nav, startDestination = "conversations") {
        composable("conversations") {
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
        ) { entry ->
            DebugScreen(
                sessionId = entry.arguments?.getString("sessionId"),
                onBack = { nav.popBackStack() },
            )
        }
    }
}

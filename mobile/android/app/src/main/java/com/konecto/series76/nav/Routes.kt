package com.konecto.series76.nav

/** Single source of truth for navigation routes; MainActivity and tests use these, never string literals. */
object Routes {
    const val SPLASH = "splash"
    const val LOGIN = "login"
    const val CONVERSATIONS = "conversations"
    const val CHAT = "chat"
    const val DEBUG = "debug"

    const val SESSION_ARG = "sessionId"
    const val CHAT_PATTERN = "$CHAT?$SESSION_ARG={$SESSION_ARG}"
    const val DEBUG_PATTERN = "$DEBUG?$SESSION_ARG={$SESSION_ARG}"

    /** A null id opens a new, empty chat. */
    fun chat(id: String?) = if (id == null) CHAT else "$CHAT?$SESSION_ARG=$id"

    /** A null id opens Debug with nothing sent yet. */
    fun debug(id: String?) = if (id == null) DEBUG else "$DEBUG?$SESSION_ARG=$id"
}

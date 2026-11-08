package com.konecto.series76.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive

@Serializable
data class ConversationRequest(
    @SerialName("session_id") val sessionId: String? = null,
    val query: String,
)

@Serializable
data class ConversationResponse(
    @SerialName("session_id") val sessionId: String,
    val answer: String,
    val products: List<Product> = emptyList(),
    val debug: List<ToolTrace> = emptyList(),
    /** "es" or "en": language of [answer]; null from older backends. */
    val language: String? = null,
)

@Serializable
data class Product(
    @SerialName("part_number") val partNumber: String,
    val enclosure: String,
    val voltage: String,
    val phase: Int? = null,
    val service: String,
    @SerialName("csa_certified") val csaCertified: Boolean = true,
    @SerialName("has_data") val hasData: Boolean,
    val fields: Map<String, JsonPrimitive?> = emptyMap(),
    val notes: List<String> = emptyList(),
)

@Serializable
data class ToolTrace(
    val tool: String,
    val params: JsonObject = JsonObject(emptyMap()),
    val result: JsonElement = JsonNull,
    @SerialName("duration_ms") val durationMs: Double? = null,
)

@Serializable
data class SessionOut(
    val id: String,
    @SerialName("user_id") val userId: String? = null,
    val title: String,
    @SerialName("created_at") val createdAt: String,
    @SerialName("updated_at") val updatedAt: String,
    val match: SearchMatch? = null,
)

/** Present only on `GET /api/sessions?q=`: where the query matched and a backend-cut snippet. */
@Serializable
data class SearchMatch(val where: String, val snippet: String)

@Serializable
data class MessageOut(
    val id: Long,
    @SerialName("session_id") val sessionId: String,
    val role: String,
    val content: String,
    val products: List<Product> = emptyList(),
    val trace: List<ToolTrace> = emptyList(),
    @SerialName("created_at") val createdAt: String,
)

@Serializable
data class ErrorOut(val error: String, val detail: String? = null)

/** THE number rule: show the literal JSON text. Never convert or format. */
fun displayValue(p: JsonPrimitive?): String =
    if (p == null || p is JsonNull) "—" else p.content

@Serializable
data class TranscribeResponse(
    val text: String,
    @SerialName("raw_text") val rawText: String? = null,
    val model: String? = null,
    val seconds: Double? = null,
)

@Serializable
data class SpeechRequest(val text: String, val language: String? = null)

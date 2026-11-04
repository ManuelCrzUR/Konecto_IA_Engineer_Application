# Android app contract (Sprint 5)

Single source of truth for the subagents building `mobile/android`. The HTTP
contract is the backend's (`backend/app/api/schemas.py`, `docs/ARCHITECTURE.md`
§4, §5). Real responses captured from the running API live in
`mobile/contract/*.json` and are the test fixtures (copy them into
`app/src/test/resources/contract/` and `app/src/androidTest/assets/contract/`).

## Stack (KISS)

- One Gradle module `:app`, Kotlin, Jetpack Compose (Material 3), Navigation Compose.
- Retrofit + OkHttp + kotlinx.serialization (converter
  `com.squareup.retrofit2:converter-kotlinx-serialization`). No Hilt: manual DI
  through one `AppContainer` created in `Application`.
- MVVM: `ViewModel` + `StateFlow<UiState>`; coroutines.
- Version catalog `gradle/libs.versions.toml`; Gradle wrapper committed.
- minSdk 26, target/compileSdk = the highest platform installed in
  `~/Library/Android/sdk/platforms` (check; likely 36 or 37). Java/Kotlin JVM target 17.
- Build with the JDK bundled in Android Studio:
  `export JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home"`
  and `ANDROID_HOME=~/Library/Android/sdk` (write `local.properties` `sdk.dir=`; it is git-ignored).
- applicationId / namespace: `com.konecto.series76`.

## Packages (`com.konecto.series76`)

```
App.kt (Application + AppContainer)   MainActivity.kt (NavHost)
data/      ApiModels.kt  ApiService.kt  ApiClient.kt  ApiResult.kt
           AssistantRepository.kt (interface the ViewModels use)  Repository.kt (HTTP impl)
ui/        theme/  ProductCard.kt  ComparisonTable.kt  FieldLabels.kt
conversations/  ConversationsScreen.kt  ConversationsViewModel.kt
chat/      ChatScreen.kt  ChatViewModel.kt
debug/     DebugScreen.kt
```

## Backend URL

`BuildConfig.API_BASE_URL`, read in `app/build.gradle.kts` from `local.properties`
key `api.baseUrl`, default `http://localhost:8000/`, reached through
`adb reverse tcp:<port> tcp:<port>` (`make android-reverse`; D-35). `10.0.2.2` did not
work with Colima's port forwarding; `adb reverse` works with Docker Desktop, Colima
and USB phones. The developer uses `api.baseUrl=http://localhost:8001/`.
Cleartext HTTP is allowed only for `10.0.2.2` and `localhost` via
`res/xml/network_security_config.xml`.

## Data models (kotlinx.serialization, `@SerialName` snake_case)

```kotlin
@Serializable data class ConversationRequest(val session_id: String? = null, val query: String)
@Serializable data class ConversationResponse(val session_id: String, val answer: String,
    val products: List<Product> = emptyList(), val debug: List<ToolTrace> = emptyList())
@Serializable data class Product(val part_number: String, val enclosure: String, val voltage: String,
    val phase: Int? = null, val service: String, val csa_certified: Boolean = true,
    val has_data: Boolean, val fields: Map<String, JsonPrimitive?> = emptyMap(),
    val notes: List<String> = emptyList())
@Serializable data class ToolTrace(val tool: String, val params: JsonObject,
    val result: JsonElement, val duration_ms: Double? = null)
@Serializable data class SessionOut(val id: String, val user_id: String? = null, val title: String,
    val created_at: String, val updated_at: String)
@Serializable data class MessageOut(val id: Long, val session_id: String, val role: String,
    val content: String, val products: List<Product> = emptyList(),
    val trace: List<ToolTrace> = emptyList(), val created_at: String)
@Serializable data class ErrorOut(val error: String, val detail: String? = null)
```
DECIDED: Kotlin properties are camelCase (`partNumber`, `csaCertified`, `hasData`,
`sessionId`, `durationMs`, ...) with `@SerialName("<json_name>")`; the JSON names
above are fixed. The source of truth is `data/ApiModels.kt`. `Json { ignoreUnknownKeys = true }`.

## THE number rule

The app NEVER converts, rounds or reformats a technical number. A field value is
displayed as `jsonPrimitive.content` — the literal JSON text (`800`, `6.5`), which
the backend already writes as printed in the PDF. No `toDouble()`, no `String.format`.
`null` -> "—". Tests assert that the text on screen equals the JSON literal.

## Field labels and units (presentation only, `ui/FieldLabels.kt`)

| key | label | unit |
|---|---|---|
| onoff_torque_nm / onoff_torque_in_lbs | On/off torque | Nm / in-lbs |
| mod_torque_nm / mod_torque_in_lbs | Modulating torque | Nm / in-lbs |
| output_torque_nm / output_torque_in_lbs | Output torque | Nm / in-lbs |
| onoff_duty_cycle_pct / mod_duty_cycle_pct / duty_cycle_pct | Duty cycle (on/off / mod. / —) | % |
| cycles_per_hour / starts_per_hour | Cycles per hour / Starts per hour | /h |
| speed_sec_60hz / speed_sec_50hz / speed_sec | Speed 60 Hz / 50 Hz / — | s per 90° |
| fla_60hz_a / fla_50hz_a / fla_a | FLA 60 Hz / 50 Hz / — | A |
| lra_60hz_a / lra_50hz_a / lra_a | LRA 60 Hz / 50 Hz / — | A |
| motor_power_w | Motor power | W |

Display order = this table's order; unknown keys are shown last with the raw key
as label (never dropped).

## Components

- `ProductCard(product)`: part number (title), voltage · phase · enclosure · service,
  "Not CSA certified" chip when `csa_certified == false`, "No data (N/A)" when
  `has_data == false`, then label/value/unit rows, then notes (collapsible).
- `ComparisonTable(products)`: shown when 2+ products; one column per product
  (horizontal scroll), one row per field present in any product; "—" for missing.

## Screens

- **Conversations** (start): list of `GET /api/sessions` (title, relative date),
  "New conversation" FAB, pull/refresh. Tap -> Chat with that session id.
- **Chat**: loads `GET /api/sessions/{id}/messages` for an existing session; bubbles
  for user/assistant; assistant bubbles show their product cards and, with 2+
  products, the comparison table. Input + send -> `POST /api/conversation`
  (session_id null for a new chat; keep the returned id). Sending shows a typing
  indicator and disables send. **The chat never shows tool names, params, results
  or the word "trace"/"debug".**
- **Debug** (route `debug?sessionId={id}`): opened by tapping the Chat top-bar title
  5 times within 3 s (hidden gesture, documented in the README); Chat passes its
  current session id. Loads `GET /api/sessions/{id}/messages` (stateless; the
  backend stores every trace) and shows, per assistant turn, each ToolTrace:
  tool, params JSON, result JSON (pretty, monospace, scrollable), duration.
- Loading, empty and error states on all three screens. Errors show the backend's
  `ErrorOut.detail` when present; network errors show "Cannot reach the server"
  with Retry. A failed send keeps the typed text and shows Retry.

## Tests

- JVM unit (`app/src/test`): MockWebServer + the contract fixtures for every
  endpoint and error body; ViewModels with a fake repository (loading -> success,
  loading -> error), `kotlinx-coroutines-test`.
- Compose UI (`app/src/androidTest`, run on the emulator): ProductCard numbers equal
  the fixture literals; ComparisonTable columns; Chat never displays any ToolTrace
  `tool` name; 5 taps open Debug and it shows the trace.
- Commands: `./gradlew assembleDebug testDebugUnitTest` and, with the emulator
  running, `./gradlew connectedDebugAndroidTest`.

## Shared wiring (fixed before Wave 2 — do not change)

- `App.kt`: `AppContainer(baseUrl).repository` (lazy). Screens obtain it via
  `(LocalContext.current.applicationContext as App).container.repository` and build
  their ViewModel with a factory (`viewModel(factory = ...)`); ViewModels take a
  `Repository`-like interface or the class itself so tests can pass a fake.
- `MainActivity.kt` signatures: `ConversationsScreen(onOpenChat: (String?) -> Unit)`,
  `ChatScreen(sessionId: String?, onBack: () -> Unit, onOpenDebug: (String?) -> Unit)`,
  `DebugScreen(sessionId: String?, onBack: () -> Unit)`.

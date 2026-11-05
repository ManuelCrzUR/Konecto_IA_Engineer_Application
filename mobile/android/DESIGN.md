# Axel design contract (Sprint 5.5)

Visual source of truth for the Compose redesign. The approved canvas is in
`docs/design/*.dc.html` (static HTML with inline styles; read the markup for exact
spacing). Board → file: Style guide `Main`, Motion `Motion`, light palette
`LightTokens`, character `Character`, screens `Splash`, `Conversations`, `Search`,
`ChatEmpty`, `ChatLookup`, `ChatCompare`, `Debug`, `States` and their `Light*`
twins. `CONTRACT.md` still rules data, networking and **the number rule**
(show `JsonPrimitive.content`, never reformat).

## 1. Identity

- Assistant name: **Axel**. Tagline: "Series 76 actuator assistant".
- Character: an actuator housing with a face. The valve-stem knob on top makes a
  quarter turn (90°) while Axel thinks.

## 2. Color tokens

| Token | Dark (default) | Light |
|---|---|---|
| background | `#0E0E0E` | `#FAF8FC` |
| surface (cards, rows, inputs) | `#1D1D1D` | `#FFFFFF` |
| surfaceViolet (assistant bubble, chips, avatar body) | `#20152A` | `#F3EAFE` |
| divider / outline | `#2A2A2A` | `#E7E2EE` |
| primary | `#BD7BFF` | `#7B2CBF` |
| onPrimary | `#0E0E0E` | `#FFFFFF` |
| accent text (lilac edge / chip text) | `#D0ACE5` | `#6A3FA0` |
| textPrimary | `#FFFFFF` | `#16121C` |
| textSecondary | `#CCCCCC` | `#4A4458` |
| textTertiary (timestamps, hints) | `#8A8A8A` | `#6E6878` |
| caution | `#FFB86B` | `#A15C00` |
| cautionContainer | `#1D1D1D` + caution border | `#FFF7EC` + caution border |
| codeBackground (Debug JSON) | `#141414` | `#F6F3FA` |
| glow (focus, best match) | shadow 0/4/34/−1 `#412C64` | none (use 1 dp primary border) |

Caution is only for "Not CSA certified" and the number-guard badge.
Map the tokens onto a Material 3 `ColorScheme` (background, surface,
surfaceContainer = surfaceViolet, outlineVariant = divider, primary, onPrimary,
onSurface = textPrimary, onSurfaceVariant = textSecondary). Expose the extra tokens
(textTertiary, caution, cautionContainer, codeBackground, accentText) through a
small `AxelColors` `staticCompositionLocalOf`. Dynamic color stays off.

## 3. Type: DM Sans (bundled in `res/font`, OFL)

| Role | Size / weight | Use |
|---|---|---|
| title | 28 / 700, letter-spacing −0.01em | screen titles |
| partNumber | 20 / 700, −0.01em | product card header |
| body | 16 / 400, line height 1.5 | chat answers |
| keyFigure | 20–24 / 700, tabular numerals | "750 Nm" figures |
| label | 13 / 500 | field labels, section headers |
| code | 12 / 400, system monospace | Debug JSON |

Every technical number uses `fontFeatureSettings = "tnum"`.

## 4. Shapes and spacing

Radius: cards 28 dp, buttons and bubbles 20 dp (the assistant bubble has a 6 dp
bottom-start corner; the user bubble has a 6 dp bottom-end corner), tiles 16 dp,
chips fully rounded. Screen side padding is 16 dp. Touch targets are at least 48 dp.
The header is a distinct band: the surface color in light, and a background with a
bottom divider in dark. It holds the Axel avatar (32 dp), the title "Axel" and the
subtitle.

## 5. Axel avatar (`ui/axel/AxelAvatar.kt`)

Drawn on a `Canvas` in a 64×64 viewBox, scaled to the requested size.

```
body  rect x8 y16 w48 h40 rx16   fill surfaceViolet, stroke primary 2.5
knob  rect x26 y5 w12 h11 rx3    fill primary        (group pivot 32,10)
slot  rect x31 y3 w2 h6 rx1      fill background (dark #0E0E0E / light #FFFFFF)
eyes  circles (24,34) and (40,34) r4.5   fill textPrimary (dark #FFF / light #16121C)
smile path M23 45 Q32 52 41 45   stroke accentText (dark #D0ACE5 / light #7B2CBF) 3, round cap
```

States (`enum class AxelState { IDLE, THINKING, READY, PROBLEM }`):
- **IDLE:** both eyes blink (scaleY to 0.1 for about 120 ms) every ~4 s, with jitter.
- **THINKING:** the knob rotates 0° → 90° → 0° over 1.8 s, repeating (hold at 90°
  between 42% and 58% of the cycle). The eyes glance (+1.6, −1.6) at the same time.
- **READY:** a wider smile `M21 44 Q32 56 43 44`, cheeks (circles at (16,43) and
  (48,43), r3, primary at 35% alpha) and a small bounce (−5 dp, then −2 dp).
- **PROBLEM:** flat eyes (`M19.5 34h9`, `M35.5 34h9`, stroke 3) and a flat mouth
  `M24 47h16` in caution.

When the system animator scale is 0 ("Remove animations"), every state is static.

**Launcher icon:** an adaptive icon. The background is a solid `#20152A`. The
foreground is the idle Axel inside the 66 dp safe zone, in the dark colors. The
monochrome layer is the silhouette. The light variant appears in the in-app
splash only.

## 6. Screens

- **Splash:** the system SplashScreen (Axel icon on `#0E0E0E` / `#FAF8FC`), then a
  Compose route showing Axel (about 112 dp, IDLE), "Axel" as the title and the
  tagline. It pings `/health` and stays between 600 ms and 1.5 s. It is replaced by
  Conversations (popUpTo inclusive).
- **Conversations:** the header band (avatar, "Axel", "Your conversations") with a
  theme button (moon/sun icon) that opens a menu: Dark / Light / System, with a
  check on the current one. Below the header: a search field (pill, surface color,
  search icon, placeholder "Search conversations"). Then the rows: surface cards
  (radius 20) with the title (1 line, ellipsis) and a relative time in tertiary
  text. The FAB is extended ("New conversation"), with a primary background.
  Empty state: Axel IDLE with a hint.
- **Search mode:** a "N results" label, then "In titles" and "In messages"
  sections. Each result is a row with the title, the time and the snippet (the
  backend snippet as is, 2 lines; matched text in primary).
- **Chat:** a header with back, avatar and title "Axel". **5 taps on the title
  still open Debug** (`chat_title`). User bubble: primary-tinted, aligned to the
  end. Assistant: avatar (24–32 dp) plus a surfaceViolet bubble. Thinking:
  `AxelAvatar(THINKING)` with "Looking up the tables…" and 3 pulsing dots (1.2 s,
  staggered 0.15 s), tag `typing_indicator`. Offline / error: a banner with Retry
  and the avatar in PROBLEM. Empty chat: Axel, "Ask about Series 76 actuators"
  and 3–4 suggestion chips that send the query.
- **ProductCard:** radius 28, surface color. Header: the part number (20/700) and
  chips (voltage · phase, enclosure, and a caution chip "Not CSA certified" when
  `csaCertified == false`). Key-figure tiles (radius 16, surfaceViolet): label 13/500
  and value + unit in tnum. Other fields go in a list, and notes are expandable
  (`notes_toggle`). When `hasData == false`, the card says "No data in the
  catalog" instead of the fields.
- **ComparisonTable:** a horizontally scrollable table. The best match column has
  the glow (dark) or a primary border (light) and a "Best match" chip.
- **Debug:** a header with back, "Debug", a chip "N turns · M calls" and Refresh.
  One section per turn ("Turn 2 · \"query\""). Each tool call is a surface card
  with the tool name (monospace, primary), the duration, Params and Result
  (codeBackground, the result collapsed to 6 lines with "Show all N lines"). The
  number guard is a caution-bordered card "Number guard fired".

## 7. Motion (specs live in `NavMotion`, `ui/theme/Motion.kt`)

- Conversations <-> Chat: Material 3 shared X axis, 400 ms `FastOutSlowInEasing`.
  Enter: `slideInHorizontally { it / 4 }` + `fadeIn(tween(210, delayMillis = 90,
  LinearOutSlowInEasing))`. Exit: `slideOutHorizontally { -it / 4 }` +
  `fadeOut(tween(90, FastOutLinearInEasing))`. Pop reverses the directions.
  Predictive back follows the finger.
- Chat -> Debug: fade-through. Exit `fadeOut(tween(90))`; enter
  `fadeIn(tween(210, delayMillis = 90)) + scaleIn(initialScale = 0.92f,
  tween(300, FastOutSlowInEasing))`.
- Splash -> Conversations: a plain fade (300 ms).
- In-screen: new messages fade in and rise 12 dp. Expand/collapse takes 250 ms
  ease-out. List rows use `Modifier.animateItem()`. Animate only alpha and
  translation.

## 8. Search API (`GET /api/sessions?q=&limit=`)

The response is a list of `SessionOut` plus an optional `match`:
`{"where": "title" | "message", "snippet": "…"}`. `match` is null when `q` is
absent or empty, which is today's behavior. Matching is case-insensitive, over
the title and the message content. The most recently updated sessions come first.
`where` is "title" when the title matches, otherwise "message". The snippet is
about 80 characters around the first match, with "…" at a cut edge. The backend
never cuts inside a number.

## 9. Theme preference

`ThemePreferences` (DataStore Preferences, key `theme_mode`, values `SYSTEM`,
`LIGHT`, `DARK`; the default is `DARK`, the brand default). It is exposed as a
`Flow<ThemeMode>` from `AppContainer` and collected in `MainActivity`. The status
bar and navigation bar icons follow the resolved theme.

## 10. Kept from Sprint 5

All existing `testTag`s, the 5-tap Debug entry, `SavedStateHandle` session
restore, the routes `conversations`, `chat?sessionId=` and `debug?sessionId=`,
and the number rule.

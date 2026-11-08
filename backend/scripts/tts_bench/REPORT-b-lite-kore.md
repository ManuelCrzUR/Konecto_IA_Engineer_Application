# Text-to-speech comparison (D-54, Sprint 10 wave S1)

MP3 durations are estimates (bytes at 128 kbps); estimated costs use the D-54 prices.
First audio ready = time until playback could start (first sentence if split, else total).

| model | voice | lang | split | ok | TTFB s | first audio ready s | total s | audio s | real USD | est. USD | est. / 300 ch |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `google/gemini-3.8-flash-lite-tts` (b-lite-kore) | Kore | - | no | 2/2 | 5.32 | 6.82 | 6.82 | 48.2 |  | 0.010885 | 0.010205 |

## Samples

- `google/gemini-3.8-flash-lite-tts` / Kore / es1: /Users/manuelcruz/Desktop/Konecto Aplication/backend/scripts/tts_bench/audio/google_gemini-3.8-flash-lite-tts__Kore__es1__b-lite-kore.wav
- `google/gemini-3.8-flash-lite-tts` / Kore / es2: /Users/manuelcruz/Desktop/Konecto Aplication/backend/scripts/tts_bench/audio/google_gemini-3.8-flash-lite-tts__Kore__es2__b-lite-kore.wav

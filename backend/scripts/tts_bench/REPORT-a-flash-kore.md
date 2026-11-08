# Text-to-speech comparison (D-54, Sprint 10 wave S1)

MP3 durations are estimates (bytes at 128 kbps); estimated costs use the D-54 prices.
First audio ready = time until playback could start (first sentence if split, else total).

| model | voice | lang | split | ok | TTFB s | first audio ready s | total s | audio s | real USD | est. USD | est. / 300 ch |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `google/gemini-3.8-flash-tts` (a-flash-kore) | Kore | - | no | 2/2 | 7.27 | 8.71 | 8.71 | 44.6 | 0.003853 | 0.010066 | 0.009437 |

## Samples

- `google/gemini-3.8-flash-tts` / Kore / es1: /Users/manuelcruz/Desktop/Konecto Aplication/backend/scripts/tts_bench/audio/google_gemini-3.8-flash-tts__Kore__es1__a-flash-kore.wav
- `google/gemini-3.8-flash-tts` / Kore / es2: /Users/manuelcruz/Desktop/Konecto Aplication/backend/scripts/tts_bench/audio/google_gemini-3.8-flash-tts__Kore__es2__a-flash-kore.wav

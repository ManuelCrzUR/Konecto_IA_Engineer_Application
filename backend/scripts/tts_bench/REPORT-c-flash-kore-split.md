# Text-to-speech comparison (D-54, Sprint 10 wave S1)

MP3 durations are estimates (bytes at 128 kbps); estimated costs use the D-54 prices.
First audio ready = time until playback could start (first sentence if split, else total).

| model | voice | lang | split | ok | TTFB s | first audio ready s | total s | audio s | real USD | est. USD | est. / 300 ch |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `google/gemini-3.8-flash-tts` (c-flash-kore-split) | Kore | - | yes | 2/2 | 4.65 | 5.28 | 13.57 | 48.3 | 0.003780 | 0.010903 | 0.010221 |

## Samples

- `google/gemini-3.8-flash-tts` / Kore / es1: /Users/manuelcruz/Desktop/Konecto Aplication/backend/scripts/tts_bench/audio/google_gemini-3.8-flash-tts__Kore__es1__c-flash-kore-split.wav
- `google/gemini-3.8-flash-tts` / Kore / es2: /Users/manuelcruz/Desktop/Konecto Aplication/backend/scripts/tts_bench/audio/google_gemini-3.8-flash-tts__Kore__es2__c-flash-kore-split.wav

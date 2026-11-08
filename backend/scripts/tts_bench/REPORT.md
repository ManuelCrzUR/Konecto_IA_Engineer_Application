# Text-to-speech comparison (D-54, Sprint 10 wave S1)

MP3 durations are estimates (bytes at 128 kbps); estimated costs use the D-54 prices.

| model | voice | ok | TTFB s | total s | audio s | real USD | est. USD | est. / 300 ch |
|---|---|---|---|---|---|---|---|---|
| `google/gemini-3.8-flash-tts` | Kore | 4/4 | 7.18 | 8.17 | 87.8 | 0.019895 | 0.019819 | 0.010233 |
| `elevenlabs/eleven-flash-v2.5` | sarah | 4/4 | 0.80 | 1.06 | 76.1 | 0.023240 | 0.023240 | 0.012000 |
| `elevenlabs/eleven-multilingual-v2` | sarah | 4/4 | 1.32 | 1.87 | 70.4 | 0.046480 | 0.046480 | 0.024000 |

## Samples

- `google/gemini-3.8-flash-tts` / Kore / es1: /Users/manuelcruz/Desktop/Konecto Aplication/backend/scripts/tts_bench/audio/google_gemini-3.8-flash-tts__Kore__es1.wav
- `google/gemini-3.8-flash-tts` / Kore / es2: /Users/manuelcruz/Desktop/Konecto Aplication/backend/scripts/tts_bench/audio/google_gemini-3.8-flash-tts__Kore__es2.wav
- `google/gemini-3.8-flash-tts` / Kore / en1: /Users/manuelcruz/Desktop/Konecto Aplication/backend/scripts/tts_bench/audio/google_gemini-3.8-flash-tts__Kore__en1.wav
- `google/gemini-3.8-flash-tts` / Kore / en2: /Users/manuelcruz/Desktop/Konecto Aplication/backend/scripts/tts_bench/audio/google_gemini-3.8-flash-tts__Kore__en2.wav
- `elevenlabs/eleven-flash-v2.5` / sarah / es1: /Users/manuelcruz/Desktop/Konecto Aplication/backend/scripts/tts_bench/audio/elevenlabs_eleven-flash-v2.5__sarah__es1.mp3
- `elevenlabs/eleven-flash-v2.5` / sarah / es2: /Users/manuelcruz/Desktop/Konecto Aplication/backend/scripts/tts_bench/audio/elevenlabs_eleven-flash-v2.5__sarah__es2.mp3
- `elevenlabs/eleven-flash-v2.5` / sarah / en1: /Users/manuelcruz/Desktop/Konecto Aplication/backend/scripts/tts_bench/audio/elevenlabs_eleven-flash-v2.5__sarah__en1.mp3
- `elevenlabs/eleven-flash-v2.5` / sarah / en2: /Users/manuelcruz/Desktop/Konecto Aplication/backend/scripts/tts_bench/audio/elevenlabs_eleven-flash-v2.5__sarah__en2.mp3
- `elevenlabs/eleven-multilingual-v2` / sarah / es1: /Users/manuelcruz/Desktop/Konecto Aplication/backend/scripts/tts_bench/audio/elevenlabs_eleven-multilingual-v2__sarah__es1.mp3
- `elevenlabs/eleven-multilingual-v2` / sarah / es2: /Users/manuelcruz/Desktop/Konecto Aplication/backend/scripts/tts_bench/audio/elevenlabs_eleven-multilingual-v2__sarah__es2.mp3
- `elevenlabs/eleven-multilingual-v2` / sarah / en1: /Users/manuelcruz/Desktop/Konecto Aplication/backend/scripts/tts_bench/audio/elevenlabs_eleven-multilingual-v2__sarah__en1.mp3
- `elevenlabs/eleven-multilingual-v2` / sarah / en2: /Users/manuelcruz/Desktop/Konecto Aplication/backend/scripts/tts_bench/audio/elevenlabs_eleven-multilingual-v2__sarah__en2.mp3

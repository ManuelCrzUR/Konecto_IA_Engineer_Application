# Text-to-speech comparison (D-54, Sprint 10 wave S1)

MP3 durations are estimates (bytes at 128 kbps); estimated costs use the D-54 prices.
First audio ready = time until playback could start (first sentence if split, else total).

| model | voice | lang | split | ok | TTFB s | first audio ready s | total s | audio s | real USD | est. USD | est. / 300 ch |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `elevenlabs/eleven-flash-v2.5` (d-eleven-laura-es) | laura | es | no | 1/1 | 1.01 | 1.29 | 1.29 | 12.0 |  | 0.003800 | 0.012000 |

## Samples

- `elevenlabs/eleven-flash-v2.5` / laura / es1: /Users/manuelcruz/Desktop/Konecto Aplication/backend/scripts/tts_bench/audio/elevenlabs_eleven-flash-v2.5__laura__es1__d-eleven-laura-es.mp3

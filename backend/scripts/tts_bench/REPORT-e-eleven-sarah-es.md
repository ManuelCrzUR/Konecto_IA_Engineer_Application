# Text-to-speech comparison (D-54, Sprint 10 wave S1)

MP3 durations are estimates (bytes at 128 kbps); estimated costs use the D-54 prices.
First audio ready = time until playback could start (first sentence if split, else total).

| model | voice | lang | split | ok | TTFB s | first audio ready s | total s | audio s | real USD | est. USD | est. / 300 ch |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `elevenlabs/eleven-flash-v2.5` (e-eleven-sarah-es) | sarah | es | no | 1/1 | 0.75 | 0.83 | 0.83 | 13.9 |  | 0.003800 | 0.012000 |

## Samples

- `elevenlabs/eleven-flash-v2.5` / sarah / es1: /Users/manuelcruz/Desktop/Konecto Aplication/backend/scripts/tts_bench/audio/elevenlabs_eleven-flash-v2.5__sarah__es1__e-eleven-sarah-es.mp3

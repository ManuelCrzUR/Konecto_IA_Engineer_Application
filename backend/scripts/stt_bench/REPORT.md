# Speech-to-text comparison (D-53, Sprint 9 wave V1)

| model | part numbers exact | after normalization | errors | mean latency s | cost USD |
|---|---|---|---|---|---|
| `openai/whisper-large-v3-turbo` | 1/7 | 5/7 | 0 | 1.91 | 0.000160 |
| `openai/whisper-large-v3` | 0/7 | 3/7 | 0 | 2.37 | 0.000360 |
| `openai/gpt-4o-mini-transcribe` | 1/7 | 4/7 | 0 | 0.88 | 0.001374 |
| `mistralai/voxtral-mini-transcribe-3-0` | 1/7 | 4/7 | 0 | 0.93 | 0.002567 |
| `google/gemini-3.5-transcribe` | 1/7 | 5/7 | 0 | 2.48 | 0.004650 |

## Transcripts

- `openai/whisper-large-v3-turbo` / s1 (torque on off del siete seis cuatro A cero cero guion ... barra A (es-MX)): ' ¿Cuál es el torque on-off del 764A00-113000000, barra A?'
- `openai/whisper-large-v3-turbo` / s2 (Dame el LRA a cincuenta hertz del 763B00-11330C00/A (es-ES)): ' Dame el LRA 50 Hz del 763 B0011330 C00 barra oblicua a.'
- `openai/whisper-large-v3-turbo` / s3 (What is the duty cycle of 766A00-11320000/A? (en)): ' What is the duty cycle of 766 A00 11320,000/A?'
- `openai/whisper-large-v3-turbo` / s4 (explosionproof 24 V modulante, al menos 100 Nm (es-MX)): ' Busco un actuador Explosion Proof de 24 voltios modulante con al menos 100 Nm.'
- `openai/whisper-large-v3-turbo` / s5 (Compare 764X30-11320000/A and 765A00-11320000/A (en)): ' Compare 764 by 30-11,320,000 slash A and 765 A00 11,320,000 slash A.'
- `openai/whisper-large-v3-turbo` / s6 (¿Qué potencia tiene el 761A00-11330C00 barra A? (es-ES)): ' ¿Qué potencia tiene el 761 A0011330 C00 barra A?'
- `openai/whisper-large-v3-turbo` / s7 (y cuántos arranques por hora tiene el 762X30 (es-MX)): ' ¿Y cuántos arranques por hora tiene el 762 por 30?'
- `openai/whisper-large-v3` / s1 (torque on off del siete seis cuatro A cero cero guion ... barra A (es-MX)): ' ¿Cuál es el torque ON-OFF del 764A00-113000-A?'
- `openai/whisper-large-v3` / s2 (Dame el LRA a cincuenta hertz del 763B00-11330C00/A (es-ES)): ' Dame el LRA 50Hz del 763B001330C00 barra oblicua A.'
- `openai/whisper-large-v3` / s3 (What is the duty cycle of 766A00-11320000/A? (en)): ' What is the duty cycle of 766A0011320000?'
- `openai/whisper-large-v3` / s4 (explosionproof 24 V modulante, al menos 100 Nm (es-MX)): ' Busco un actuador ExplosionProf de 24 voltios modulante con al menos 100 Nm.'
- `openai/whisper-large-v3` / s5 (Compare 764X30-11320000/A and 765A00-11320000/A (en)): ' Compare 764 by 30-11320000-A and 765A0011320000-A.'
- `openai/whisper-large-v3` / s6 (¿Qué potencia tiene el 761A00-11330C00 barra A? (es-ES)): ' ¿Qué potencia tiene el 761A0011330C00-A?'
- `openai/whisper-large-v3` / s7 (y cuántos arranques por hora tiene el 762X30 (es-MX)): ' ¿Y cuántos arranques por hora tiene el 762 por 30?'
- `openai/gpt-4o-mini-transcribe` / s1 (torque on off del siete seis cuatro A cero cero guion ... barra A (es-MX)): '¿Cuál es el torque on-off del 764A00-1130000/0/A?'
- `openai/gpt-4o-mini-transcribe` / s2 (Dame el LRA a cincuenta hertz del 763B00-11330C00/A (es-ES)): 'DMLLL a cincuenta hertz del setecientos sesenta y tres B0011330C00/oblicua.'
- `openai/gpt-4o-mini-transcribe` / s3 (What is the duty cycle of 766A00-11320000/A? (en)): 'What is the duty cycle of 766A001132000/A?'
- `openai/gpt-4o-mini-transcribe` / s4 (explosionproof 24 V modulante, al menos 100 Nm (es-MX)): 'Busco un actuador explosión prof de 24 voltios modulante con al menos 100 newton metro.'
- `openai/gpt-4o-mini-transcribe` / s5 (Compare 764X30-11320000/A and 765A00-11320000/A (en)): 'Compare 764 by 30-11,320,000/A and 765A0011,320,000/A.'
- `openai/gpt-4o-mini-transcribe` / s6 (¿Qué potencia tiene el 761A00-11330C00 barra A? (es-ES)): '¿Qué potencia tiene el 761A0011330C00/A?'
- `openai/gpt-4o-mini-transcribe` / s7 (y cuántos arranques por hora tiene el 762X30 (es-MX)): '¿Y cuántos arranques por hora tiene el 762x30?'
- `mistralai/voxtral-mini-transcribe-3-0` / s1 (torque on off del siete seis cuatro A cero cero guion ... barra A (es-MX)): '¿Cuál es el torque on-off del 764A00-11300000/A?'
- `mistralai/voxtral-mini-transcribe-3-0` / s2 (Dame el LRA a cincuenta hertz del 763B00-11330C00/A (es-ES)): 'Dame el LRA50X del 763B0011330C00/obliqua.'
- `mistralai/voxtral-mini-transcribe-3-0` / s3 (What is the duty cycle of 766A00-11320000/A? (en)): 'What is the duty cycle of 766A0011320000/A?'
- `mistralai/voxtral-mini-transcribe-3-0` / s4 (explosionproof 24 V modulante, al menos 100 Nm (es-MX)): 'Busco un actuador Explosion Pro de 24 voltios modulante con al menos 100 Nm.'
- `mistralai/voxtral-mini-transcribe-3-0` / s5 (Compare 764X30-11320000/A and 765A00-11320000/A (en)): 'Compare 764 by 30 - 11,320,000/A and 765A0011,320,000/A.'
- `mistralai/voxtral-mini-transcribe-3-0` / s6 (¿Qué potencia tiene el 761A00-11330C00 barra A? (es-ES)): '¿Qué potencia tiene el 761-0011-330-C00-A?'
- `mistralai/voxtral-mini-transcribe-3-0` / s7 (y cuántos arranques por hora tiene el 762X30 (es-MX)): '¿Y cuántos arranques por hora tiene el 762 por 30?'
- `google/gemini-3.5-transcribe` / s1 (torque on off del siete seis cuatro A cero cero guion ... barra A (es-MX)): '¿Cuál es el torque on-off del 764A00-11300000/A?'
- `google/gemini-3.5-transcribe` / s2 (Dame el LRA a cincuenta hertz del 763B00-11330C00/A (es-ES)): 'L R A 50 Hz del 763B0011330C00/A'
- `google/gemini-3.5-transcribe` / s3 (What is the duty cycle of 766A00-11320000/A? (en)): 'What is the duty cycle of 766A0011320000/A?'
- `google/gemini-3.5-transcribe` / s4 (explosionproof 24 V modulante, al menos 100 Nm (es-MX)): 'Busco un actuador Explosion Proof de 24 V modulante con al menos 100 N m.'
- `google/gemini-3.5-transcribe` / s5 (Compare 764X30-11320000/A and 765A00-11320000/A (en)): 'Compare 764/30-11,320,000/A and 765A0011,320,000/A.'
- `google/gemini-3.5-transcribe` / s6 (¿Qué potencia tiene el 761A00-11330C00 barra A? (es-ES)): '¿Qué potencia tiene el 761A0011330C00/A?'
- `google/gemini-3.5-transcribe` / s7 (y cuántos arranques por hora tiene el 762X30 (es-MX)): '¿Y cuántos arranques por hora tiene el 762 por 30?'

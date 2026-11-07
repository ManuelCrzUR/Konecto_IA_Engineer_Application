# Series 76 Technical Assistant: contexto del proyecto

## 1. Qué es esto

Prueba técnica "AI Engineer Assessment" de Konecto. Hay que construir un asistente técnico para ingenieros de planta que eligen y consultan **actuadores eléctricos Series 76**:

- **Backend** en Python: FastAPI + agente LangChain + PostgreSQL.
- **App móvil nativa** (Kotlin + Jetpack Compose o Swift + SwiftUI).

Plazo: una semana desde que llegó el correo del enunciado.

**Cómo se evalúa:** se asume que la IA escribe el código. Lo que se evalúa es que el desarrollador **entienda lo construido y pueda defender las decisiones** en una entrevista de seguimiento. La **reproducibilidad es eliminatoria**: si no pueden correrlo siguiendo el README, no avanzan. Konecto lo probará con casos propios, así que la solución debe generalizar.

Idioma: conversación conmigo en español. Código, comentarios, commits y README en inglés (los evaluadores leen inglés).

## 1.1 Principios: modular y KISS

- **Modular:** módulos pequeños, con una sola responsabilidad y un solo contrato (entradas y salidas). Cada módulo cabe en ~150 líneas y se prueba por separado.
- **KISS:** la opción más simple que cumpla el enunciado. Sin ORM, sin interfaces abstractas que no tengan una segunda implementación, sin grafo propio de LangGraph.
- **Auto-recuperable:** la cadena PDF → OCR → JSON → Postgres. Si falta o se corrompe una etapa, el sistema vuelve a la anterior y la reconstruye. Nada se da por hecho.

## 2. Alcance

**Dentro:** extracción del PDF y su validación, base de datos de consulta, tools, agente, selección de LLM, casos borde, set de evaluación, `cli.py`, API FastAPI (`POST /api/conversation` y sesiones), conversaciones persistidas en Postgres, Docker Compose y app Android (Kotlin + Compose). El plan de entrega tiene 7 sprints más el 5.5 de rediseño (`docs/ARCHITECTURE.md` §11); el 6 es de seguridad (prompting incluido) y el 7 de entrega.

**Solo hueco (opcional):** login y voz. Hoy solo existen los ganchos (`user_id` nullable y transcripción en el dispositivo); se implementan solo si sobra tiempo.

El agente se invoca como `run_agent(query, history=[])`. La API le pasa el historial guardado en Postgres.

## 3. Requisitos duros del enunciado

- REST en **FastAPI**. Contrato fijo: `POST /api/conversation` con request `{session_id?, query}` y response `{session_id, answer, ...}`. El resto de la respuesta lo diseñamos nosotros: datos de producto estructurados para la app y traza de tools para la pantalla Debug.
- Agente con **LangChain** y **al menos una Tool personalizada** que consulte los datos de las tablas.
- **PostgreSQL** local con Docker Compose. **pgvector** solo si hace falta búsqueda semántica.
- Conversaciones persistidas (sobreviven a un reinicio). Sprint 4.
- Script de ingesta (p. ej. `ingest.py`) que procese el PDF crudo.
- **Los números que ve el usuario deben coincidir con las tablas. El LLM no inventa ni recuerda números.**
- Modelos vía **OpenRouter**, configurables por variables de entorno, con la elección explicada en el README por tarea.
- **Presupuesto de la key de OpenRouter: USD 10, límite duro, sin recarga.** Para experimentar con la extracción se puede usar la API gratuita de Google AI Studio.
- Casos borde manejados: part numbers inválidos, datos faltantes, consultas ambiguas, requisitos que ningún modelo cumple.
- Entregables: repo con código de backend y app, script de ingesta, datos procesados (o instrucciones), `Dockerfile`, `docker-compose.yml`, `.env.example` sin keys, README completo (setup, backend, ingesta, app, diseño y trade-offs, opcionales) y **la carpeta de configuración de IA (`.claude/`) commiteada**.
- Opcionales (solo si sobra tiempo): login con email/contraseña y token, mensajes de voz.

## 4. Los datos

Fuente de verdad de los números: `series_76_electric_data.pdf`. El `series_76_summary.pdf` solo da contexto de negocio y **no** es fuente de números.

**Hechos verificados del PDF:**

- 4 páginas, **sin capa de texto**: `pdfplumber` y `pdftotext` no devuelven palabras. Cada página es una imagen incrustada de unos 110 a 180 ppi, así que hace falta OCR o un modelo de visión.
- 7 tablas con 4 esquemas de columnas distintos:
  - Monofásico 110V/220V: columnas on/off y modulante, velocidad/FLA/LRA a 60 y 50 Hz.
  - Trifásico 220V: torque y duty cycle únicos, con columnas de cycles/h y starts/h.
  - 24V AC/DC on/off.
  - 24V DC modulante. Las dos tablas de 24V no tienen columnas de Hz.
- Conteo de filas esperado (contado a ojo, **verificar**): Weatherproof 110V = 11, 220V monofásico = 16, 220V trifásico = 11; Explosionproof 24V on/off = 5, 24V modulante = 5, 110V = 10, 220V = 10. Total 68.
- Encabezados de dos niveles; Motor Power aparece una sola vez por grupo de filas (celdas combinadas); separador de miles con coma.
- La tabla trifásica tiene **4 filas N/A** (761A, 761B, 762A, 762B): son part numbers válidos sin datos.
- Los part numbers `766A`, `766B`, `767A`, `767B` y `767C` (220V monofásico weatherproof) terminan en `/A*`: "Sizes 6 and 7 are not CSA Certified".
- El PDF es un **subconjunto**: no hay 24V weatherproof ni trifásico explosionproof. Si el usuario pregunta por eso, el agente dice que no hay datos y no infiere.
- Enclosure: *Weatherproof* (CSA, CE y UKCA) o *Explosionproof* (CSA). El summary menciona IECEx/ATEX, pero las tablas dicen CSA: **mandan las tablas**.
- Notas de las tablas (tolerancias de voltaje ±10% y de frecuencia ±5%, duty cycle según IEC 60034-1, clasificación de área peligrosa de las tablas explosionproof) se guardan como metadatos de la sección.
- Campos: Base Part Number, torque (in-lbs y Nm), duty cycle S4%, cycles/h (on/off), starts/h (modulante), velocidad en segundos para 90° (60 y 50 Hz), FLA, LRA y potencia del motor en W.

**Reglas de extracción (valen para todo extractor):**

- Valores tal como están impresos. No calcular, no convertir unidades, no "corregir".
- Quitar comas de miles. N/A pasa a `null`. El asterisco pasa a un flag `csa_certified=false` y el part number queda limpio.
- Una fila por (part number, tabla), con campos nullable.
- Enclosure, voltaje, fase y servicio salen del **título de la sección**, no del part number. Los sufijos (`11300000`=110V, `11320000`=220V 1φ, `11330C00`=220V 3φ, `11380000`=24V on/off, `11370000`=24V modulante) sirven solo como verificación cruzada.

## 5. Estrategia de extracción

**Cascada auto-reparable** (`ensure_data()`; corre al arrancar la API, en la CLI y en `ingest.py`):

1. Si Postgres tiene exactamente las filas del JSON (68), no se hace nada. Contar filas, no "no está vacía": así se detectan cargas parciales.
2. Si no, y `data/processed/actuators.json` existe y pasa las validaciones, se carga a Postgres con upsert idempotente.
3. Si no, se extrae del PDF crudo: OCR local (RapidOCR) sobre recortes 2×, marcado de celdas sospechosas, escalado a visión (OpenRouter, `EXTRACT_LLM_MODEL`) solo de las tablas marcadas, validación, escritura del JSON (sin sobrescribir uno existente salvo con `--force`) y carga.
4. Si la validación falla, se aborta con un mensaje claro: no se carga nada dudoso.

**Extractor actual: híbrido** (decisión D-01 en `docs/DECISIONS.md`). Hay un solo extractor: no hay interfaces `DataSource`/`Extractor` ni variable `EXTRACTORS` (D-02). El modelo pydantic `Actuator` es el contrato único (`docs/ARCHITECTURE.md` §2).

**Validaciones comunes** (sobre la salida de cualquier extractor): conteo de filas por tabla, parseo numérico, razón in-lbs/Nm ≈ 8,85 (±5%), FLA ≤ LRA, velocidad a 60 Hz ≤ 50 Hz (solo warning), duty cycle entre 0 y 100, regex del part number. Si fallan, abortar con mensaje claro: no cargar datos dudosos.

**Benchmark** (`Konecto OCR/bench`, resultados en su `REPORT.md`, contra el golden file): visión por tabla (B) dio 100%, pero requiere key y tokens en cada corrida. RapidOCR (E) dio 99,45%, offline y determinista. Tesseract (40–55% de celdas) se descartó. El híbrido dio 100% en simulación; la llamada real a OpenRouter sigue pendiente (ver §10).

## 6. Arquitectura propuesta

La fuente de verdad del diseño es **`docs/ARCHITECTURE.md`** (en inglés, para los evaluadores). Este es el árbol resumido; si difiere, manda el documento.

```
backend/
├── pyproject.toml
├── app/
│   ├── domain/models.py            # Actuator (único contrato), Product, ToolTrace
│   ├── ingestion/{ocr,flags,escalate,normalize,validate,pipeline,store_json}.py
│   ├── db/{schema.sql,connection.py,actuators_repo.py,sessions_repo.py}
│   ├── bootstrap.py                # ensure_data()
│   ├── agent/{tools,llm,prompts,agent,response}.py
│   └── api/{main.py,schemas.py,deps.py,routes_conversation.py,routes_sessions.py}
├── cli.py   ingest.py
├── data/{raw/series_76_electric_data.pdf, processed/actuators.json}
├── bench/   eval/   tests/
mobile/android/
docs/{ARCHITECTURE.md, DECISIONS.md, TOOLING.md}
docker-compose.yml  Dockerfile  Makefile  .env.example  README.md
```

**Reglas de capas:** `repository` no conoce el agente; las tools no conocen el LLM; el agente solo conoce las tools. Cada capa se prueba sola. Los tests no llaman a un LLM real.

**Base de datos:**

- Columnas tipadas (torque, voltaje, fase, enclosure, servicio, etc.), no un blob JSON: el filtrado de la recomendación depende de eso.
- Carga idempotente con `INSERT ... ON CONFLICT (part_number) DO UPDATE`.
- Compose con volumen para `pgdata` y `depends_on` con healthcheck (`pg_isready`).
- La API crea las tablas si no existen y carga los datos si `actuators` está vacía. `ingest.py` queda como comando manual con `--reset`.
- Imagen con pgvector solo si se decide usar búsqueda vectorial (probablemente no hace falta: las consultas son filtros numéricos).
- Más adelante: tablas `sessions` y `messages` (con datos de producto y traza de tools en JSON).

**Tools** (SQL parametrizado; el LLM nunca escribe SQL):

- `get_actuator(part_number)`: normaliza la entrada y devuelve una de tres salidas: encontrado con datos, **encontrado sin datos** (filas N/A) o no encontrado con sugerencias cercanas. Si el part number es parcial y coincide con varios, devuelve los candidatos.
- `search_actuators(requisitos)`: filtra por torque mínimo (con parámetro de unidad Nm o in-lbs), voltaje, fase, enclosure, servicio, velocidad máxima y duty cycle. Ordena por el más ajustado que cumpla. Si no hay resultados, devuelve qué restricción lo impidió y el valor más cercano disponible.
- `describe_catalog()`: voltajes, enclosures y rangos de torque disponibles (para consultas ambiguas).

**Agente y respuesta:**

- Los datos de producto de la respuesta los arma el código desde lo que devolvieron las tools. El LLM solo redacta texto.
- Guardia opcional: verificar que cada número del texto aparezca en los resultados de las tools.
- Capturar la traza de cada ejecución (tool, parámetros, resultado) para la pantalla Debug.

**LLM:** `get_llm(task)` en `app/llm.py` (D-19) lee `LLM_BASE_URL`, `LLM_API_KEY` y un modelo por tarea: `AGENT_MODEL` (agente) y `EXTRACT_LLM_MODEL` (escalado a visión). OpenRouter es el valor por defecto; como usa el formato de OpenAI, se puede cambiar a otra key para desarrollo. Nunca commitear keys.

## 7. Orden de construcción y paralelización

1. Modelo `Actuator` + JSON verificado (provisional de ~10 filas mientras tanto).
2. Postgres con compose y carga idempotente.
3. `repository.py` con tests.
4. Tools con tests, sin LLM.
5. `get_llm()` + agente + prompt.
6. Capa de respuesta y trazas.
7. Set de evaluación (20 a 30 preguntas: consulta puntual, recomendación, part number inválido, N/A, requisito imposible, ambigüedad, dato inexistente en el subconjunto) y `cli.py`.
8. Después: persistencia de conversaciones, API, app, Docker/README, prueba desde cero en máquina limpia.

**Paralelizable tras fijar contratos:** pista A extracción (`ingestion/`), B base de datos (`db/`), C tools (`agent/tools.py`), D LLM + agente + evaluación (`agent/`). Una pista por carpeta para evitar conflictos.

- Fase 0 (secuencial): modelo `Actuator`, `schema.sql`, firmas de `repository` y tools, este `CLAUDE.md`.
- Los worktrees nuevos nacen de la rama por defecto del remoto: hacer push de los contratos antes, o configurar `worktree.baseRef` en `"head"`.
- Copiar `.env` a los worktrees con `.worktreeinclude`; ignorar `.claude/worktrees/` en `.gitignore`.
- Fase 2 (secuencial): integrar, correr el set de evaluación con datos reales y corregir.

## 8. Convenciones

- Python con type hints, pydantic para modelos, pytest para tests.
- Cada módulo declara su contrato (entradas y salidas) antes de implementarse.
- Tests de tools deterministas y sin LLM; el set de evaluación del agente usa un modelo barato mientras se itera y el bueno solo en la corrida final.
- Mantener `docs/DECISIONS.md` con cada decisión y su trade-off (extractor elegido, columnas tipadas, tools, modelos). El desarrollador tiene que poder explicarlas en la entrevista.
- Al terminar cada pieza, explicar brevemente qué hace y por qué se hizo así.

## 9. Prohibido

- Que el LLM invente, recuerde o calcule números técnicos.
- Que el LLM escriba SQL libre.
- Commitear keys o `.env`.
- Usar la key de OpenRouter para pruebas sin preguntar primero.
- Sobrescribir `actuators.json` en silencio.
- Cargar a Postgres datos que no pasaron las validaciones.
- Modificar el PDF original (trabajar con copias).

## 10. Decisiones

**Decidido** (detalle en `docs/DECISIONS.md`):

- Plataforma móvil: Android (Kotlin + Compose) (D-13).
- Extractor: híbrido, RapidOCR con escalado de tablas marcadas a visión (D-01).
- pgvector no hace falta: las consultas son filtros numéricos.
- `session_id` inexistente: 404 (D-09).

**Pendiente:**

- Sprint 8 en curso (plan y estado por ola en `docs/plans/SPRINT-8.md`): correcciones de la evaluación externa, login (D-43) y voz (D-48).

- (Hecho, Sprint 8 ola 1) Llamada real a OpenRouter para el escalado: 4 tablas con visión, salida idéntica al JSON commiteado (D-49).
- (Decidido 2026-11-06) No se prueba la regla de marcado con otros PDFs: el enunciado solo pide este PDF. Queda como limitación conocida en README y D-01.
- Opcionales implementados en el Sprint 8: login (D-43, backend ola 2, app ola 4) y voz en el dispositivo (D-48, ola 4). Falta la puerta final (ola 5).

# Plan: arquitectura completa, modular y simple (Series 76 Technical Assistant)

## Context

El repo solo tiene configuración de IA (`.claude/`, `.mcp.json`, `skills-lock.json`), `CLAUDE.md`, `.gitignore` y `docs/TOOLING.md`. No hay código. Este plan fija la arquitectura de punta a punta (datos, backend, agente, API, app Android) antes de implementar, con tres reglas del desarrollador:

1. **Modular**: módulos pequeños, una responsabilidad y un contrato cada uno, conectados entre sí.
2. **KISS**: la opción más simple que cumpla el enunciado. Funciones antes que jerarquías; sin ORM; sin LangGraph propio.
3. **Reproducible y auto-recuperable**: `PDF → OCR → JSON → Postgres (Docker)`. Si algo falta o se corrompe, el sistema vuelve a la fuente anterior y lo reconstruye. Nada se asume ya hecho.

Decisiones tomadas con el desarrollador: **Android (Kotlin + Compose)**; **login y voz: solo dejar el hueco en el diseño** (no implementar ahora); el extractor OCR (`extract.py`, `flag_cells.py`) vive fuera del repo y se copia a `ingestion/` al implementar (sin tocar el original).

Lo que el enunciado fija y la arquitectura debe cumplir: FastAPI con `POST /api/conversation` (`{session_id?, query}` → `{session_id, answer, ...}`); agente LangChain con ≥1 tool que consulte las tablas; Postgres en Docker Compose; historial por `session_id` que sobrevive al reinicio; los números salen de las tablas, nunca del LLM; casos borde (PN inválido, datos faltantes, ambigüedad, requisito imposible); app con 3 pantallas (Conversaciones, Chat, Debug); `Dockerfile`, `docker-compose.yml`, `.env.example`, README completo y `.claude/` commiteado. Key de OpenRouter: USD 10, límite duro.

## 1. Vista general

```
 Android app ──HTTP──► FastAPI (api/) ──► agent/ ──► tools ──► db/actuators_repo ──► Postgres
   Chat / Conversaciones / Debug            │                                          ▲
                                            └─► db/sessions_repo (sessions, messages) ─┤
 PDF ► ingestion/ (OCR+flags+escala) ► actuators.json ► bootstrap.ensure_data() ───────┘
```

Dependencias solo hacia abajo: `api → agent → db/domain`; `bootstrap → ingestion + db`; `ingestion → domain`; `db → domain`. Nadie importa hacia arriba. Los puntos de entrada (`cli.py`, `ingest.py`, `api/main.py`) no tienen lógica.

## 2. Datos: cadena auto-reparable

```
 ensure_data() (corre al arrancar API, CLI e ingest.py)
  1. ¿COUNT(*) en Postgres == filas del JSON y el JSON es válido?  → listo
  2. Si no: ¿actuators.json existe y pasa validate()?               → upsert a Postgres
  3. Si no: PDF → OCR → flags → escalado → validate() → escribir JSON → upsert
  4. Si validate() falla: abortar con mensaje claro; no cargar datos dudosos
```

- "Tiene datos" = conteo exacto, no "no vacía": detecta cargas parciales.
- Upsert idempotente (`ON CONFLICT (base_part_number) DO UPDATE`): repetirlo no duplica ni rompe.
- El JSON no se sobrescribe sin `--force` (CLAUDE.md §9). El camino normal (JSON commiteado) no necesita internet ni key.
- OpenRouter solo en el paso 3 y solo para tablas marcadas (extractor actual: RapidOCR offline sobre recortes 2×; celda sospechosa si confianza < 0.9, ceros iniciales o falla un validador; esas tablas completas van a Sonnet 5.5). Sin key: falla listando las celdas dudosas.
- Pendientes del extractor: llamada real a OpenRouter (hoy simulada; pedir permiso antes de gastar, CLAUDE.md §9) y probar con otros PDFs.

**Esquema de `actuators`** (columnas tipadas; una fila por (part number, tabla); un solo PN tiene sufijo de voltaje, así que `base_part_number` es único):
`base_part_number`, `enclosure` (weatherproof/explosionproof), `voltage` (24/110/220), `current_type`/`phase` (ac_dc, 1, 3), `service` (on_off, modulating, both), `torque_inlbs`, `torque_nm`, `duty_cycle_pct`, `cycles_per_hour`, `mod_torque_inlbs`, `mod_torque_nm`, `mod_duty_cycle_pct`, `starts_per_hour`, `speed_60hz_s`, `speed_50hz_s`, `fla_60hz`, `fla_50hz`, `lra_60hz`, `lra_50hz`, `motor_power_w`, `csa_certified`, `certifications` (texto), `has_data`, `table_notes` (jsonb: tolerancias, IEC 60034-1, área peligrosa).
Punto a fijar en Fase 0: la tabla trifásica trae **un solo** torque y duty para ambos servicios. Recomendación: guardarlo en las columnas on/off **y** en las de modulating (valor impreso, sin calcular) y marcarlo en `table_notes`, para que `search_actuators` filtre igual por servicio.

**Conversaciones** (misma BD, mismo volumen `pgdata`):
- `sessions(id uuid, user_id null, title, created_at, updated_at)`
- `messages(id, session_id fk, role, content, products jsonb, trace jsonb, created_at)`
`user_id` nullable es el hueco para login. El título sale de los primeros ~50 caracteres de la primera consulta (sin llamar a un LLM).

## 3. Agente y reglas de números

- `agent/agent.py`: `run_agent(query, history=[])` con `create_agent()` de LangChain (skill `langchain-fundamentals`), sin checkpointer: el historial lo guardamos nosotros en `messages` y lo pasamos como lista.
- Tools (SQL parametrizado, el LLM no escribe SQL): `get_actuator(part_number)` (normaliza; devuelve encontrado / encontrado-sin-datos N/A / no encontrado con sugerencias / parcial con candidatos), `search_actuators(requisitos)` (torque con unidad Nm o in-lbs, voltaje, fase, enclosure, servicio, velocidad, duty; ordena por el más ajustado; si no hay, dice qué restricción lo impidió y el valor más cercano), `describe_catalog()` (para ambigüedad).
- Seguimiento multi-turno ("¿y cuánta potencia consume?"): al armar el historial se añade una línea de contexto con los part numbers de `products` del turno anterior, y el prompt obliga a **volver a llamar la tool** para cualquier número (el LLM no recuerda cifras).
- `agent/response.py`: arma `products[]` desde lo que devolvieron las tools (código, no LLM). Guardia: cada número del texto debe aparecer en los resultados de las tools; si no, se usa una respuesta determinista de plantilla y se anota en `trace`.
- Modelos por variable de entorno y por tarea: `AGENT_MODEL` (barato mientras se itera, bueno en la corrida final), `EXTRACT_LLM_MODEL` (escalado OCR, Sonnet 5.5). Desarrollo con Google AI Studio vía endpoint compatible OpenAI (`LLM_BASE_URL`); la key de OpenRouter solo con permiso explícito. Sin traducción por LLM de títulos ni embeddings (sin pgvector).
- Idioma: responde en el idioma del usuario; los números y part numbers van tal cual.

## 4. API (FastAPI)

- `POST /api/conversation` → `{session_id, answer, products[], debug}`. `products[]`: `{part_number, enclosure, voltage, phase, service, fields:{...valores con unidad...}, csa_certified, notes[]}`; la app los pinta como tarjetas comparables (una columna por producto). `debug`: lista de `{tool, params, result}`, **siempre presente en la respuesta**; la app de usuario no la muestra.
- `GET /api/sessions` (id, title, date) y `GET /api/sessions/{id}/messages` (incluye `products` y `debug`).
- `session_id` inexistente → **404** con mensaje claro (política explícita; sin crear sesiones por accidente). Sin `session_id` → crea sesión y la devuelve.
- Hueco de login: dependencia `get_current_user()` que hoy devuelve `None`; las consultas de `sessions_repo` ya aceptan `user_id`. Activarlo = implementar `POST /api/auth/login` y cambiar esa dependencia. Tabla `users` solo si se implementa.
- Hueco de voz: **transcripción en el dispositivo** (Android `SpeechRecognizer`), el texto va al mismo endpoint. Cero costo de presupuesto y cero cambios de backend.
- Errores: JSON uniforme `{error, detail}`; timeout/LLM caído devuelve 503 sin perder el mensaje del usuario ya guardado.

## 5. App Android (`mobile/android`)

Un solo módulo Gradle con paquetes por función (KISS; los skills `android-development` y `android-skills` aplican): `conversations/`, `chat/`, `debug/`, `data/` (Retrofit + kotlinx.serialization, un `ApiClient`), `ui/` (tema, `ProductCard`, `ComparisonTable`). MVVM: `ViewModel` + `StateFlow`; Navigation Compose; DI manual.
- Estados de carga/error en las 3 pantallas (backend caído, timeout).
- URL del backend en `BuildConfig` desde `local.properties` (emulador: `http://10.0.2.2:8000`).
- Debug: se abre con un gesto oculto (5 toques en el título del chat) y muestra el `debug` de cada respuesta; documentado en el README.
- El chat nunca muestra nombres de tools ni trazas.

## 6. Módulos backend (≤ ~150 líneas cada uno, probado solo)

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

Sin ORM (`psycopg` + SQL parametrizado), sin interfaces `DataSource`/`Extractor`, sin `EXTRACTORS=...` (un solo extractor definido), un `pyproject.toml`, `pip install -e .`.

## 7. Infraestructura

- `docker-compose.yml`: `db` (postgres:16, volumen `pgdata`, healthcheck `pg_isready`) y `api` (`depends_on: service_healthy`; al arrancar ejecuta `ensure_data()` y luego uvicorn).
- `Dockerfile`: python slim; `rapidocr-onnxruntime` trae los modelos ONNX → OCR offline.
- `.env.example`: `DATABASE_URL`, `LLM_BASE_URL`, `LLM_API_KEY`, `AGENT_MODEL`, `EXTRACT_LLM_MODEL`; sin secretos.
- `Makefile` (solo atajos): `up`, `reset` (borra volumen y recarga), `ingest-force`, `test`, `chat`, `eval`.
- Recuperación documentada en el README: BD borrada → `make up`; JSON borrado → `make up` (re-extrae); todo roto → `make reset`.

## 8. Pruebas y evaluación

- Unitarias por módulo, sin LLM real: `validate`, `flags`, `normalize`, repos (Postgres de prueba), tools, `response` (guardia de números), API con agente simulado.
- Test de auto-recuperación (criterio principal): (a) `docker compose down -v && make up` → 68 filas; (b) borrar `actuators.json` → se regenera y valida; (c) borrar filas en Postgres → el conteo se corrige; (d) JSON corrupto → se detecta y re-extrae; (e) reiniciar la API → las conversaciones siguen.
- `eval/`: 20–30 preguntas (puntual, recomendación, PN inválido, N/A, requisito imposible, ambigüedad, dato fuera del subconjunto, seguimiento multi-turno). Aserciones deterministas sobre la tool llamada y los números en `products`. Modelo barato al iterar, el bueno solo en la corrida final.
- Prueba final desde cero en máquina limpia siguiendo solo el README (requisito eliminatorio).

## 9. Orden de construcción y pistas paralelas

- **Fase 0 (secuencial)**: `domain/models.py`, `schema.sql`, firmas de `actuators_repo`/`sessions_repo`/tools, esquema `ConversationResponse`, `pyproject.toml`, compose, `CLAUDE.md`.
- **Pistas** (una carpeta cada una): A `ingestion/` + `bootstrap.py`; B `db/`; C `agent/tools.py`; D `agent/` (LLM, agente, response, eval); luego E `api/`; F `mobile/android` (puede arrancar con un servidor falso con el contrato de §4).
- **Fase 2 (secuencial)**: integrar, correr `eval/` con datos reales, README, prueba en máquina limpia.
- Si sobra tiempo: login (endpoint + `users` + dependencia) y voz en la app.

## 10. Cambios a aplicar tras aprobar (solo archivos locales; sin git)

1. **`CLAUDE.md`**: sección nueva "Principios: modular y KISS" en lenguaje llano; reescribir §5 (flujo auto-reparable y extractor actual, quitar interfaces/`EXTRACTORS`); actualizar §6 y §7 con `api/`, `sessions_repo` y el esquema de §2; mover el alcance de §2 (la fase de API y app entra al plan); registrar pendientes del OCR en §10 y cerrar la decisión de Android.
2. **`docs/ARCHITECTURE.md`**: este plan, versión duradera (vive en `docs/`, versionado y legible por evaluadores; `.claude/plans/` es personal).
3. **`docs/DECISIONS.md`**: primeras decisiones y sus trade-offs (OCR+escalado, sin interfaces, sin ORM, columnas tipadas, conteo exacto, historial propio sin checkpointer, 404 en sesión inexistente, voz en el dispositivo, `user_id` nullable).

## 11. Sugerencias de git (las ejecutas tú; yo no hago commits ni push)

- No hay commits aún: commit inicial con `CLAUDE.md`, `.gitignore`, `docs/`, `.mcp.json`, `skills-lock.json` y `.claude/`.
- Ramas cortas por módulo (`feat/db-repos`, `feat/ingestion`, `feat/agent-tools`, `feat/api`, `feat/android-chat`) y merge a `main`; encajan con las pistas en worktrees.
- Podar skills fuera de alcance (quickstarts TypeScript, `managed-deep-agents`, `swarm`, `deep-agents-*`) y actualizar `skills-lock.json` y `docs/TOOLING.md`.
- `.gitignore`: confirmar que `data/raw/*.pdf` y `data/processed/actuators.json` **sí** se versionan; añadir `inputs/crops/` si el OCR deja recortes dentro del repo.
- Versionar `.env.example`, nunca `.env`.

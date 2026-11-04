# Evaluation report

Model: `stealth/crouton-alpha`

Passed: 26/26 (100%)

| category | passed | % |
|---|---|---|
| lookup | 4/4 | 100% |
| recommend | 5/5 | 100% |
| invalid_pn | 3/3 | 100% |
| na | 2/2 | 100% |
| impossible | 3/3 | 100% |
| ambiguous | 3/3 | 100% |
| out_of_subset | 3/3 | 100% |
| multi_turn | 3/3 | 100% |

| id | category | pass | tools | seconds | failures |
|---|---|---|---|---|---|
| lookup-01 | lookup | PASS | get_actuator | 6.31 |  |
| lookup-02 | lookup | PASS | get_actuator | 5.61 |  |
| lookup-03 | lookup | PASS | get_actuator | 5.62 |  |
| lookup-04 | lookup | PASS | get_actuator | 4.62 |  |
| recommend-01 | recommend | PASS | search_actuators | 3.9 |  |
| recommend-02 | recommend | PASS | search_actuators | 6.01 |  |
| recommend-03 | recommend | PASS | search_actuators | 5.28 |  |
| recommend-04 | recommend | PASS | search_actuators | 5.09 |  |
| recommend-05 | recommend | PASS | search_actuators | 5.25 |  |
| invalid-01 | invalid_pn | PASS | get_actuator | 4.68 |  |
| invalid-02 | invalid_pn | PASS | get_actuator | 4.77 |  |
| invalid-03 | invalid_pn | PASS | get_actuator | 4.01 |  |
| na-01 | na | PASS | get_actuator | 5.59 |  |
| na-02 | na | PASS | get_actuator | 4.65 |  |
| impossible-01 | impossible | PASS | search_actuators | 5.24 |  |
| impossible-02 | impossible | PASS | search_actuators | 4.5 |  |
| impossible-03 | impossible | PASS | search_actuators | 4.17 |  |
| ambiguous-01 | ambiguous | PASS | get_actuator | 4.63 |  |
| ambiguous-02 | ambiguous | PASS | describe_catalog | 7.02 |  |
| ambiguous-03 | ambiguous | PASS | get_actuator | 4.14 |  |
| subset-01 | out_of_subset | PASS | search_actuators | 9.31 |  |
| subset-02 | out_of_subset | PASS | search_actuators | 6.86 |  |
| subset-03 | out_of_subset | PASS | search_actuators | 4.35 |  |
| multi-01 | multi_turn | PASS | get_actuator | 7.32 |  |
| multi-02 | multi_turn | PASS | get_actuator | 7.17 |  |
| multi-03 | multi_turn | PASS | get_actuator | 7.14 |  |

## Transcripts

### lookup-01 (lookup): PASS

**User:** What's the on/off torque in Nm and the 60 Hz stroke time of the 764A00-11300000/A?

**Assistant:**

> For **764A00-11300000/A**:
> 
> - On/off torque: **750 Nm**
> - 60 Hz stroke time: **30 seconds per 90°**

- Expected: `{'tools': ['get_actuator'], 'status': 'found', 'products': ['764A00-11300000/A'], 'answer_numbers': ['750', '30']}`
- Tools: get_actuator; products: 764A00-11300000/A

### lookup-02 (lookup): PASS

**User:** Cuánto es el FLA a 60 Hz del 762b0011320000/A? Es para dimensionar la protección.

**Assistant:**

> El FLA a 60 Hz es **1.1 A**.

- Expected: `{'tools': ['get_actuator'], 'status': 'found', 'products': ['762B00-11320000/A'], 'answer_numbers': ['1.1']}`
- Tools: get_actuator; products: 762B00-11320000/A

### lookup-03 (lookup): PASS

**User:** is the 766a00-11320000 CSA certified? and what's its on/off torque in Nm

**Assistant:**

> 766A00-11320000/A is **not CSA certified** — Sizes 6 and 7 are not CSA Certified.
> 
> On/off torque: **3500 Nm**

- Expected: `{'tools': ['get_actuator'], 'status': 'found', 'products': ['766A00-11320000/A'], 'answer_numbers': ['3500']}`
- Tools: get_actuator; products: 766A00-11320000/A

### lookup-04 (lookup): PASS

**User:** Necesito la corriente de rotor bloqueado (LRA) y el torque modulante en Nm del 761x30-11370000

**Assistant:**

> Para el **761X30-11370000/A**:
> 
> - **Corriente de rotor bloqueado (LRA):** 12.8 A
> - **Torque modulante:** 65 Nm

- Expected: `{'tools': ['get_actuator'], 'status': 'found', 'products': ['761X30-11370000/A'], 'answer_numbers': ['12.8', '65']}`
- Tools: get_actuator; products: 761X30-11370000/A

### recommend-01 (recommend): PASS

**User:** I need at least 200 Nm of modulating torque, 220V single phase, weatherproof. What do you recommend?

**Assistant:**

> Best match: **763A00-11320000/A**
> 
> - 220V, 1-phase, weatherproof, modulating
> - Modulating torque: 220 Nm
> - CSA certified

- Expected: `{'tools': ['search_actuators'], 'status': 'ok', 'products': ['763A00-11320000/A']}`
- Tools: search_actuators; products: 763A00-11320000/A

### recommend-02 (recommend): PASS

**User:** Necesito un actuador de 3000 in-lbs mínimo, 220V monofásico, a prueba de intemperie, servicio on/off.

**Assistant:**

> Mejor coincidencia: **763B00-11320000/A**
> 
> - 4400 in-lbs en servicio on/off
> - 220V, monofásico, a prueba de intemperie
> 
> También hay otras opciones de mayor torque en esa misma configuración.

- Expected: `{'tools': ['search_actuators'], 'status': 'ok', 'products': ['763B00-11320000/A']}`
- Tools: search_actuators; products: 763B00-11320000/A

### recommend-03 (recommend): PASS

**User:** Looking for 300 Nm or more, on/off, 220V single phase, weatherproof, and it has to stroke in 25 seconds or less.

**Assistant:**

> Best match: **763A00-11320000/A**
> 
> - 300 Nm on/off torque
> - 220V, 1-phase, weatherproof
> - 24 seconds per 90° at 60 Hz

- Expected: `{'tools': ['search_actuators'], 'status': 'ok', 'products': ['763A00-11320000/A']}`
- Tools: search_actuators; products: 763A00-11320000/A

### recommend-04 (recommend): PASS

**User:** Necesito un actuador antiexplosión (explosionproof), 220V monofásico, modulante, con al menos 600 Nm. Qué opciones hay?

**Assistant:**

> Hay 4 opciones explosionproof, 220V monofásico, modulante, con al menos 600 Nm:
> 
> **Mejor ajuste:** 764X30-11320000/A — 640 Nm en modulante
> 
> Otras opciones:
> - 764Y30-11320000/A — 750 Nm en modulante
> - 765X30-11320000/A — 1600 Nm en modulante
> - 765Y30-11320000/A — 2400 Nm en modulante

- Expected: `{'tools': ['search_actuators'], 'status': 'ok', 'products': ['764X30-11320000/A']}`
- Tools: search_actuators; products: 764X30-11320000/A, 764Y30-11320000/A, 765X30-11320000/A, 765Y30-11320000/A

### recommend-05 (recommend): PASS

**User:** 24V explosion proof valve actuator, modulating, at least 50 Nm. Which one fits best?

**Assistant:**

> Best match: **761X30-11370000/A** — 24V DC, explosionproof, modulating, 65 Nm modulating torque.
> 
> Also available in this series up to 220 Nm if you need more margin.

- Expected: `{'tools': ['search_actuators'], 'status': 'ok', 'products': ['761X30-11370000/A']}`
- Tools: search_actuators; products: 761X30-11370000/A

### invalid-01 (invalid_pn): PASS

**User:** What is the torque of the 999Z actuator?

**Assistant:**

> The 999Z actuator does not exist in the catalog. No close suggestions were returned.

- Expected: `{'tools': ['get_actuator'], 'status': 'not_found', 'no_products': True}`
- Tools: get_actuator; products: -

### invalid-02 (invalid_pn): PASS

**User:** Dame las especificaciones del 768A00-11300000/A

**Assistant:**

> El número de parte **768A00-11300000/A** no existe en el catálogo.
> 
> Sugerencias cercanas:
> - 761A00-11300000/A
> - 762A00-11300000/A
> - 763A00-11300000/A
> - 764A00-11300000/A
> - 765A00-11300000/A
> 
> ¿Quieres que busque las especificaciones de alguno de estos?

- Expected: `{'tools': ['get_actuator'], 'status': 'not_found', 'no_products': True}`
- Tools: get_actuator; products: -

### invalid-03 (invalid_pn): PASS

**User:** pull up the datasheet numbers for ABC-123 please

**Assistant:**

> Part number ABC-123 does not exist in the Series 76 catalog — no close matches were returned.
> 
> If you have a different part number, or want to search by torque / voltage / enclosure, I can look it up.

- Expected: `{'tools': ['get_actuator'], 'status': 'not_found', 'no_products': True}`
- Tools: get_actuator; products: -

### na-01 (na): PASS

**User:** What's the torque and speed of the 761A00-11330C00/A?

**Assistant:**

> The 761A00-11330C00/A exists, but the catalog prints N/A for both torque and speed — no data is available for that part number.

- Expected: `{'tools': ['get_actuator'], 'status': 'found_no_data'}`
- Tools: get_actuator; products: 761A00-11330C00/A

### na-02 (na): PASS

**User:** Cuál es el FLA del 762b00-11330c00? Es trifásico 220V.

**Assistant:**

> El **762B00-11330C00/A** existe — trifásico 220V, weatherproof — pero en la tabla figura **N/A**: no hay dato de FLA disponible para esa referencia.

- Expected: `{'tools': ['get_actuator'], 'status': 'found_no_data'}`
- Tools: get_actuator; products: 762B00-11330C00/A

### impossible-01 (impossible): PASS

**User:** I need 10000 Nm, 220V single phase, weatherproof.

**Assistant:**

> No actuator meets all of those requirements — the blocking requirement is torque.
> 
> For 220V, single-phase, weatherproof, the maximum available torque is 9000.0 Nm, below your requested 10000 Nm.

- Expected: `{'tools': ['search_actuators'], 'status': 'no_match', 'no_products': True}`
- Tools: search_actuators; products: -

### impossible-02 (impossible): PASS

**User:** Necesito 1000 Nm mínimo, 220V monofásico weatherproof y que cierre en 5 segundos o menos.

**Assistant:**

> No hay un actuador que cumpla todos los requisitos.
> 
> El requisito que bloquea es el tiempo de cierre de 5 segundos o menos. El más rápido disponible con 1000 Nm mínimo, 220V monofásico y weatherproof es de 33.0 s a 60 Hz.
> 
> ¿Quieres que busque sin el límite de velocidad, o con un tiempo mayor?

- Expected: `{'tools': ['search_actuators'], 'status': 'no_match', 'no_products': True}`
- Tools: search_actuators; products: -

### impossible-03 (impossible): PASS

**User:** Any 110V weatherproof actuator with 4000 Nm or more?

**Assistant:**

> No match for 110V weatherproof at 4000 Nm or more.
> 
> The closest available torque reported is 3000.0 Nm.

- Expected: `{'tools': ['search_actuators'], 'status': 'no_match', 'no_products': True}`
- Tools: search_actuators; products: -

### ambiguous-01 (ambiguous): PASS

**User:** Tell me about the 764A00

**Assistant:**

> 764A00 is ambiguous — which one do you mean?
> 
> - **764A00-11300000/A** — weatherproof, 110V, 1-phase
> - **764A00-11320000/A** — weatherproof, 220V, 1-phase
> - **764A00-11330C00/A** — weatherproof, 220V, 3-phase

- Expected: `{'tools': ['get_actuator'], 'status': 'ambiguous'}`
- Tools: get_actuator; products: -

### ambiguous-02 (ambiguous): PASS

**User:** I need an actuator

**Assistant:**

> The Series 76 catalog covers 65 to 9000 Nm (550 to 79700 in-lbs), in weatherproof and explosionproof enclosures, at 24V, 110V and 220V, single- and three-phase, for on/off and modulating service.
> 
> What torque, voltage, enclosure and service do you need?

- Expected: `{'tools': ['describe_catalog']}`
- Tools: describe_catalog; products: -

### ambiguous-03 (ambiguous): PASS

**User:** Me recomendaron el 763, cuáles son sus datos?

**Assistant:**

> Hay varias variantes del **763**, ¿cuál necesitas?
> 
> Por carcasa, voltaje y fase:
> 
> **Weatherproof**
> - 110V, 1 fase: 763A00-11300000/A, 763B00-11300000/A, 763C00-11300000/A
> - 220V, 1 fase: 763A00-11320000/A, 763B00-11320000/A, 763C00-11320000/A
> - 220V, 3 fases: 763A00-11330C00/A, 763B00-11330C00/A, 763C00-11330C00/A
> 
> **Explosionproof**
> - 110V, 1 fase: 763X30-11300000/A, 763Y30-11300000/A
> - 220V, 1 fase: 763X30-11320000/A, 763Y30-11320000/A
> - 24V DC, modulante: 763X30-11370000/A
> - 24V AC/DC, on/off: 763X30-11380000/A

- Expected: `{'tools': ['get_actuator'], 'status': 'ambiguous'}`
- Tools: get_actuator; products: -

### subset-01 (out_of_subset): PASS

**User:** I need a 24V weatherproof actuator, at least 100 Nm.

**Assistant:**

> No match — a 24V weatherproof actuator at that torque is out of catalog. The catalog has no data for that voltage/enclosure combination.

- Expected: `{'tools': ['search_actuators'], 'status': 'no_match', 'no_products': True, 'out_of_catalog': True}`
- Tools: search_actuators; products: -

### subset-02 (out_of_subset): PASS

**User:** Necesito un actuador trifásico 220V a prueba de explosión (explosionproof).

**Assistant:**

> No hay en el catálogo un actuador trifásico 220V a prueba de explosión (explosionproof). Esa combinación está fuera de catálogo.
> 
> ¿Quieres que busque una alternativa, por ejemplo monofásico explosionproof o trifásico weatherproof?

- Expected: `{'tools': ['search_actuators'], 'status': 'no_match', 'no_products': True, 'out_of_catalog': True}`
- Tools: search_actuators; products: -

### subset-03 (out_of_subset): PASS

**User:** Do you have a 24V three-phase actuator with at least 100 Nm?

**Assistant:**

> No — a 24V three-phase actuator with at least 100 Nm is out of catalog. That voltage/phase combination does not exist in the catalog.
> 
> Would you like me to search for 24V single-phase, or three-phase at a different voltage?

- Expected: `{'tools': ['search_actuators'], 'status': 'no_match', 'no_products': True, 'out_of_catalog': True}`
- Tools: search_actuators; products: -

### multi-01 (multi_turn): PASS

**User:** Give me the specs of the 761A00-11300000/A

**Assistant:**

> **761A00-11300000/A** — weatherproof, 110V, 1-phase, CSA certified
> 
> - On/off torque: 80 Nm (700 in-lbs), 40% duty, 36 cycles/hour
> - Modulating torque: 65 Nm (580 in-lbs), 40% duty, 960 starts/hour
> - Speed: 17 seconds per 90° @ 60Hz / 20 seconds per 90° @ 50Hz
> - FLA: 1.2 A @ 60Hz, Motor power: 15 W

**User:** and how much current does it draw at 50 Hz?

**Assistant:**

> For **761A00-11300000/A** at 50 Hz:
> 
> - FLA: 1.1 A
> - LRA: 1.3 A

- Expected: `{'tools': ['get_actuator'], 'status': 'found', 'products': ['761A00-11300000/A'], 'answer_numbers': ['1.1']}`
- Tools: get_actuator; products: 761A00-11300000/A

### multi-02 (multi_turn): PASS

**User:** I need at least 200 Nm of modulating torque, 220V single phase, weatherproof.

**Assistant:**

> Best match: **763A00-11320000/A** — 220 Nm modulating torque, 220V single phase, weatherproof.
> 
> 4 other matches also meet your requirements.

**User:** what's the 60 Hz speed of the first one?

**Assistant:**

> **763A00-11320000/A** — 24 seconds per 90° at 60 Hz.

- Expected: `{'tools': ['get_actuator'], 'answer_numbers': ['24']}`
- Tools: get_actuator; products: 763A00-11320000/A

### multi-03 (multi_turn): PASS

**User:** Hola, dame los datos del 762a00-11300000

**Assistant:**

> **762A00-11300000/A** — weatherproof, 110V AC, 1 fase, servicio on/off y modulante. Certificaciones: CSA, CE, & UKCA.
> 
> - Par on/off: 150 Nm (1330 in-lbs), ciclo de trabajo 50%, 42 ciclos/hora
> - Par modulante: 130 Nm (1150 in-lbs), ciclo de trabajo 40%, 960 arranques/hora
> - Velocidad: 18 segundos por 90° a 60Hz / 21 segundos por 90° a 50Hz
> - FLA: 2.3 A, LRA: 2.5 A a 60Hz / 2.4 A a 50Hz
> - Potencia del motor: 40 W

**User:** y cuál es su velocidad a 50 Hz?

**Assistant:**

> **762A00-11300000/A** — a 50 Hz: **21 segundos por 90°**.

- Expected: `{'tools': ['get_actuator'], 'products': ['762A00-11300000/A'], 'answer_numbers': ['21']}`
- Tools: get_actuator; products: 762A00-11300000/A


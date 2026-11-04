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
| lookup-01 | lookup | PASS | get_actuator | 4.96 |  |
| lookup-02 | lookup | PASS | get_actuator | 4.27 |  |
| lookup-03 | lookup | PASS | get_actuator | 5.59 |  |
| lookup-04 | lookup | PASS | get_actuator | 3.86 |  |
| recommend-01 | recommend | PASS | search_actuators | 5.86 |  |
| recommend-02 | recommend | PASS | search_actuators | 5.94 |  |
| recommend-03 | recommend | PASS | search_actuators | 4.5 |  |
| recommend-04 | recommend | PASS | search_actuators | 4.25 |  |
| recommend-05 | recommend | PASS | search_actuators | 4.84 |  |
| invalid-01 | invalid_pn | PASS | get_actuator | 3.21 |  |
| invalid-02 | invalid_pn | PASS | get_actuator | 3.64 |  |
| invalid-03 | invalid_pn | PASS | get_actuator | 4.48 |  |
| na-01 | na | PASS | get_actuator | 3.79 |  |
| na-02 | na | PASS | get_actuator | 4.16 |  |
| impossible-01 | impossible | PASS | search_actuators | 4.13 |  |
| impossible-02 | impossible | PASS | search_actuators | 4.33 |  |
| impossible-03 | impossible | PASS | search_actuators | 5.11 |  |
| ambiguous-01 | ambiguous | PASS | get_actuator | 4.26 |  |
| ambiguous-02 | ambiguous | PASS | describe_catalog | 4.62 |  |
| ambiguous-03 | ambiguous | PASS | get_actuator | 5.14 |  |
| subset-01 | out_of_subset | PASS | search_actuators | 5.65 |  |
| subset-02 | out_of_subset | PASS | search_actuators | 5.01 |  |
| subset-03 | out_of_subset | PASS | search_actuators | 4.42 |  |
| multi-01 | multi_turn | PASS | get_actuator | 8.68 |  |
| multi-02 | multi_turn | PASS | get_actuator | 7.6 |  |
| multi-03 | multi_turn | PASS | get_actuator | 7.2 |  |

## Transcripts

### lookup-01 (lookup): PASS

**User:** What's the on/off torque in Nm and the 60 Hz stroke time of the 764A00-11300000/A?

**Assistant:**

> For 764A00-11300000/A:
> 
> - On/off torque: 750 Nm
> - 60 Hz stroke time: 30 seconds per 90°

- Expected: `{'tools': ['get_actuator'], 'status': 'found', 'products': ['764A00-11300000/A'], 'answer_numbers': ['750', '30']}`
- Tools: get_actuator; products: 764A00-11300000/A

### lookup-02 (lookup): PASS

**User:** Cuánto es el FLA a 60 Hz del 762b0011320000/A? Es para dimensionar la protección.

**Assistant:**

> Para el **762B00-11320000/A**, el FLA a 60 Hz es **1.1 A**.

- Expected: `{'tools': ['get_actuator'], 'status': 'found', 'products': ['762B00-11320000/A'], 'answer_numbers': ['1.1']}`
- Tools: get_actuator; products: 762B00-11320000/A

### lookup-03 (lookup): PASS

**User:** is the 766a00-11320000 CSA certified? and what's its on/off torque in Nm

**Assistant:**

> No — 766A00-11320000/A is not CSA certified. Note: Sizes 6 and 7 are not CSA Certified.
> 
> On/off torque: 3500 Nm

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

> La mejor coincidencia es **763B00-11320000/A**:
> 
> - 220V, monofásico, a prueba de intemperie, servicio on/off
> - Torque on/off: 4400 in-lbs
> 
> Cumple con su mínimo de 3000 in-lbs.

- Expected: `{'tools': ['search_actuators'], 'status': 'ok', 'products': ['763B00-11320000/A']}`
- Tools: search_actuators; products: 763B00-11320000/A

### recommend-03 (recommend): PASS

**User:** Looking for 300 Nm or more, on/off, 220V single phase, weatherproof, and it has to stroke in 25 seconds or less.

**Assistant:**

> Best match: **763A00-11320000/A**
> 
> - On/off torque: 300 Nm
> - Speed: 24 seconds per 90° at 60 Hz
> - 220V, single phase, weatherproof
> - CSA certified

- Expected: `{'tools': ['search_actuators'], 'status': 'ok', 'products': ['763A00-11320000/A']}`
- Tools: search_actuators; products: 763A00-11320000/A

### recommend-04 (recommend): PASS

**User:** Necesito un actuador antiexplosión (explosionproof), 220V monofásico, modulante, con al menos 600 Nm. Qué opciones hay?

**Assistant:**

> Hay 4 opciones explosionproof, 220V monofásico, modulante, con al menos 600 Nm. La más ajustada es:
> 
> **764X30-11320000/A** — par modulante 640 Nm, 34 seconds per 90° a 60 Hz, certificado CSA.
> 
> También cumplen:
> - **764Y30-11320000/A** — par modulante 750 Nm
> - **765X30-11320000/A** — par modulante 1600 Nm
> - **765Y30-11320000/A** — par modulante 2400 Nm

- Expected: `{'tools': ['search_actuators'], 'status': 'ok', 'products': ['764X30-11320000/A']}`
- Tools: search_actuators; products: 764X30-11320000/A, 764Y30-11320000/A, 765X30-11320000/A, 765Y30-11320000/A

### recommend-05 (recommend): PASS

**User:** 24V explosion proof valve actuator, modulating, at least 50 Nm. Which one fits best?

**Assistant:**

> Best match: **761X30-11370000/A** — 24V DC, explosionproof, modulating, 65 Nm.
> 
> CSA certified.

- Expected: `{'tools': ['search_actuators'], 'status': 'ok', 'products': ['761X30-11370000/A']}`
- Tools: search_actuators; products: 761X30-11370000/A

### invalid-01 (invalid_pn): PASS

**User:** What is the torque of the 999Z actuator?

**Assistant:**

> The part number 999Z does not exist in the Series 76 catalog.

- Expected: `{'tools': ['get_actuator'], 'status': 'not_found', 'no_products': True}`
- Tools: get_actuator; products: -

### invalid-02 (invalid_pn): PASS

**User:** Dame las especificaciones del 768A00-11300000/A

**Assistant:**

> Ese número de parte no existe en el catálogo.
> 
> ¿Querías decir uno de estos?
> - 761A00-11300000/A
> - 762A00-11300000/A
> - 763A00-11300000/A
> - 764A00-11300000/A
> - 765A00-11300000/A

- Expected: `{'tools': ['get_actuator'], 'status': 'not_found', 'no_products': True}`
- Tools: get_actuator; products: -

### invalid-03 (invalid_pn): PASS

**User:** pull up the datasheet numbers for ABC-123 please

**Assistant:**

> ABC-123 does not exist in the Series 76 catalog — no matching part number was found.

- Expected: `{'tools': ['get_actuator'], 'status': 'not_found', 'no_products': True}`
- Tools: get_actuator; products: -

### na-01 (na): PASS

**User:** What's the torque and speed of the 761A00-11330C00/A?

**Assistant:**

> The 761A00-11330C00/A exists, but the catalog prints N/A for torque and speed — no data is available for that part number.

- Expected: `{'tools': ['get_actuator'], 'status': 'found_no_data'}`
- Tools: get_actuator; products: 761A00-11330C00/A

### na-02 (na): PASS

**User:** Cuál es el FLA del 762b00-11330c00? Es trifásico 220V.

**Assistant:**

> El 762B00-11330C00/A (220V, trifásico) existe, pero en la tabla figura como N/A: no hay datos de FLA disponibles para esa referencia.

- Expected: `{'tools': ['get_actuator'], 'status': 'found_no_data'}`
- Tools: get_actuator; products: 762B00-11330C00/A

### impossible-01 (impossible): PASS

**User:** I need 10000 Nm, 220V single phase, weatherproof.

**Assistant:**

> No match for 10000 Nm, 220V single phase, weatherproof.
> 
> The blocking requirement is torque — the maximum available is 9000.0 Nm.

- Expected: `{'tools': ['search_actuators'], 'status': 'no_match', 'no_products': True}`
- Tools: search_actuators; products: -

### impossible-02 (impossible): PASS

**User:** Necesito 1000 Nm mínimo, 220V monofásico weatherproof y que cierre en 5 segundos o menos.

**Assistant:**

> No hay un actuador que cumpla todos los requisitos.
> 
> El requisito que bloquea es el tiempo de cierre de 5 segundos o menos. El más rápido disponible con las demás condiciones es de 33.0 s a 60 Hz.
> 
> ¿Quieres que busque sin el límite de velocidad, o con un tiempo máximo mayor?

- Expected: `{'tools': ['search_actuators'], 'status': 'no_match', 'no_products': True}`
- Tools: search_actuators; products: -

### impossible-03 (impossible): PASS

**User:** Any 110V weatherproof actuator with 4000 Nm or more?

**Assistant:**

> No match for 110V weatherproof at 4000 Nm or more.
> 
> Closest available torque reported is 3000.0 Nm.

- Expected: `{'tools': ['search_actuators'], 'status': 'no_match', 'no_products': True}`
- Tools: search_actuators; products: -

### ambiguous-01 (ambiguous): PASS

**User:** Tell me about the 764A00

**Assistant:**

> The part number 764A00 is ambiguous — there are 3 candidates:
> 
> 1. **764A00-11300000/A** — weatherproof, 110V, 1-phase
> 2. **764A00-11320000/A** — weatherproof, 220V, 1-phase
> 3. **764A00-11330C00/A** — weatherproof, 220V, 3-phase
> 
> Which one do you mean?

- Expected: `{'tools': ['get_actuator'], 'status': 'ambiguous'}`
- Tools: get_actuator; products: -

### ambiguous-02 (ambiguous): PASS

**User:** I need an actuator

**Assistant:**

> The Series 76 catalog covers 65 to 9000 Nm (550 to 79700 in-lbs) in weatherproof and explosionproof versions.
> 
> What minimum torque do you need, in Nm or in-lbs?

- Expected: `{'tools': ['describe_catalog']}`
- Tools: describe_catalog; products: -

### ambiguous-03 (ambiguous): PASS

**User:** Me recomendaron el 763, cuáles son sus datos?

**Assistant:**

> Hay varios modelos 763, ¿cuál necesitas?
> 
> **Weatherproof:**
> - 763A00-11300000/A, 763B00-11300000/A, 763C00-11300000/A — 110V, 1 fase
> - 763A00-11320000/A, 763B00-11320000/A, 763C00-11320000/A — 220V, 1 fase
> - 763A00-11330C00/A, 763B00-11330C00/A, 763C00-11330C00/A — 220V, 3 fases
> 
> **Explosionproof:**
> - 763X30-11300000/A, 763Y30-11300000/A — 110V, 1 fase
> - 763X30-11320000/A, 763Y30-11320000/A — 220V, 1 fase
> - 763X30-11370000/A — 24V DC
> - 763X30-11380000/A — 24V AC/DC
> 
> Indícame la carcasa, el voltaje y la fase que buscas y te doy sus datos.

- Expected: `{'tools': ['get_actuator'], 'status': 'ambiguous'}`
- Tools: get_actuator; products: -

### subset-01 (out_of_subset): PASS

**User:** I need a 24V weatherproof actuator, at least 100 Nm.

**Assistant:**

> No match — the 24V weatherproof combination is out of catalog, so no actuator meets at least 100 Nm with those requirements.
> 
> Would you like to try a different voltage or enclosure?

- Expected: `{'tools': ['search_actuators'], 'status': 'no_match', 'no_products': True, 'out_of_catalog': True}`
- Tools: search_actuators; products: -

### subset-02 (out_of_subset): PASS

**User:** Necesito un actuador trifásico 220V a prueba de explosión (explosionproof).

**Assistant:**

> No hay un actuador Series 76 con esa combinación en el catálogo: trifásico 220V a prueba de explosión (explosionproof) está fuera de catálogo.
> 
> ¿Quieres que busque la alternativa más cercana priorizando trifásico o priorizando a prueba de explosión?

- Expected: `{'tools': ['search_actuators'], 'status': 'no_match', 'no_products': True, 'out_of_catalog': True}`
- Tools: search_actuators; products: -

### subset-03 (out_of_subset): PASS

**User:** Do you have a 24V three-phase actuator with at least 100 Nm?

**Assistant:**

> No — a 24V three-phase actuator is not in the catalog.
> 
> The search returned no match, with voltage and phase blocking the combination.

- Expected: `{'tools': ['search_actuators'], 'status': 'no_match', 'no_products': True, 'out_of_catalog': True}`
- Tools: search_actuators; products: -

### multi-01 (multi_turn): PASS

**User:** Give me the specs of the 761A00-11300000/A

**Assistant:**

> **761A00-11300000/A** — weatherproof, 110V, 1-phase, CSA certified.
> 
> - On/off torque: 80 Nm (700 in-lbs), 40% duty cycle, 36 cycles/hour
> - Modulating torque: 65 Nm (580 in-lbs), 40% duty cycle, 960 starts/hour
> - Speed: 17 seconds per 90° @ 60Hz (20 @ 50Hz)
> - FLA: 1.2 A @ 60Hz, motor power: 15 W

**User:** and how much current does it draw at 50 Hz?

**Assistant:**

> At 50 Hz, FLA is **1.1 A**.

- Expected: `{'tools': ['get_actuator'], 'status': 'found', 'products': ['761A00-11300000/A'], 'answer_numbers': ['1.1']}`
- Tools: get_actuator; products: 761A00-11300000/A

### multi-02 (multi_turn): PASS

**User:** I need at least 200 Nm of modulating torque, 220V single phase, weatherproof.

**Assistant:**

> Best match: **763A00-11320000/A** — modulating torque 220 Nm, 220V single phase, weatherproof.
> 
> 4 other matches also meet ≥200 Nm modulating in this configuration.

**User:** what's the 60 Hz speed of the first one?

**Assistant:**

> **763A00-11320000/A** — 24 seconds per 90° at 60 Hz.

- Expected: `{'tools': ['get_actuator'], 'answer_numbers': ['24']}`
- Tools: get_actuator; products: 763A00-11320000/A

### multi-03 (multi_turn): PASS

**User:** Hola, dame los datos del 762a00-11300000

**Assistant:**

> **762A00-11300000/A** — weatherproof, 110V, 1 fase, AC, CSA
> 
> - Par on/off: 150 Nm (1330 in-lbs), ciclo 50%, 42 ciclos/hora
> - Par modulante: 130 Nm (1150 in-lbs), ciclo 40%, 960 arranques/hora
> - Velocidad: 18 s a 60 Hz / 21 s a 50 Hz
> - FLA: 2.3 A, LRA: 2.5 A a 60 Hz / 2.4 A a 50 Hz
> - Potencia motor: 40 W

**User:** y cuál es su velocidad a 50 Hz?

**Assistant:**

> Para el **762A00-11300000/A**, la velocidad a 50 Hz es de **21 s** por 90°.

- Expected: `{'tools': ['get_actuator'], 'products': ['762A00-11300000/A'], 'answer_numbers': ['21']}`
- Tools: get_actuator; products: 762A00-11300000/A


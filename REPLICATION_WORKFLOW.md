# Replicar El Análisis Econométrico: Orden Correcto y Lógica

## Objetivo

Este documento explica el **orden correcto** para llegar desde un clon del repositorio hasta el uso del `replication package` de `analysis/paper_replication/`.

La idea principal es esta:

- el paquete de réplica **no reconstruye todo desde cero**
- antes necesita que el pipeline general haya creado varios insumos compartidos
- si se intenta entrar directamente por `paper_replication` o por el scraper SEPE, aparecen errores confusos o faltan ficheros

Por eso conviene pensar el proyecto en **capas**:

1. **pipeline base de exposición IA** sobre ocupaciones españolas
2. **dataset mensual SEPE a nivel CNO4** enriquecido con exposure
3. **replication package** que usa esos insumos para preparar paneles, descriptivos y estimaciones

---

## Idea General Del Flujo

El flujo correcto es:

1. instalar dependencias
2. preparar el modelo y la caché del pipeline EPA
3. descargar el ZIP de Anthropic usado en descriptivos
4. construir el dataset mensual SEPE enriquecido con exposure IA
5. ejecutar el `replication package` por pasos

La razón de este orden es que el paso de SEPE no vive aislado:

- necesita medidas de exposure a nivel `CNO4`
- esas medidas salen del pipeline base
- el paquete de réplica necesita además el CSV final SEPE ya construido

---

## Paso 0. Entrar En El Repo

```powershell
cd C:\Users\hjimenez\Documents\Spain-AI-Exposure
```

### Qué hace

Te sitúa en la raíz correcta del proyecto.

### Por qué importa

Muchos scripts resuelven rutas relativas desde la raíz del repo. Si se lanzan desde otra carpeta, pueden no encontrar bien `data/`, `analysis/` o `scripts/`.

---

## Paso 1. Instalar Dependencias Python

```powershell
python -m pip install -r requirements.txt
```

### Qué hace

Instala las librerías Python que usa el proyecto:

- descarga de datos
- parsing del PDF CNO
- embeddings
- merges y agregaciones
- análisis econométricos en Python

### Qué añade

No añade outputs del análisis, pero deja el entorno preparado para que los scripts funcionen.

### Valor para el análisis posterior

Sin este paso no puede ejecutarse ni el pipeline base ni el paquete de réplica.

---

## Paso 2. Instalar El Modelo De Embeddings En Ollama

```powershell
ollama pull qwen3-embedding:4b
```

### Qué hace

Descarga el modelo de embeddings usado por el pipeline para representar:

- ocupaciones Anthropic/O*NET
- ocupaciones españolas CNO4

### Qué añade

Deja disponible localmente el modelo que luego usan `main.py` y otros componentes.

### Valor para el análisis posterior

El proyecto necesita embeddings para construir:

- el modelo RF
- los matches por cosine similarity
- las medidas de exposure a nivel `CNO4`

Sin esto no se puede reconstruir la parte estructural del pipeline.

---

## Paso 3. Ejecutar El Pipeline Base EPA

```powershell
python main.py --embedding-model qwen3-embedding:4b --ine-manifest ine_manifest.csv --methods rf,cosine_weighted,cosine_nearest
```

### Qué hace

Este es el paso fundacional. Construye la parte “base” del proyecto:

1. descarga o reutiliza `job_exposure.csv` de Anthropic
2. descarga o reutiliza el PDF `cno11_notas.pdf` de INE
3. lee el manifest de EPA y descarga los ficheros necesarios de INE
4. parsea la taxonomía CNO4 desde el PDF
5. genera embeddings
6. entrena o reconstruye el bundle de exposure
7. calcula exposure por `CNO4`
8. agrega después a `OCUP1` y a industria-trimestre
9. escribe varios outputs procesados

### Qué añade o debería añadir

Después de este paso deberían existir al menos:

- `models/exposure_model_qwen3-embedding_4b_rf_cosine_weighted_cosine_nearest.joblib`
- `data/cache/embeddings.sqlite`
- `data/raw/anthropic/job_exposure.csv`
- `data/raw/ine/cno11_notas.pdf`
- `data/processed/spanish_occupation_exposure.csv`
- `data/processed/spanish_occupation_matches_cosine_weighted.csv`
- `data/processed/spanish_occupation_matches_cosine_nearest.csv`
- `data/processed/spanish_ai_exposure.sqlite`

### Valor para el análisis posterior

Este paso crea dos cosas críticas para todo lo demás:

1. **el modelo/caché que luego necesita el paso de SEPE**
2. **la capa de exposure IA sobre ocupaciones españolas**

Sin este paso, el repo puede tener algunos CSV sueltos, pero no queda garantizado que exista el bundle coherente que espera `build_sepe_occupation_dataset.py`.

### Nota importante

No conviene empezar por el scraper SEPE si este paso no ha corrido bien. El scraper SEPE necesita exposure a nivel `CNO4`, y en este repo esa capa nace aquí.

---

## Paso 4. Descargar El ZIP De Anthropic Usado En Los Descriptivos

```powershell
python main.py --analysis-only --run-anthropic-country-figure
```

### Qué hace

Ejecuta la parte del proyecto que descarga o reutiliza:

- `data/raw/anthropic/release-2026-06-26.zip`

y además genera la figura España-EEUU por major occupation group.

### Qué añade

El fichero clave que interesa para la réplica es:

- `data/raw/anthropic/release-2026-06-26.zip`

### Valor para el análisis posterior

El `replication package`, en el paso de descriptivos, usa ese ZIP para extraer:

- `aei_claude_ai_2026-06-26.csv`

Si el ZIP no existe, el wrapper de réplica se rompe en ese punto.

### Por qué este paso está separado

Porque el pipeline base no siempre deja descargado automáticamente ese release ZIP concreto. Este paso lo asegura y además deja un artefacto útil para las figuras descriptivas.

---

## Paso 5. Construir El Dataset Mensual SEPE Enriquecido Con Exposure

```powershell
python scripts/build_sepe_occupation_dataset.py --embedding-model qwen3-embedding:4b
```

### Qué hace

Este script:

1. visita la fuente SEPE de informes mensuales por ocupación
2. descarga y cachea los reportes HTML en bruto
3. parsea parados, contratos, personas y desgloses
4. reconstruye un panel mensual por `CNO4`
5. une a cada `CNO4` sus variables de exposure IA

### Qué añade o debería añadir

Después de este paso deberían existir:

- `data/raw/sepe/reports/`
- `data/processed/sepe_cno4_monthly_ai_exposure.csv`

### Valor para el análisis posterior

Este CSV es el insumo central de la econometría SEPE. A partir de él se construyen:

- paneles totales por ocupación
- paneles por provincia
- paneles por edad
- paneles por sexo
- variantes para TWFE, SDID y ContDID

### Por qué no debe correrse antes del paso 3

Porque este script necesita:

- medidas de exposure a nivel `CNO4`
- el modelo o la estructura derivada del pipeline base

Si se intenta usar como input `spanish_occupation_exposure.csv`, falla, porque ese fichero está agregado a `OCUP1`, no a `CNO4`.

### Si ya existe caché de SEPE

Se puede reconstruir sin tocar la web:

```powershell
python scripts/build_sepe_occupation_dataset.py --embedding-model qwen3-embedding:4b --from-cache --workers 8
```

Esto tiene valor cuando queremos rehacer el CSV procesado sin redescargar todos los HTML.

---

## Paso 6. Comprobar El Estado Del Replication Package

```powershell
python scripts/run_paper_replication.py --dry-run
```

### Qué hace

No ejecuta la réplica. Solo informa de:

- qué pasos intentaría correr
- dónde montaría el `runtime`
- si los insumos principales están presentes o ausentes

### Valor para el análisis posterior

Es la forma más limpia de validar que ya están los prerequisitos antes de lanzar notebooks, Stata o R.

---

## Paso 7. Ejecutar La Preparación Del Replication Package

```powershell
python scripts/run_paper_replication.py --step prepare
```

### Qué hace

El wrapper:

1. crea `analysis/paper_replication/runtime/`
2. copia ahí los notebooks y scripts fuente
3. materializa en `runtime/data/raw/` los insumos compartidos del repo
4. ejecuta `01_Preparation_v1.ipynb`

### Qué añade

Genera el entorno de trabajo real del paquete de réplica y produce los paneles preparados que usan los pasos siguientes.

### Valor para el análisis posterior

Este es el primer momento en el que tiene sentido “jugar” con el paquete de réplica.

### Idea clave

No conviene abrir directamente:

- `analysis/paper_replication/01_Preparation_v1.ipynb`

como notebook principal de trabajo. El lugar correcto para inspeccionar lo generado es:

- `analysis/paper_replication/runtime/01_Preparation_v1.ipynb`

porque ahí ya están staged los insumos y los outputs intermedios.

---

## Paso 8. Ejecutar Los Descriptivos

```powershell
python scripts/run_paper_replication.py --step descriptives
```

### Qué hace

Ejecuta `02_Descriptives_v1.ipynb` dentro del `runtime`.

### Qué usa

Entre otros insumos:

- el CSV mensual SEPE ya preparado
- el ZIP de Anthropic
- el PDF de CNO
- las tablas auxiliares en `data_sources/`

### Valor para el análisis posterior

Este paso genera:

- figuras descriptivas
- tablas de validación
- comparaciones y comprobaciones previas a la econometría

Es la capa que documenta que las construcciones previas tienen sentido antes de pasar a identificación econométrica.

---

## Paso 9. Ejecutar Las Estimaciones En Stata

```powershell
python scripts/run_paper_replication.py --step estimates --stata-exe "C:\Program Files\StataNow19\StataMP-64.exe" --sdid-reps 20
```

### Qué hace

Ejecuta:

- `03_Estimates_TWFE_SDID_HonestDID_v1.do`

### Qué produce

Corre:

- TWFE
- SDID
- diagnósticos de pretrends y robustness
- salidas para figuras y tablas

### Valor para el análisis posterior

Aquí está el núcleo causal del trabajo. Usa los paneles preparados para convertir el dataset en resultados econométricos reproducibles.

### Nota práctica

Para smoke tests conviene usar reps pequeñas, por ejemplo `20`. Los valores de producción son más altos y tardan bastante más.

---

## Paso 10. Ejecutar ContDID En R

```powershell
python scripts/run_paper_replication.py --step contdid --rscript "C:\RUTA\A\Rscript.exe" --contdid-reps 50
```

### Qué hace

Ejecuta:

- `04_Estimates_contDID_v1.R`

### Valor para el análisis posterior

Añade la versión de tratamiento continuo del análisis, complementando las estimaciones TWFE y SDID.

### Requisito

Necesitas tener `Rscript` instalado y localizable.

---

## Paso 11. Ejecutar El Tuning Final De Outputs

```powershell
python scripts/run_paper_replication.py --step tuning
```

### Qué hace

Ejecuta:

- `05_Output_tuning_v1.ipynb`

### Valor para el análisis posterior

Este paso organiza y afina:

- figuras finales
- tablas
- salidas de manuscrito

Es el cierre del flujo de réplica.

---

## Orden Corto Recomendado

Si un colaborador quiere ir de cero a una réplica utilizable, el orden corto es:

1. `python -m pip install -r requirements.txt`
2. `ollama pull qwen3-embedding:4b`
3. `python main.py --embedding-model qwen3-embedding:4b --ine-manifest ine_manifest.csv --methods rf,cosine_weighted,cosine_nearest`
4. `python main.py --analysis-only --run-anthropic-country-figure`
5. `python scripts/build_sepe_occupation_dataset.py --embedding-model qwen3-embedding:4b`
6. `python scripts/run_paper_replication.py --dry-run`
7. `python scripts/run_paper_replication.py --step prepare`
8. `python scripts/run_paper_replication.py --step descriptives`
9. `python scripts/run_paper_replication.py --step estimates --stata-exe "C:\Program Files\StataNow19\StataMP-64.exe" --sdid-reps 20`
10. `python scripts/run_paper_replication.py --step contdid --rscript "C:\RUTA\A\Rscript.exe" --contdid-reps 50`
11. `python scripts/run_paper_replication.py --step tuning`

---

## Qué No Hacer

Evitar estos atajos, porque llevan a errores difíciles de interpretar:

- no abrir directamente `analysis/paper_replication/*.ipynb` como punto de partida
- no lanzar primero `build_sepe_occupation_dataset.py` si no existe todavía el bundle base del pipeline
- no usar `data/processed/spanish_occupation_exposure.csv` como si fuera exposure a nivel `CNO4`
- no asumir que el `replication package` genera por sí solo los insumos compartidos del repo

---


## Dónde “Jugar” Con El Replication Package

Una vez corrido `--step prepare`, el sitio correcto para inspeccionar y experimentar es:

- `analysis/paper_replication/runtime/`

En particular:

- `analysis/paper_replication/runtime/01_Preparation_v1.ipynb`
- `analysis/paper_replication/runtime/02_Descriptives_v1.ipynb`

Ahí ya están montados:

- los inputs staged
- los paneles preparados
- los outputs intermedios

---

## Resumen Final

La lógica del proyecto no es:

`paper_replication` -> produce todo

La lógica real es:

`pipeline base` -> `SEPE monthly dataset` -> `paper_replication runtime`

Cuando ese orden se respeta, el proyecto sí tiene sentido como paquete replicable por un colaborador en otra máquina.

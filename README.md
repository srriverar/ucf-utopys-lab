# UCF × UTOPYS · Research Lab

**Una propuesta de cooperación científica, no un producto oficial de UTOPYS.** Aplicación bilingüe ES/EN que ilustra cómo las funciones de costo de incertidumbre (UCF), desarrolladas en la línea de investigación del profesor Sergio Rivera y colaboradores, podrían aportar a preguntas de UTOPYS. **No está afiliada ni conectada a UTOPYS; no ha sido validada por el consorcio y no ejecuta simulaciones EMT.**

An independent, bilingual research prototype exploring how uncertainty cost functions might support decision-aware uncertainty quantification for UTOPYS. It is not affiliated with, connected to, or validated by UTOPYS, and it does not run EMT simulations. See [English quick start](#english-quick-start).

## Qué incluye

La navegación conserva los identificadores originales y tiene ahora tres páginas, en este orden:

1. **02 · Explorador UCF:** un control visible de `Ps`, escenario de potencia renovable, batería/ESS o respaldo despachable y comparación del costo esperado analítico **con respaldo** frente a Monte Carlo; también conserva las curvas UCF originales sin respaldo.
2. **03 · Wasserstein + DRO:** el mismo control de `Ps` y respaldo; transporte hacia una delta de Dirac en `Ps`, antes y después de la acción del respaldo. El costo operativo se suma por separado. El DRO y la comparación entre distribuciones son del modelo **sin respaldo**.
3. **01 · Encaje UTOPYS:** mapa de M1–M3, C1/C2 y P3; distingue objetivos publicados de contribuciones propuestas y evidencia aún necesaria. También describe C3, P1 y P2.

El `Ps` de las páginas 02 y 03 está sincronizado con la barra lateral. En el panel de respaldo puede elegir **batería / ESS**, **respaldo despachable** o **sin respaldo**; ajuste potencia, energía, estado inicial, eficiencias y costo según corresponda. El control de **escenario** cambia una realización de potencia renovable, sin alterar su distribución. La batería responde idealmente para un solo intervalo; cada escenario parte del mismo SOC inicial. No hay optimización económica, secuencia de SOC, fallas ni garantía de entrega.

Para la beta sintética, el costo esperado con respaldo usa una expresión continua en funciones beta incompletas y Monte Carlo muestrea esa misma beta; las curvas UCF/DRO originales usan 200 puntos discretos y pueden diferir, sobre todo con densidades altas cerca de los extremos. Para un CSV se usa la suma exacta de la distribución empírica ponderada y Monte Carlo la remuestrea.

La distancia `W₁(μ, δPs)` está en MW y **no es por sí sola un costo**. Si ambas penalizaciones son iguales a `c`, `U(Ps) = Δt·c·W₁(μ, δPs)`. Si difieren, se deben ponderar por separado las distancias a izquierda y derecha; la suma ponderada es un costo de transporte direccional, no la distancia métrica W₁ estándar. Tras el respaldo, se repite la comparación usando la distribución de potencia neta entregada; a la penalización residual se agrega el costo de operación del respaldo.

Los datos predeterminados y el CSV de ejemplo son **sintéticos**; una comparación no es automáticamente una validación independiente. Los costos corresponden a un generador y a un intervalo, no a un despacho de red. El radio ε no garantiza cobertura estadística sin calibración y validación. La cota Lipschitz no certifica estabilidad ni cubre directamente indicadores discontinuos de falla. Más detalles: [`docs/methodology.md`](docs/methodology.md).

## Requisitos y ejecución local

Probado localmente con **Python 3.13**. Las dependencias de ejecución están fijadas en `requirements.txt`; las de prueba, en `requirements-dev.txt`. En el directorio del proyecto:

```bash
# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
streamlit run app.py
```

En Windows PowerShell:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run app.py
```

Abra la dirección local mostrada por Streamlit. Para instalar también herramientas de prueba y ejecutarlas:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest tests -q
```

El flujo `.github/workflows/ci.yml` está configurado para ejecutar las pruebas en Python 3.12 y 3.13 **después** de subir el repositorio; la presencia del archivo no significa que CI ya se haya ejecutado.

## Datos propios y privacidad

Seleccione **Cargar CSV** en la barra lateral. El archivo UTF-8 debe tener separador coma, entre 1 y 5.000 filas y tamaño máximo 2 MB:

```csv
p_mw,split,weight
45.5,reference,1
60.0,reference,2
38.0,comparison,1
52.0,comparison,1
```

- `p_mw`: potencia disponible en MW, finita y dentro de `[0, Pmax]` configurado.
- `split`: `reference` o `comparison`; ambos grupos son obligatorios.
- `weight`: opcional; si aparece, todos los pesos deben ser finitos y estrictamente positivos. Los pesos se normalizan **por grupo**. Los valores repetidos se agregan.
- No se descartan filas inválidas: un archivo inválido detiene el cálculo y muestra un error. El archivo [`examples/synthetic_scenarios.csv`](examples/synthetic_scenarios.csv) es un ejemplo sintético para una capacidad de 100 MW.

**Un archivo cargado se transmite al servidor donde se ejecuta Streamlit**. No cargue datos sensibles o confidenciales en una instancia pública sin autorización, controles, infraestructura y acuerdos apropiados. La app no necesita claves, tokens ni otros secretos. Consulte [`docs/methodology.md`](docs/methodology.md) para las limitaciones de la entrada escalar.

## Publicar en GitHub

Este proyecto **está preparado**; esta sesión no ha creado un repositorio remoto ni ha hecho `push` por usted. Para publicarlo con su cuenta:

1. Descomprima el paquete y abra una terminal en `ucf-utopys-lab/`. Revise el contenido, los derechos y los datos antes de hacerlo público. No hay una licencia seleccionada; añada la que usted decida si desea otorgar permisos de reutilización.
2. En GitHub, cree un repositorio **vacío** (sin README, licencia ni `.gitignore` iniciales) y copie su URL. Elija público o privado según sus necesidades.
3. Ejecute, sustituyendo el ejemplo por su URL real:

```bash
git init -b main
git status --short
git add .
git commit -m "Initial UCF UTOPYS research prototype"
git remote add origin https://github.com/TU_USUARIO/TU_REPOSITORIO.git
git push -u origin main
```

Si Git solicita identidad para el commit, configure su nombre y correo (`git config user.name` y `git config user.email`). GitHub solicitará autenticación mediante su método autorizado; **no incluya tokens en el código, la URL, el README ni en este chat**. Compruebe el repositorio y la pestaña Actions para ver si CI finalizó.

## Desplegar en Streamlit Community Cloud

Tras subir el repositorio:

1. Entre en [share.streamlit.io](https://share.streamlit.io/) e inicie sesión/conecte su cuenta de GitHub según las instrucciones del servicio.
2. Seleccione **Create app**; elija su repositorio, la rama `main` y el archivo principal `app.py`.
3. En **Advanced settings**, seleccione **Python 3.13** (versión probada localmente). `requirements.txt` se instalará desde la raíz. No se requieren secretos.
4. Pulse **Deploy**, espere la instalación y revise la URL resultante en escritorio y móvil. Pruebe ambos idiomas, sliders, animaciones y, si procede, el CSV sintético.
5. Recuerde que la visibilidad y acceso de una app desplegada dependen de su configuración y del servicio; no la utilice para información sensible sin controles apropiados.

Guías oficiales: [despliegue Streamlit](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy), [dependencias](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies), [publicar código en GitHub](https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github).

## Estructura

```text
app.py                         Interfaz Streamlit bilingüe
ucf_core.py                    UCF discreta, W₁, DRO y CSV
analytic_ucf.py                UCF beta cerrada, Monte Carlo y W₁ hacia Dirac
firming.py                     Respaldo ilustrativo en un intervalo y costos
plots.py                       Gráficos interactivos Plotly
animations.py                  Animaciones SVG autocontenidas
requirements.txt               Dependencias de ejecución
requirements-dev.txt           Dependencias de prueba
.streamlit/config.toml         Tema y límite de carga
.github/workflows/ci.yml       Pruebas automáticas en GitHub Actions
examples/synthetic_scenarios.csv Datos de ejemplo sintéticos
assets/UCF_Wasserstein_Explorer.html  Explorador autónomo anterior (sin respaldo ni animaciones nuevas)
docs/methodology.md            Fórmulas, alcance y validación
docs/sources.md                Fuentes y correspondencia con UTOPYS
docs/verification.md           Resultados y pruebas locales
tests/                         Pruebas matemáticas y de la interfaz
```

## English quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
streamlit run app.py
```

Choose **English** in the sidebar. The pages are ordered UCF Explorer, Wasserstein + DRO, and UTOPYS fit. On pages 02 and 03, change **Ps** using the in-page slider linked to the sidebar; choose a battery/ESS, dispatchable backup or no backup and explore a separate renewable-power scenario. Analytic cost and Monte Carlo both apply the same selected single-interval backup rule. The Dirac comparison shows transport before and after backup; add backup operating cost separately. The DRO section remains **without backup**. This assumes ideal response and the same initial energy in each scenario, not a multi-period controller or reliability guarantee. For equal penalties `U = Δt·c·W₁`; otherwise, weight each direction separately. Default data are synthetic. CSV files are uploaded to the Streamlit server; do not upload sensitive data without authorisation and appropriate infrastructure. For testing, install `requirements-dev.txt` and run `python -m pytest tests -q`. To deploy, push the project to your own GitHub repository and select `app.py` with Python 3.13 in Streamlit Community Cloud. No deployment has been performed by the preparer.

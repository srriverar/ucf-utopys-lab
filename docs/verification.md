# Registro de verificación local

Fecha de preparación: 2026-10-31. Estas verificaciones se refieren al **prototipo local**, no a UTOPYS, a una instalación EMT ni a un despliegue público.

## Comparación analítica, Monte Carlo y Dirac sin respaldo

Con `Pmax=100 MW`, `Ps=55 MW`, `c_o=100 €/MWh`, `c_u=35 €/MWh`, `Δt=1 h` y una beta **continua** de referencia con media 55 % y concentración 16. La fila Monte Carlo corresponde a seleccionar **Sin respaldo**; la aplicación abre con batería por defecto:

| Magnitud | Resultado aproximado |
|---|---:|
| UCF beta continua, expresión analítica | €659,3240 / intervalo |
| Monte Carlo, 100.000 muestras, semilla 42 | €659,1493 / intervalo |
| Diferencia absoluta del ejemplo Monte Carlo | €0,1747 / intervalo |
| Error estándar Monte Carlo estimado | €1,9938 / intervalo |
| `W₋` y `W₊`, integrando independientemente la CDF | 4,883881 MW cada uno |
| `W₁(beta, δPs) = W₋ + W₊` | 9,767763 MW |
| `Δt(c_o W₋ + c_u W₊)` | €659,3240 / intervalo |

La coincidencia de Monte Carlo es específica de esta semilla, muestra y modelo; otras realizaciones difieren. `W₁` está en MW: con penalizaciones distintas, la comparación en euros exige los dos componentes ponderados. Las 17 partículas de la animación son ilustrativas; las barras se calculan con toda la distribución.

## Batería ilustrativa en el mismo ejemplo

Con batería de `20 MW` de descarga y carga, `40 MWh` útiles, SOC inicial `50 %`, eficiencias de carga y descarga `90 %` y costo operativo `10 €/MWh` de energía AC:

| Magnitud | Resultado aproximado |
|---|---:|
| Límite efectivo de descarga / carga durante 1 h | 18 / 20 MW |
| Escenario `P=40 MW`: descarga, potencia neta | 15 MW, 55 MW |
| Energía final y SOC del escenario `P=40 MW` | 3,333 MWh, 8,33 % |
| Penalización residual esperada | €43,1549 / intervalo |
| Operación esperada del respaldo | €92,2103 / intervalo |
| Costo total esperado analítico | €135,3652 / intervalo |
| Monte Carlo con la misma regla, 100.000 muestras, semilla 42 | €135,1462 / intervalo |
| Diferencia absoluta / error estándar estimado | €0,2191 / €0,6503 |
| `W₁` de potencia neta posrespaldo hacia `δPs` | 0,546732 MW |
| Probabilidad de ausencia de déficit residual | 92,7075 % |
| Probabilidad de coincidencia exacta con `Ps` | 88,1595 % |

Estas probabilidades son condicionales al modelo ilustrativo, a la distribución y al mismo estado inicial en cada escenario. La prueba no es una garantía de firmeza; no modela la continuidad temporal del SOC, red, fallas ni inversión.

## Comparaciones y DRO sobre la referencia discretizada y sin respaldo

La aplicación original también representa la beta por **200 puntos medios** para sus curvas UCF y su DRO. Para los mismos parámetros, esta aproximación produce UCF ≈ €659,37 / intervalo y un mínimo UCF de 47,25 MW. Con la beta de comparación sintética (media 40 %, concentración 10), `W₁` entre las dos **medidas discretas** es aproximadamente 15 MW, el costo de comparación es €1.681,23 y la diferencia €1.021,86 no supera la cota €1.500. Para `ε=12 MW`, el DRO en `Ps=55` es ≈ €1.859,37 y su mínimo sobre la malla utilizada es 24,50 MW. La comparación está fuera de esa bola de radio 12 MW.

La ligera diferencia entre €659,3240 y €659,37 refleja modelos numéricos distintos: beta continua frente a aproximación discreta, no una discrepancia del cálculo.

## Pruebas automáticas

- Python 3.13.16 y dependencias fijadas: `python -m pytest tests -q` → **106 pruebas aprobadas**.
- El dual DRO se contrastó con un LP primal de transporte formulado por separado: **160 casos** aleatorios reproducibles y **18 casos adicionales** con una penalización nula, distintos horarios y radios.
- La UCF beta cerrada se contrastó con cuadratura independiente de la PDF; la comparación con Dirac integra la CDF y se verificó para penalizaciones iguales, distintas o nulas, en extremos del soporte y para medidas empíricas con átomos.
- El respaldo se contrastó con integración independiente de la PDF beta y Monte Carlo, además de **80 casos aleatorios ponderados** comparados con despacho directo; se probaron límites de energía/potencia, SOC final, reserva despachable, átomos empíricos en los límites, escenarios sin batería y costos operativos superiores a las penalizaciones.
- Se comprobaron controles de Ps bidireccionales y persistencia al navegar/cambiar idioma, modos de respaldo, límites al reducir Pmax, Monte Carlo, cuantiles, intervalos subgradiente, costos y áreas, radios y penalizaciones cero, monotonía y cota, CSV válidos e inválidos, datos de animación y navegación de tres páginas.
- El flujo de GitHub Actions está incluido pero **no se ha ejecutado remotamente**. Python 3.12 figura en la matriz de CI; esta ejecución local se realizó con 3.13.

## Navegador local

Con Streamlit local y Chromium se comprobó el orden **02 → 03 → 01**, navegación ES/EN y sincronización bidireccional entre el Ps visible en las páginas y el de la barra lateral. Se probaron batería con energía cero, reserva con energía limitada, ausencia de respaldo, conservación de ajustes, respuesta del escenario y actualización inmediata de costos. Se verificaron reproducción y pausa de las animaciones, Monte Carlo con respaldo, transporte a `Ps` antes y después del respaldo, coincidencia de barras residuales y distinción entre penalización y operación. Se comprobó la identidad simétrica para `c_o=c_u=100`, la carga y persistencia del CSV sintético al cambiar idioma y el rechazo de un CSV inválido. En una ventana móvil de 390 px se modificó Ps en 02 y 03 y se verificaron los resultados y animaciones sin desbordamiento horizontal ni errores JavaScript detectados.

Estas pruebas no demuestran exactitud de datos de campo, representatividad estadística, seguridad de una instancia pública, funcionamiento futuro del servicio de nube, ni validez física o beneficios operativos.

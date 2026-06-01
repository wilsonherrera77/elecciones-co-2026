# Cómo leer los mapas y los resultados · elecciones-co-2026

Este documento explica qué muestra cada mapa, de dónde salen los cálculos y cómo interpretar la información para la estrategia de **segunda vuelta presidencial Colombia 2026**.

---

## Contexto numérico básico (todos los mapas parten de aquí)

| Indicador | Valor |
|---|---:|
| Censo electoral nacional | 41.421.973 |
| Votos válidos 1ra vuelta | 23.668.108 |
| Espriella (Defensores de la Patria) | 10.351.548 · 43,74% |
| Cepeda (Pacto Histórico) | 9.683.743 · 40,91% |
| Brecha 1ra vuelta | 667.805 votos (Espriella +2,83 pp) |
| Municipios analizados | 1.189 |
| Escrutinio al cierre de captura | 99,92% |

Cepeda perdió la 1ra vuelta por 668 mil votos pero pasó a segunda vuelta. Para ganar el balotaje se necesita superar el 50% + 1 de los votos válidos en ese acto. Con el turnout histórico colombiano en segundas vueltas (sube ~5 puntos porcentuales respecto a la primera) el universo proyectado es ~25,7 millones de votos válidos, y por lo tanto **se necesitan ~3 millones de votos adicionales para Cepeda**.

---

## Mapa 1 · Afinidad Cepeda

**Qué muestra**: el porcentaje de votos válidos que obtuvo Cepeda en cada uno de los 1.189 municipios.

**Lectura del color**:

- Verde oscuro (>65%): bastión Cepeda (Pacífico afro, sur andino, Amazonía, Caribe + Magdalena Medio).
- Verde claro (50-65%): zonas favorables consolidadas.
- Beige (35-50%): zona en disputa, sin ganador claro.
- Rojo claro (15-35%): zonas de baja afinidad, voto disperso o competido.
- Rojo oscuro (<15%): territorio hostil (rurales conservadores, eje cafetero ortodoxo, Antioquia rural uribista).

**Para qué sirve**: identifica de un vistazo los corredores territoriales donde la marca Cepeda/Pacto Histórico ya está construida y aquellos donde hay que partir desde cero.

**Cálculo**:

```
afinidad_municipio = votos_cepeda_municipio / votos_validos_municipio × 100
```

---

## Mapa 2 · ¿Quién ganó cada municipio?

**Qué muestra**: el partido cuyo candidato obtuvo más votos en cada municipio en la 1ra vuelta.

**Lectura del color**:

- Verde: Cepeda fue el más votado (432 municipios).
- Rojo: Espriella fue el más votado (756 municipios).
- Gris: ganó un tercer candidato (1 municipio).

**Para qué sirve**: la geografía electoral colombiana se polariza. Cepeda gana en cabeceras costeras (Barranquilla, Cartagena, Santa Marta), Pacífico, sur del país. Espriella gana en la mayoría de municipios rurales del eje cafetero, Antioquia rural, Cundinamarca rural. Hay que cuantificar más allá del color para saber si el ganador local pesa mucho o poco en número de votantes.

**Cálculo**: para cada municipio se toma el partido con mayor `votos` en la tabla del snapshot.

---

## Mapa 3 · Brecha en votos Cepeda − Espriella

**Qué muestra**: la diferencia ABSOLUTA en votos entre Cepeda y Espriella por municipio. La escala va de −20.000 a +20.000.

**Lectura del color**:

- Verde oscuro (+20.000 a +5.000): Cepeda gana con margen amplio en términos absolutos.
- Verde claro (+5.000 a 0): Cepeda gana con margen estrecho.
- Beige (cerca de 0): empate técnico (atención prioritaria).
- Rojo claro (0 a −5.000): Espriella gana con margen estrecho.
- Rojo oscuro (−5.000 a −20.000): Espriella gana con margen amplio en votos.

**Para qué sirve**: a diferencia del Mapa 1 (porcentual) y el Mapa 2 (binario), este muestra la MAGNITUD del esfuerzo necesario. Ganar un municipio donde la brecha es 50 votos es muy distinto a uno donde es 50.000.

**Cálculo**:

```
brecha = votos_cepeda - votos_espriella
```

Un valor negativo significa que Cepeda perdió por esa cantidad de votos en el municipio.

---

## Mapa 4 · Score de oportunidad 2da vuelta (el mapa clave para campaña)

**Qué muestra**: una puntuación combinada que estima cuántos votos NUEVOS puede sumar Cepeda en cada municipio de cara al balotaje. Es el mapa más importante para decidir dónde invertir recursos.

**Lectura del color**: la escala YlGnBu va de amarillo claro (score bajo) a azul oscuro (score alto). Los municipios en azul oscuro son aquellos donde:

- Hay muchos no-votantes (techo de turnout sin explotar).
- Cepeda ya tiene una afinidad mínima (no es zona perdida).
- Existe un margen de victoria capturable contra Espriella.

**Para qué sirve**: focalizar la campaña en los 200-300 municipios con mayor score. Estos suman la mayor parte del potencial de los 3M votos extra. No tiene sentido invertir igual en todos los 1.189 municipios.

**Fórmula del score**:

```
no_votantes = censo_electoral - votos_validos
score = (afinidad_cepeda × no_votantes) + min(10.000, max(0, brecha_a_favor_de_espriella)) × 0,5
```

Componentes:

- **afinidad × no_votantes**: votos que Cepeda recupera si mueve un porcentaje del electorado que no fue a votar.
- **brecha_capturable**: contempla un piso (0) y un techo (10.000) para que un municipio donde se pierde por margen recuperable contribuya al score, sin que dominen los outliers.

---

## Los 4 cuadrantes operativos (más allá de los mapas)

Cada municipio se etiqueta en un cuadrante según el margen porcentual Cepeda vs Espriella en la 1ra vuelta:

| Cuadrante | Definición | Mpios | Estrategia |
|---|---|---:|---|
| **Q1 Defender** | Cepeda ganó · afinidad ≥40% | 425 | Proteger turnout · testigos en cada puesto · brigadas de transporte |
| Q1 Defender frágil | Cepeda ganó pero <40% afinidad | 6 | Reforzar antes que se pierda |
| **Q2 Movilizar** | Diferencia absoluta ≤10 pp | 81 | Aquí se gana o se pierde · puerta a puerta · capturar voto blanco |
| **Q3 Convertir** | Gap 10-30 pp a favor de Espriella | 240 | Persuasión: coalición Dignidad & Compromiso + voto blanco urbano |
| Q4 Resistir | Gap >30 pp a favor de Espriella | 437 | Territorio hostil · piso digno >20% · no derrochar recursos |

---

## ¿De dónde salen los 3 millones? · simulación numérica

Bajo supuestos conservadores aplicados por cuadrante:

| Cuadrante | % no-votantes movilizables | Afinidad de los nuevos votos | % voto blanco capturado | Aporte estimado |
|---|---:|---:|---:|---:|
| Q1 Defender | 10% | 55% | 20% | ~606.000 |
| Q1 Defender frágil | 8% | 50% | 20% | ~900 |
| Q2 Movilizar | 12% | 55% | 20% | ~65.000 |
| Q3 Convertir | 8% | 35% | 35% | ~113.000 |
| Q4 Resistir | 3% | 20% | 20% | ~41.000 |
| **Total proyectado** | | | | **~826.000** |

Con estos supuestos conservadores quedan 2,17M faltantes para los 3M. **Esto significa que la meta de 3M es ambiciosa pero alcanzable si la campaña empuja al menos uno de los siguientes apalancamientos**:

1. **Subir el % movilizado en Q1 Defender del 10% al 18%** (esto solo aporta +1M extra). Aquí está la mayor palanca por volumen.
2. **Subir la conversión en Q3 del 35% al 50%** (coalición efectiva con centro/Dignidad/voto blanco). Aporta +400K extra.
3. **Mejorar la afinidad de los nuevos votantes en Q2 del 55% al 65%** (campaña narrativa local fuerte). Aporta +100K extra.

---

## Foco operativo recomendado

1. **Q1 Defender es el reservorio principal**: 10,1 millones de no-votantes en municipios donde Cepeda ya gana. NO descuidar este cuadrante por la trampa de "ya está ganado". Si el turnout cae, la elección se pierde acá.
2. **Q2 Movilizar son los 81 municipios decisivos**: Neiva, Dosquebradas, Cartago, Girardot, Sogamoso, Duitama, La Dorada, Espinal. La diferencia es menor a 10 puntos. Aquí ganar el balotaje pasa por testigos electorales y transporte el día E.
3. **Q3 Convertir es el campo de batalla urbano**: Pereira, Ibagué, Bello, Villavicencio, Manizales, Armenia. Espriella entre 45-55%, Cepeda 28-35%. Coalición con Dignidad + voto blanco son la clave.
4. **Q4 Resistir es contención de daños**: no invertir recursos en 437 municipios donde la matemática no da.

---

## Fuente y reproducibilidad

Todos los datos provienen del portal público de la Registraduría Nacional del Estado Civil (`https://resultados.registraduria.gov.co/`). Los CSVs de cada cuadrante, los CSVs de top 200 oportunidad y top 100 defender, los 4 mapas HTML interactivos y el Word ejecutivo por departamento están en la sección **Descargas** de la web pública.

Web: <https://wilsonherrera77.github.io/elecciones-co-2026/>

Código fuente: <https://github.com/wilsonherrera77/elecciones-co-2026>

---

Wilson Herrera Quiroga · 2026 · MIT License

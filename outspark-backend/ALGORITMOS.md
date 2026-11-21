# Algoritmos: implementación y respaldo del curso

Este archivo registra el vínculo entre el código y el material de **Complejidad Algorítmica, ciclo 6**. La revisión es focalizada en las páginas indicadas; no declara revisado todo el curso. Los PDF originales permanecen en el directorio del curso y no se redistribuyen en el repositorio.

| Función | Base del curso | Implementación | Estado |
| --- | --- | --- | --- |
| Recorrer las ramas de republicación | Semana 5.1, pp. 8–9: DFS, pila LIFO, visitados y listas de adyacencia | `outspark/publishing/domain/services/traversal.py: tree_dfs` | Implementada y probada |
| Seleccionar el feed diverso | Semana 12, pp. 3–4: elección local factible, sin revertir decisiones; condiciones de optimalidad | `outspark/discovery/domain/services/selection.py: select` | Adaptación propia de la técnica voraz, implementada y probada |
| Reconstruir una ruta de llegada | Representación del grafo del curso; especialización de padre único | `outspark/publishing/domain/services/provenance.py: routes` | Implementada; sigue padres en un mapa ya cargado |
| BFS del histórico | Semana 5.1, pp. 12–13: niveles, FIFO, visitados y O(V+E) | `outspark/network_analysis/domain/services/reach.py: breadth_first_reach` | Implementada sobre adyacencias importadas en DynamoDB; cuaderno de TB1 conservado |

## BFS del histórico desde DynamoDB

La página 12 expande primero todos los nodos de profundidad d y después los de d+1; la página 13 presenta la cola de no visitados, la marca de visitados y O(V+E). Ambas páginas se verificaron en texto e imagen el 12/10/2026.

La implementación procesa una frontera completa por ronda, mantiene visitados y construye la frontera siguiente sin ordenar. Esta organización conserva el orden por niveles de BFS y permite recuperar adyacencias con BatchGetItem. No cuenta dos veces los nodos alcanzados por varios caminos.

El cálculo sobre las adyacencias recuperadas cuesta O(Vr+Er) y guarda visitados/fronteras O(Vr), más la materialización de las adyacencias de la frontera. Vr y Er son los nodos y relaciones examinados hasta el límite de saltos, no necesariamente todo el grafo. El IO, los bloques y la deserialización se registran aparte. La API admite 1–3 saltos y 128 peticiones de lectura por lotes; exceder el presupuesto devuelve 422 en vez de afirmar cobertura completa.

La red usa 817 090 amistades únicas no dirigidas. Se conservan todas las filas dirigidas originales y sus fechas por separado. El alcance BFS expresa posibilidad topológica; no prueba que un mensaje se leyó, persuadió o se republicó históricamente. La procedencia de republicaciones nuevas sigue perteneciendo a Publishing y se calcula con DFS.

## DFS de procedencia

Construye el mapa de eventos y las listas de hijos, comienza en el original y usa una pila explícita con profundidad. Registra visitados y verifica padres, original común, raíz única y cobertura completa. Un componente desconectado o ciclo provoca error. La pila evita depender del límite de recursión de Python.

Con R eventos y T enlaces, tiempo O(R+T), memoria O(R+T); en este dominio cada republicación tiene un único padre, por lo que T≤R−1 y la memoria es O(R). La lectura DynamoDB es un costo adicional, paginado y registrado. Reconstruir una ruta de longitud L cuesta O(L) con el mapa precargado; no se consulta una arista por cada paso.

Pruebas: ramas, padre ausente, otro original, ciclo y cadena de 1 500 eventos en el algoritmo puro. El endpoint interactivo admite 1 000; no confundir esa prueba pura con el límite de la API.

## Selección voraz del feed

En cada paso se recorre el conjunto pendiente y se elige la mejor tarjeta factible. Se admiten hasta k=10 tarjetas y hasta dos del mismo autor original. La relevancia propia es `r = 0.7·coincidencia_de_temas + 0.3·recencia`, con recencia lineal en siete días. La ganancia es `r + 0.3` si la comunidad aún no fue seleccionada; en otro caso es r. Desempata por actividad más reciente e identificador.

Objetivo de diseño: `F(S) = Σ r(p) + 0.3·|comunidades(S)|`. Los pesos, cupos y fórmula son decisiones de Outspark, **no un ejemplo del profesor**. Se usa la técnica voraz del curso sin afirmar que este problema cumple las condiciones necesarias para garantizar un óptimo.

El feed cronológico usa el mismo conjunto materializado, deduplicación y cupo por autor; compara fechas en lugar de ganancia. Ambos guardan hash de candidatos, instante, versión de preferencias, parámetros y métricas. Tiempo del selector O(kC), con temas acotados; memoria O(C+k). Recuperación, agrupación, ordenación de fuentes e IO se miden/aprecian aparte y no se incluyen artificialmente en esa cota.

Una prueba pequeña enumera subconjuntos factibles y contrasta el objetivo con la referencia exacta. Coincidir en ese caso no constituye prueba general de optimalidad ni evidencia de satisfacción del usuario.

## Simulador de difusión de una publicación

Python calcula capas BFS en listas de adyacencia, con visitados y un límite de uno a tres saltos. El primer salto usa los contactos que seleccionó el plan y el origen queda visitado desde el inicio. Se cuentan perfiles distintos sin incluir el origen. El modelo representa alcance potencial sobre el histórico.

**Más conexiones** ordena las amistades directas por grado descendente. **Mayor alcance** aplica selección voraz y elige en cada paso el contacto cuya cobertura añade más perfiles. Los empates se resuelven por ID ascendente. La función objetivo es la unión de perfiles alcanzables bajo un presupuesto común de contactos iniciales. Los mapas de bits almacenan el resultado de cada BFS y permiten deduplicar las uniones por salto.

La BFS se apoya en `01_2_BFS_y_Lista_de_Adyacencia_LA.ipynb`, celda 4. La elección local voraz se apoya en `Semana12-Algoritmos-Voraces-y-DP.pdf`, p. 3. Maximizar la cobertura de contactos es una adaptación del criterio del curso y la selección voraz puede quedar por debajo del óptimo global.

## Fuentes verificadas

1. `Unidad 1/Semana 5/Semana5.1-Grafos-Tecnicas de recorrido y busquedas.pdf`, pp. **8–9**. Texto y ambas páginas inspeccionados visualmente. SHA-256: `237a5dcaa93e507711d49c6b5684d1e5704f91210c55c289b07efaae9e89bdca`.
2. `Unidad 2/Semana 11/Semana12-Algoritmos-Voraces-y-DP.pdf`, pp. **3–4**. Texto y ambas páginas inspeccionados visualmente. SHA-256: `dec386f09e4ffe3896b042fa7144166ebe8e5735f7d79eff4d77c847323fef4c`.

## Componentes conexas y grado — versión vigente, 21/10/2026

`network_analysis/domain/services/structural.py` reinicia BFS en cada nodo pendiente, con cola en lista, índice de lectura y visitados. Asigna a cada componente el menor identificador de sus nodos. La construcción y validación cuestan O(V+E); ordenar el ranking por grado añade O(V log V). Memoria O(V+E), incluida la copia de adyacencias para comprobar reciprocidad; el recorrido auxiliar usa O(V).

Fuente directa: `Unidad 1/Semana 5/Tipos de Recorridos en MA y LA/01_2_BFS_y_Lista_de_Adyacencia_LA.ipynb`, celdas **4, 8 y 10** (numeración humana): BFS, lectura y Graphviz. El índice de lectura evita desplazar la cola con `pop(0)` y es una adaptación explícita. No se atribuye O(V+E) a la versión literal con `pop(0)` en listas grandes.

Se retiraron CNM, modularidad, ganancias de fusión, invalidación perezosa del heap y ranking de grupos ajenos. La función actual calcula componentes conexas, no comunidades por densidad. No hay aristas entre componentes; el ranking muestra exclusivamente número de vecinos directos, que no demuestra influencia.

Resultado reproducido sobre 63 731 nodos y 817 090 aristas: **144 componentes**, mayor componente de **63 392 nodos**, grado máximo **1 098** en el nodo 2332. El alcance desde 1 es 26, 1 720 y 27 369 usuarios acumulados en 1–3 saltos. Evidencia: `evidencia/curso-2026-10-21/analisis-bfs-completo.json` y el notebook `Outspark_solo_clase.ipynb` del repositorio del grafo. Los 870 grupos y tiempos del método retirado no son resultados vigentes.

La consulta rechaza un resultado guardado cuyo método difiera de `outspark-bfs-components/2.0`. Se recalculó y guardó una ejecución BFS completa en DynamoDB Local, manteniendo las fuentes históricas y sus hashes. No se modificó un despliegue remoto.

## Dibujo y dependencia académica

En `outspark-facebook-grafo/algoritmos_curso.py` el único import es `graphviz as gv`. Se construyen listas de adyacencia con lectura `open`, `split`, índices `labels/w2i`, listas y conjuntos para evitar duplicados. El notebook oficial de orden topológico de semana 6–7 muestra `labels/w2i`; el dibujo `sfdp` está en `05_02_dijkstra_adj_list.ipynb`, celda 5. Componentes y distancias se calculan en nuestro Python, no por una biblioteca de redes.

`grafo_facebook.py` conserva utilidades de compresión, hashes, rutas, argumentos y JSON para reproducir el análisis del archivo original. No se atribuyen al docente ni forman parte del núcleo académico. Flutter, API y DynamoDB se conservan como presentación/persistencia, conforme al permiso de GUI del enunciado 2026-20 p. 2. Esto no equivale a afirmar que todo el stack fue enseñado en clase.

El selector de feed conserva la técnica voraz del material semanal citado arriba. Se retiró `collections.Counter` y se usa un diccionario con conteo explícito. La función objetivo de producto sigue siendo una adaptación propia que debe sustentarse, sin garantía de optimalidad. No se incorporan algoritmos externos para justificarla.


## Trazabilidad y evidencia del Hito 2 — 08/11/2026

Se reejecutaron el notebook académico completo, la comprobación HTTP y el análisis offline. La evidencia fijada está en `outspark-report/entregas/TB2/evidencia/`: `demo-http.json`, `analisis-bfs-actual.json`, `Outspark_Hito2_ejecutado.ipynb` y `fuentes-curso.json`. Los tiempos del resultado persistido anterior siguen siendo históricos y no se presentan como nuevas mediciones.

- `Trabajo/2026-20/01 - Consigna y rúbrica/TB1_1ACC0184_2026-20_Enunciado.pdf`, pp. 1–5; Hito 2 p. 4. SHA-256: `fe7411d34ff415f922257b366bf1b388f45d57a7654f4eb4a710ef8bec0e61fd`.
- `Unidad 1/Semana 5/Semana5.1-Grafos-Tecnicas de recorrido y busquedas.pdf`, DFS pp. 8–9; BFS pp. 12–13. SHA-256: `237a5dcaa93e507711d49c6b5684d1e5704f91210c55c289b07efaae9e89bdca`.
- `Unidad 1/Semana 5/Tipos de Recorridos en MA y LA/01_2_BFS_y_Lista_de_Adyacencia_LA.ipynb`, celdas 4, 8 y 10, contadas desde 1. SHA-256: `a8e2917639b59fd12f0e1af5f770588c3b90a9ca3158a95d30916eede595a8f1`.
- `Unidad 1/Semana 4/04_02_Lista_Adyacencia_CA.ipynb`, lectura, adyacencias y Graphviz. SHA-256: `ec78fc541c4ece2f21d442bc791997204499bebde45547cc9cfe8232cc31f36b`.
- `Unidad 1/Semana 5/05_02_dijkstra_adj_list.ipynb`, celda 5, Graphviz sfdp. SHA-256: `58f771a75875fb79528ac1ff3631484fe17648fe22253b69d564ac65fe2683cb`.
- `Unidad 1/Semana 6-7/06_01_Ordenamieno_Topologico.ipynb`, labels/w2i, celdas 4–6. SHA-256: `d6a1d33d9ff413288a760e9d489701be7108e13eb6e21e7afc6681158f11f8ed`.
- `Unidad 2/Semana 11/Semana12-Algoritmos-Voraces-y-DP.pdf`, pp. 3–4. SHA-256: `dec386f09e4ffe3896b042fa7144166ebe8e5735f7d79eff4d77c847323fef4c`.

El archivo de amistades conserva SHA-256 `32d149f76c3421a08b03bfc629a9de6ce65b6fa56272cd9d5424e3de5b1acff2`; el muro, `c4449336e346061068b8278d09176b195b3f132f6d6fe50adbc5730938496dca`. El script de demostración es infraestructura de verificación y no se presenta como núcleo didáctico ni como código enseñado en clase.

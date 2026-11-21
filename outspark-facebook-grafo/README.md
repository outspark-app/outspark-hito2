# Outspark: grafo histórico de Facebook

Versión adaptada al material del curso. El cuaderno de trabajo es `Outspark_solo_clase.ipynb`, apoyado por `algoritmos_curso.py`. `preparar_datos_curso.py` prepara las entradas. `grafo_facebook.py` permite ejecutar la preparación y visualización por terminal.

El archivo se lee fila por fila. El grafo es un diccionario de adyacencias con conjuntos de vecinos para reunir duplicados, sin bibliotecas de análisis de redes. Componentes y alcance se calculan con BFS propia, cola en una lista y visitados. Graphviz dibuja nodos y aristas con `Graph`, `node`, `edge` y `sfdp`, como los notebooks oficiales. No se calcula una distribución de fuerzas con otra biblioteca ni se reubican componentes a mano.

Fuentes del curso (celdas numeradas desde 1):

- `Unidad 1/Semana 4/04_02_Lista_Adyacencia_CA.ipynb`: diccionario de listas, lectura y Graphviz.
- `Unidad 1/Semana 5/Tipos de Recorridos en MA y LA/01_2_BFS_y_Lista_de_Adyacencia_LA.ipynb`, celdas 4, 8 y 10: BFS, lectura y dibujo.
- `Unidad 1/Semana 5/05_02_dijkstra_adj_list.ipynb`, celda 5: dibujo Graphviz con `layout="sfdp"`.

La cola con índice de lectura evita desplazar una lista con `pop(0)`: es una adaptación explícita, no una función entregada por el docente. Recorrer componentes cuesta O(V+E); ordenar sus tamaños añade O(C log C). El dibujo tiene costo propio de Graphviz.

Los `.gz` son los originales históricos MPI-SWS/WOSN 2009. Los módulos de compresión, hashes, rutas, JSON y argumentos sirven para preparar y registrar datos; no son algoritmos atribuidos al curso. El código académico usa estructuras de Python y Graphviz. El notebook `Outspark_solo_clase.ipynb` contiene una alternativa estricta sobre archivos de texto, con Graphviz como único import.

Se conservan las entregas anteriores y sus resultados como antecedentes; no prueban la ejecución de esta versión. Una componente conexa no es una comunidad por afinidad; grado y alcance no demuestran influencia ni circulación histórica de una publicación.

Ejecutar localmente con Python 3.12 y Graphviz:

```sh
python grafo_facebook.py --links facebook-links.txt.gz --wall facebook-wall.txt.gz --out resultados_curso
```

La aplicación Flutter y la API son infraestructura de presentación. El enunciado 2026-20 p. 2 permite una GUI en cualquier lenguaje; los algoritmos permanecen en Python. La versión de trabajo no se publica automáticamente.

La ejecución habitual analiza todos los nodos y dibuja una vista de 1 500 nodos inducidos por BFS más un detalle del usuario 1. El render íntegro es opcional con `--full-graph`: no se incluye como resultado ejecutado de esta adaptación. La consigna p. 4 permite grafo completo y/o subgrafos. El orden por ID para elegir la vista hace el mismo piloto reproducible en ambos programas; ordenar vecinos cuesta adicionalmente a BFS.

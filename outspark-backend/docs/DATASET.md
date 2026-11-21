# Dataset histórico completo en DynamoDB Local

La importación conserva los dos archivos MPI-SWS Facebook New Orleans/WOSN 2009 completos. El contexto `network_analysis` posee el histórico; Profiles posee las cuentas locales de simulación; Connections consume la topología mediante su ACL. Los eventos históricos de muro mantienen autor, destinatario y fecha, sin texto ni ID de contenido compartido. La [definición original de MPI-SWS](https://socialnetworks.mpi-sws.org/data-wosn2009.html) confirma que la segunda columna representa al autor y la primera al dueño del muro.

## Contenido

| Dato lógico | Cantidad en los archivos completos |
| --- | ---: |
| Usuarios presentes en amistades | 63 731 |
| Usuarios presentes solo en el muro | 160 |
| Usuarios totales y cuentas locales de simulación | 63 891 |
| Filas originales dirigidas de amistad | 1 545 686 |
| Amistades únicas no dirigidas | 817 090 |
| Referencias de vecinos en ambas direcciones | 1 634 180 |
| Eventos originales de muro | 876 993 |
| Filas de amistad con fecha | 905 565 |

Cada fila conserva su número de línea y su timestamp original; `\N` se representa como null. Las amistades se normalizan para recorrer el grafo, manteniendo también las filas originales sin deduplicarlas. Los eventos de muro se indexan por dueño y por autor; ambas proyecciones corresponden a los mismos eventos, no a dos datasets independientes.

Los archivos comprimidos originales se guardan también como bloques binarios de 256 KiB. Es posible recuperar sus bytes exactos desde DynamoDB y comprobar las dos sumas SHA-256 registradas en el manifiesto.

**Ítems físicos y filas del dataset son cantidades distintas.** Cada bloque de consulta contiene hasta 512 vecinos o registros. Así se conserva toda la información sin convertir cada fila en una escritura individual ni cargar una colección ilimitada en un solo ítem.

## Modelo físico y propiedad

El histórico reside en **Outspark-local-network-analysis**; las cuentas de simulación y preferencias en **Outspark-local-profiles**. Publishing conserva publicaciones nuevas en su propia tabla con dos GSI. [Distribución y copia íntegra desde el modelo inicial](PERSISTENCIA.md).

| Propietario / dato | PK | SK |
| --- | --- | --- |
| Network Analysis: manifiesto | `DATASET#facebook-wosn2009` | `MANIFEST` |
| Network Analysis: nodo y contadores | `DATASET#facebook-wosn2009` | `NODE#000000000001` |
| Network Analysis: vecinos | `DATASET#facebook-wosn2009#USER#1` | `ADJ#00000000` |
| Network Analysis: filas de amistad | misma partición del nodo dueño | `LINK#00000000` |
| Network Analysis: muro recibido / escrito | partición del nodo dueño / autor | `WALL_IN#00000000` / `WALL_OUT#00000000` |
| Network Analysis: bytes de origen | `DATASET#facebook-wosn2009#SOURCE#links` o `#SOURCE#wall` | `BLOCK#00000000` |
| Profiles: cuenta de simulación | `USER#fb-1` | `PROFILE` |

Los bloques históricos no escriben los GSI de Publishing. Las consultas HTTP usan GetItem, Query o BatchGetItem. La verificación administrativa de la importación recorre con Scan únicamente para comprobar todos los ítems del namespace; ese Scan no forma parte de los endpoints ni del feed.

## Importar y verificar

Con DynamoDB Local preparado y los repositorios hermanos en el mismo contenedor:

```bash
.venv/bin/python -m outspark.prepare
.venv/bin/python -m scripts.import_dataset
```

El comando admite únicamente el endpoint HTTP loopback y prefijos `Outspark-local` o `Outspark-local-test-*` mediante `--table-prefix`. Prepara las seis tablas y escribe el histórico únicamente en Network Analysis y los perfiles mediante el contrato de Profiles. Usa credenciales ficticias explícitas; no depende de perfiles AWS. La ruta de los archivos se puede cambiar con `--links` y `--wall`, pero sus hashes deben coincidir con los originales completos de referencia.

El importador:

1. Comprueba los hashes y todos los recuentos desde los archivos. SQLite prepara índices en un directorio temporal que se elimina al terminar.
2. Obtiene exclusión mediante un manifiesto IMPORTING. Las consultas históricas responden 409 durante la carga.
3. Escribe claves deterministas con lotes de hasta 25 ítems y reintentos acotados para UnprocessedItems.
4. Lee todos los ítems históricos desde DynamoDB y compara cardinalidad y suma modular de sus hashes SHA-256 con el inventario preparado. Comprueba los totales de nodos, vecinos, filas de amistad y ambas proyecciones de muro.
5. Reconstruye los bytes de los archivos almacenados y comprueba sus hashes SHA-256.
6. Profiles provisiona las cuentas de simulación, preservando los perfiles existentes y sus preferencias.
7. Publica READY mediante una escritura condicionada al token del importador.

Repetir el comando con un manifiesto READY verifica nuevamente el histórico y devuelve `replayed=true`. No reinicia la demo ni las preferencias. Si se interrumpe una primera carga, detén el importador anterior y usa `--resume`: calcula el inventario esperado y verifica lo ya escrito; si coincide, completa sin reescribirlo, y si está incompleto escribe de nuevo las mismas claves antes de verificar. Unos archivos distintos o un importador concurrente producen conflicto. No se expone una API de escritura del histórico.

La verificación usa páginas de Scan de hasta 100 ítems y el cliente administrativo admite lecturas de hasta 60 segundos. El compose de este dataset limita el contenedor a 4 GiB y el heap Java a 3 GiB, preservando el mismo volumen. Esto evita la lectura masiva que agotó el heap del emulador durante la primera comprobación. Las peticiones de la API mantienen su timeout habitual.

El recibo completo queda en `.local/importacion_dataset.json`, fuera de Git. La [evidencia resumida](../evidencia/dataset_completo.json) registra el resultado de la carga real.

## Usar el backend con la red importada

En [Swagger](http://127.0.0.1:18080/docs), Authorize admite `ana` y las otras cuentas de demo, o una cuenta histórica de simulación como `fb-1`. GET /api/me muestra `profile_origin=dataset_simulation`, `source_dataset_id` y `dataset_node_id`. El nombre «Usuario 1» es una etiqueta local; no es un nombre extraído de Facebook.

GET /api/me/contacts de una cuenta `fb-<id>` devuelve las amistades normalizadas del dataset. Se conservan inmutables; intentar retirarlas responde 409. Las conexiones propias de Ana/Bruno/Carla/Diego conservan sus operaciones habituales.

Las cuentas de simulación pueden unirse a las comunidades temáticas, configurar preferencias, publicar y republicar. Discovery usa los contactos históricos mediante Connections para obtener actividad nueva de esas cuentas. La transacción del snapshot comprueba tanto perfiles/originales como el manifiesto histórico READY. Los eventos de muro históricos se exploran con su endpoint específico; no se inventa un texto ni se convierte un registro de muro en una republicación.

Ejemplo de recorrido: `fb-1` se une a `diseno` y publica; `fb-2` republica su evento; `fb-3` genera un feed. En el dataset completo elige cuentas que estén relacionadas consultando primero vecinos o contactos. Usa los IDs de las respuestas reales y una Idempotency-Key distinta por operación.

## API de Network Analysis

Base: `/api/network/datasets/facebook-wosn2009`. Todas las operaciones requieren la identidad local o la identidad validada del adaptador Lambda.

| GET | Resultado |
| --- | --- |
| base | Fuente, hashes, estado y recuentos |
| `/nodes` | Nodos paginados, incluidos los que aparecen solo en el muro |
| `/nodes/{node_id}` | Grado y contadores del nodo |
| `/nodes/{node_id}/neighbors` | Vecinos únicos, paginados |
| `/nodes/{node_id}/friendship-records` | Todas las filas originales de amistad del dueño, incluidas fechas nulas |
| `/nodes/{node_id}/wall-events?direction=received` | Actividad recibida, en orden descendente por fecha y línea |
| `/nodes/{node_id}/wall-events?direction=sent` | Actividad escrita por ese autor |
| `/nodes/{node_id}/reach?max_hops=3` | BFS y alcance completo por nivel hasta los saltos indicados |

Las listas admiten limit de 1 a 50 y cursor de su propia consulta. BFS admite de uno a tres saltos, hasta 100 000 visitados y 128 peticiones BatchGet; superar el presupuesto responde 422, sin un resultado parcial presentado como completo. Registra peticiones y unidades de lectura. Esa métrica local no acredita latencia ni factura de AWS.

## Validación y alcance

Las pruebas aisladas verifican duplicados, fechas nulas, usuarios de muro, paginación entre bloques, orientación autor → dueño, integridad de bytes, reintentos, rechazo de bloques faltantes y el recorrido publicar → republicar → feed/procedencia sobre la topología importada. También comprueban que los endpoints funcionan después de eliminar los archivos fuente temporales del test.

La carga completa real quedó READY con 270 307 ítems históricos verificados y 63 891 perfiles de simulación. Los 65 ítems previos de la demo se compararon con el respaldo y permanecieron idénticos. La [demostración HTTP](../evidencia/demo_dataset_http.json) validó fb-1 → fb-2 → fb-3 y reprodujo los nuevos alcanzados desde el nodo 1: 26, 1 694 y 25 649 por salto. El recorrido añadió datos nuevos de simulación, identificados en su recibo.

Para repetir esa demostración con la API iniciada, ejecuta `.venv/bin/python -m scripts.demo_dataset_http`. Crea una publicación, republicación y snapshot nuevos; el histórico permanece inmutable.

BFS se basa en **Unidad 1/Semana 5/Semana5.1-Grafos-Tecnicas de recorrido y busquedas.pdf**, pp. 12–13, inspeccionadas en texto e imagen. [Justificación y costes](../ALGORITMOS.md). Las decisiones de bloques, namespace, cuentas y persistencia son de ingeniería de Outspark.

La importación real realizada en local no despliega ni importa recursos en AWS. Para cloud se conservan por definir IAM, autenticación, volumen de datos que se publicará y mediciones; los archivos/artefactos en S3 continúan siendo una opción del plan. CNM y ranking histórico siguen como trabajo independiente.

Referencias técnicas: [BatchWriteItem: 25 operaciones, reintentos y límites](https://docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_BatchWriteItem.html), [BatchGetItem: lectura por lotes y UnprocessedKeys](https://docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_BatchGetItem.html). Separadas del respaldo académico de BFS.

## Resultados estructurales derivados · 19/10/2026

El comando `scripts.analyze_network` lee el gzip original verificado y escribe ejecuciones derivadas en esta misma tabla propiedad de Network Analysis: `DATASET#id#ANALYSIS#run / LABELS#bucket` y `SUMMARY`. `DATASET#id / ANALYSIS#LATEST` apunta sólo a una ejecución completa; se actualiza en transacción condicionada al manifiesto READY/hash y a la versión del puntero previamente leída. Una ejecución que pierde esa carrera no se publica, aunque sus bloques aislados puedan conservarse sin referencias.

El verificador de inventario original filtra sólo nodos y particiones históricas USER/SOURCE; excluye puntero y resultados derivados. Las pruebas cubren conservación de hashes/inventario y una carrera piloto/completo. La ejecución vigente usa BFS y devuelve 144 componentes conexas. La evaluación de modularidad del 19/10 es antecedente del método retirado. Evidencia actual: `../evidencia/curso-2026-10-21/analisis-bfs-completo.json`.

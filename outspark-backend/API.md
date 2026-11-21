# Documentación Swagger / OpenAPI

Base: `http://127.0.0.1:18080/api`. [Swagger local](http://127.0.0.1:18080/docs) · [OpenAPI](http://127.0.0.1:18080/openapi.json). JSON UTF-8. Excepto `GET /health`, se requiere identidad. En local: `X-Demo-User`; en Lambda: `requestContext.authorizer.jwt.claims.sub`. El cliente no envía `author_id` ni `viewer_id` en el cuerpo.

Swagger documenta **31 operaciones** agrupadas por bounded context, con identificadores estables, parámetros, esquemas y errores. [La copia exportada](docs/openapi.json) permite revisarlas sin levantar la API.

## Probar desde Swagger

1. Inicia **Outspark · API local** en PyCharm o ejecuta `./start.sh`.
2. Abre [Swagger](http://127.0.0.1:18080/docs), pulsa **Authorize**, escribe `ana` y confirma. También puedes usar `bruno`, `carla`, `diego` o `elena`. Son cuentas ficticias. Al recargar se pierde esa autorización.
3. Abre **Profiles → GET /api/me**, pulsa **Try it out** y **Execute**. Debe devolver el perfil de Ana con estado 200.
4. Para publicar abre **Publishing → POST /api/publications**. Usa el cuerpo de ejemplo y una `Idempotency-Key` nueva, por ejemplo `swagger-idea-1`. Copia `publication_id` y el `event_id` completo de la respuesta 201.
5. Cambia la autorización a `bruno` (Logout y Authorize). En **POST /api/reposts**, envía `parent_event_id` igual al `event_id` de Ana, con otra clave. Como `carla`, repite usando el `event_id` recibido de Bruno.
6. Como `diego`, ejecuta **POST /api/feed/snapshots** con `{"strategy":"chronological"}`. Copia `snapshot_id`, identifica la tarjeta del original y consulta **GET /api/feed/{snapshot_id}/cards/{publication_id}/provenance**. La respuesta conserva los motivos de llegada y muestra las rutas Ana → Bruno y Ana → Bruno → Carla.

Los identificadores de ejemplo solo muestran el formato; usa valores de respuestas reales. Si se cambiaron las membresías o contactos de demo, consulta primero sus listas. El recorrido requiere que Ana pertenezca a `diseno`, que Diego mantenga los contactos con Bruno y Carla y que la publicación aparezca entre las tarjetas seleccionadas.

## Simular una publicación propia

`POST /api/publications/{publication_id}/diffusion` devuelve los contactos directos del origen, los dos planes automáticos y, cuando el cuerpo incluye `custom_contacts`, el plan propio. Ejemplo de entrada:

```json
{"origin": 1, "max_hops": 2, "slots": 3, "custom_contacts": [2]}
```

El autor puede elegir de uno a diez contactos iniciales y de uno a tres saltos. Los IDs del plan propio deben venir de la lista de contactos directos de la respuesta. El alcance cuenta perfiles únicos, excluye el origen e incluye el desglose por salto. La operación es de lectura y responde 200.

## Operaciones

| Método | Ruta | Uso / cuerpo |
| --- | --- | --- |
| GET | `/health` | Estado del proceso |
| GET | `/me` | Perfil y preferencias |
| GET | `/me/publications` | Originales propios paginados, independientes del feed |
| PUT | `/me/preferences` | `topic_ids`, `version` actual; actualización optimista |
| GET | `/communities`, `/topics` | Catálogos paginados |
| GET | `/me/communities`, `/me/contacts` | Relaciones paginadas |
| PUT / DELETE | `/me/communities/{id}` | Unirse / salir; espejos atómicos |
| DELETE | `/me/contacts/{id}` | Retirar conexión mutua de demo |
| POST | `/publications` | `community_id`, `body`, `topic_ids` |
| GET / DELETE | `/publications/{id}` | Consultar / retirar; solo autor puede retirar |
| POST | `/reposts` | `parent_event_id`; el servidor deriva el original |
| GET / POST | `/publications/{id}/comments` | Lista paginada / crear con `body` |
| POST | `/feed/snapshots` | Crear snapshot; cuerpo `{"strategy":"chronological"}` o `diverse` |
| POST | `/feed/comparisons` | Dos snapshots con los mismos candidatos, preferencias e instante |
| GET | `/feed/{snapshot_id}` | Leer snapshot propio |
| GET | `/feed/{snapshot_id}/cards/{publication_id}/provenance` | Rutas guardadas y DFS del árbol del original |

Las listas admiten `limit` de 1 a 50 y `cursor` opaco. POST de originales, republicaciones y comentarios requiere `Idempotency-Key` de 1 a 128 caracteres: **201** al crear, **200** y `replayed=true` al repetir la misma operación/payload, **409** al reutilizar la clave con otro payload. El estado retirado oculta contenido y comentarios, incluidos reintentos de comentarios existentes.

Texto: 1–1 000 caracteres. Publicación: 1–3 temas válidos del catálogo y pertenencia activa a la comunidad. Payload HTTP máximo: 16 KiB. Identificadores y fecha los genera/valida el servidor.

## Ejemplo

```bash
curl -s http://127.0.0.1:18080/api/publications   -H 'Content-Type: application/json' -H 'X-Demo-User: ana'   -H 'Idempotency-Key: mi-primera-idea'   -d '{"community_id":"diseno","body":"Una idea conecta comunidades.","topic_ids":["diseno"]}'
```

La respuesta incluye `publication_id` y `event_id`; `event_id` es una referencia opaca al evento padre, no solo un UUID. [El script de recorrido](scripts/demo_http.py) encadena las respuestas reales y consulta el feed de Diego.

Errores: `{"error":{"code":"…","message":"…"}}`; `message` y el encabezado `x-request-id` aparecen cuando están disponibles. Se usan 400 para datos inválidos (incluida validación de FastAPI), 401 sin sesión, 403 sin permiso, 404 inexistente, 409 conflicto, 410 retirado, 413 tamaño y 422 procedencia incompleta o snapshot fuera del límite. 500 indica error interno y 503 fallo de persistencia. Una carrera de escritura puede devolver 409 antes de que el reintento recupere el resultado confirmado. Swagger documenta los códigos aplicables a cada operación.

Un snapshot explica qué fuentes hicieron elegible una tarjeta al generarlo. Las razones no se recalculan al retirar un contacto. La procedencia no acredita lectura, comprensión ni persuasión; Diego se muestra como receptor, no como republicador si no realizó esa acción.

Cada grupo HTTP corresponde a su bounded context: Profiles, Connections, Communities, Publishing o Discovery. Las entradas se validan con recursos Pydantic estrictos y las rutas usan los mismos casos de uso en Uvicorn y Mangum.

## Datos y autenticación por entorno

`Outspark-local-network-analysis` conserva el dataset completo: **63 891 usuarios**, incluidos 160 presentes solo en el muro, **1 545 686 filas originales de amistad**, **817 090 amistades únicas** y **876 993 eventos de muro**. Las cuentas de simulación residen en `Outspark-local-profiles`; las publicaciones nuevas, en `Outspark-local-publishing`. [Modelo, carga e integridad](docs/DATASET.md) y [distribución entre las seis tablas](docs/PERSISTENCIA.md). Network Analysis ofrece nueve operaciones GET bajo `/api/network/datasets/facebook-wosn2009`: manifiesto, nodos, nodo, vecinos, filas de amistad, eventos de muro, alcance BFS, análisis estructural y grupo/conectividad externa de un nodo.

Después de la carga verificada, Authorize admite `fb-<id>`. GET /api/me publica el origen de la cuenta de simulación y GET /api/me/contacts usa las amistades normalizadas del histórico. Las preferencias, pertenencias, publicaciones y republicaciones nuevas siguen sus reglas de dominio. Retirar una amistad histórica devuelve 409, puesto que la fuente permanece inmutable.

Los eventos de muro conservan `source_line`, `wall_owner_id`, `author_id`, `timestamp` y `content_available=false`. No tienen texto ni identificador de contenido compartido. Se consultan con `/nodes/{id}/wall-events?direction=received` o `sent`; no se presentan como republicaciones observadas.

Swagger local ofrece `DemoUser`, que envía `X-Demo-User`. El contrato del adaptador Lambda ofrece `GatewayJWT` (Bearer JWT); la Lambda acepta únicamente el `sub` del autorizador confiable. Cognito y API Gateway aún no están desplegados. La prueba local de ese adaptador usa eventos sintéticos, no tokens reales de AWS.

## Exportar y verificar el contrato

```bash
.venv/bin/python -m scripts.export_openapi
.venv/bin/python -m scripts.export_openapi --mode lambda --output /tmp/outspark-openapi-lambda.json
.venv/bin/python -m unittest tests.test_swagger -v
```

La exportación construye los routers sin iniciar servidores ni acceder a datos. Regenera la copia versionada cuando cambien las rutas o recursos. Las pruebas Swagger validan las 21 operaciones de la app y las pruebas Network Analysis cubren sus nueve operaciones con respuestas HTTP reales en tablas temporales. Incluyen reintentos, retiro de contenido, errores, paginación entre bloques e integridad del histórico. Comprueban las peticiones con el mismo origen que Swagger, el rechazo de orígenes externos y que el modo Lambda no anuncie autenticación de demo.

Referencias técnicas: [metadatos de FastAPI](https://fastapi.tiangolo.com/tutorial/metadata/), [respuestas adicionales](https://fastapi.tiangolo.com/advanced/additional-responses/), [seguridad](https://fastapi.tiangolo.com/reference/security/) y [extensión de OpenAPI](https://fastapi.tiangolo.com/how-to/extending-openapi/).

## Análisis estructural precomputado · 19/10/2026

- `GET /network/datasets/{dataset_id}/analysis`: última ejecución completa con hash de origen, alcance, método BFS, componentes y hasta 20 nodos por grado.
- `GET /network/datasets/{dataset_id}/analysis/nodes/{node_id}`: grupo estructural, tamaño y conexiones externas de un nodo incluido. Un nodo exclusivo del muro queda fuera del grafo de amistades y devuelve 404.

Requieren la misma identidad que el resto de Network Analysis. No recalculan el grafo durante una petición. Sin resultado devuelve 404; un resultado cuyo hash no coincide con el manifiesto vigente devuelve 409. El proceso administrativo local publica sólo resultados completos, comprueba cobertura y actualiza el puntero de forma atómica. Ver [algoritmos](ALGORITMOS.md) y [mediciones](evidencia/mejora/structural-evaluation.json).

## Historial propio y retirada desde Flutter · 19/10/2026

`GET /me/publications?limit=20&cursor=...` consulta el índice existente `ActivityByActor` de Publishing en orden descendente; evalúa 1–50 eventos y conserva sólo raíces. Hidrata los originales desde la tabla base con lectura fuerte para ocultar el texto retirado. No usa Scan, no cambia el esquema y no requiere una migración de publicaciones previas. Una cuenta sólo consulta su propia partición; el cursor valida scope, actor y forma de las claves.

La página puede estar vacía y conservar `next_cursor`, por ejemplo si evaluó republicaciones o si el índice alcanzó exactamente el límite antes de confirmar el final. Continúa hasta null. `unavailable_count` informa referencias a originales ausentes, sin ocultar el problema ni bloquear páginas posteriores; una lectura sin procesar devuelve 503 y el cliente conserva su página/cursor. El índice es eventualmente consistente y la lista no es un snapshot entre páginas: actualizar desde el inicio recupera publicaciones nuevas. Las páginas de Flutter mantienen acotado el número de tarjetas montadas.

`DELETE /publications/{id}` ya existente permite retirar un original propio. Flutter pide confirmación, conserva la estructura de procedencia, actualiza el feed y elimina la tarjeta temporal de publicación reciente para que no reaparezca contenido retirado. El servidor sigue siendo la autoridad para permiso y estado.

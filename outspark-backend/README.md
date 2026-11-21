# Outspark — backend

[Organización](https://github.com/outspark-app) · [Diseño y bounded contexts](https://github.com/outspark-app/outspark-report/blob/main/docs/Dise%C3%B1o%20de%20software%20y%20bounded%20contexts.md) · [API](API.md) · [Algoritmos del curso](ALGORITMOS.md) · [PyCharm](docs/PYCHARM.md).

Backend Python 3.12 con **FastAPI**, organizado como un monolito modular. Publicar, republicar y consultar cómo llegó una tarjeta a una cuenta usan datos persistentes. La API local admite **PostgreSQL** y DynamoDB Local. El adaptador anterior de Lambda usa Mangum y DynamoDB.

## Bounded contexts

| Contexto | Posee | Consumidores |
| --- | --- | --- |
| `profiles` | Perfil y preferencias con versión | Connections, Communities, Publishing, Discovery |
| `connections` | Amistad mutua y sus proyecciones | Discovery |
| `communities` | Comunidades, membresías y catálogo de temas | Profiles, Publishing, Discovery |
| `publishing` | Original, participación única, evento inmutable, comentario e idempotencia | Discovery |
| `discovery` | Candidatos, selección y snapshot con motivos de llegada | API del feed |
| `network_analysis` | Histórico importado, adyacencias, muro, integridad y BFS | Connections y API histórica |

La persistencia usa **seis tablas por entorno**, una por contexto. Dentro de cada tabla se agrupan los ítems consultados juntos; solo Publishing tiene los dos GSI. El prefijo local es `Outspark-local`; Lambda requiere `OUTSPARK_TABLE_PREFIX` y usa el mismo modelo. [Decisión, esquemas y migración](docs/PERSISTENCIA.md).

**Network Analysis** (`network_analysis`) conserva el histórico completo importado en DynamoDB y ofrece nodos, vecinos, filas originales de amistad, eventos de muro y BFS. El [repositorio histórico](https://github.com/outspark-app/outspark-facebook-grafo) conserva los cuadernos y artefactos de análisis. [Importación y uso](docs/DATASET.md). La instalación vigente de Google Cloud usa Firebase Authentication.

Cada contexto tiene `domain`, `application`, `infrastructure` e `interfaces`. Dominio contiene agregados, valores, puertos de repositorio y algoritmos puros. Aplicación separa servicios de comandos y consultas y declara los puertos de otros contextos. Infraestructura implementa persistencia y ACL consumidoras. Interfaces publica routers REST y fachadas con proyecciones y garantías de consistencia.

Los consumidores importan únicamente las fachadas públicas del proveedor desde su ACL. No acceden a repositorios ajenos. `bootstrap.py` construye los proveedores reales e inyecta dependencias; `shared/` contiene herramientas técnicas sin conocer los contextos. Cada adaptador recibe la tabla de su propietario; las transacciones coordinan garantías entre tablas.

Las garantías públicas describen condiciones semánticas, como pertenencia activa. El adaptador del contexto propietario las traduce a condiciones DynamoDB, y la unidad de trabajo las combina con la escritura. Así, salir de una comunidad entre la validación y el commit impide publicar. No se escribe sobre otro contexto.

## Ejecutar

### Cloud Run y Firebase

El `Dockerfile` ejecuta `outspark.cloud_run:application`. El servicio usa
`OUTSPARK_FIREBASE_PROJECT`, `OUTSPARK_POSTGRES_SCHEMA` y
`OUTSPARK_POSTGRES_DSN`. En Cloud Run, el DSN se monta desde Secret Manager
y apunta al socket de Cloud SQL. La identidad del servicio tiene acceso al
conector y a ese secreto.

La API verifica los ID tokens de Firebase y crea un perfil propio al primer
acceso con esa cuenta. El acceso HTTP por cuenta de demo sigue reservado
al servidor local. Firebase Hosting sirve la landing en `/` y Flutter en
`/app/`; el navegador se conecta a Cloud Run por HTTPS.

### PostgreSQL local

Con una base PostgreSQL 17 local vacía, instala las dependencias desde `requirements-dev.txt`.
Configura `OUTSPARK_POSTGRES_DSN` con la conexión de esa base. El esquema se llama
`outspark` por defecto y se puede configurar con `OUTSPARK_POSTGRES_SCHEMA`.

```bash
.venv/bin/python -m scripts.import_dataset --postgres
.venv/bin/python -m scripts.analyze_network --postgres --publish --output .local/postgres/analysis.json
.venv/bin/python -m outspark.local --postgres --prepare
```

El importador usa los dos archivos históricos del repositorio hermano y comprueba el inventario, los recuentos
y los hashes de ambos originales. La API local admite las cuentas de simulación `fb-<id>` y las cinco cuentas de demo.
El adaptador conserva las claves, la paginación y las garantías de escritura. Los recorridos y la selección siguen en Python.

Para copiar una demo existente de DynamoDB Local con sus publicaciones, membresías y preferencias,
detén las escrituras de la aplicación y ejecuta `.venv/bin/python -m scripts.migrate_postgres`
con un esquema PostgreSQL vacío **en lugar de importar y sembrar desde cero**. La copia conserva el origen
y comprueba el inventario por contexto antes de confirmar la transacción. El recibo queda en
`.local/postgres/migration.json`.

Las pruebas del adaptador se ejecutan con `OUTSPARK_POSTGRES_TEST_DSN` apuntando a una base local.
Crean sus propios esquemas de prueba y los eliminan al terminar.

### DynamoDB Local

Con Python 3.12 y Docker disponibles:

```bash
./start.sh
```

API: <http://127.0.0.1:18080/api/health>. Swagger: <http://127.0.0.1:18080/docs>. Esquema: <http://127.0.0.1:18080/openapi.json>.

Swagger documenta las **30 operaciones** con ejemplos, esquemas, parámetros, errores e idempotencia. Pulsa **Authorize**, escribe `ana` y prueba `GET /api/me`. Tras importar el histórico, también puedes usar `fb-1` u otra cuenta `fb-<id>`. El [recorrido completo](API.md#probar-desde-swagger) explica cómo cambiar de cuenta para publicar → republicar → cómo llegó a mí. La [copia OpenAPI](docs/openapi.json) se regenera con `.venv/bin/python -m scripts.export_openapi`.

El script instala el proyecto editable y sus dependencias, inicia DynamoDB Local en 127.0.0.1:18000, conserva el volumen `outspark-backend-local_outspark-data` y prepara cinco cuentas ficticias sin reset. En PyCharm abre esta carpeta y ejecuta **Outspark · API local**. [Configuración del IDE](docs/PYCHARM.md).

Solo en local se admite `X-Demo-User: ana`, `bruno`, `carla`, `diego` o `elena`. Lambda ignora ese encabezado y lee el `sub` del autorizador JWT de API Gateway. No se usan credenciales de ninguna cuenta AWS para DynamoDB Local.

```bash
.venv/bin/python -m scripts.demo_http
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/ruff check outspark tests scripts
.venv/bin/ruff format --check outspark tests scripts
.venv/bin/python dynamodb/validar_dynamodb.py
```

Las pruebas crean tablas desechables únicas y eliminan exclusivamente sus tablas. El validador de `dynamodb/` es una referencia transaccional independiente con 33 comprobaciones; la API usa sus propios adaptadores. No inicies su compose alternativo en el puerto ocupado por la instancia persistente.

## Validación y alcance

La [evidencia](evidencia/validacion_backend.json) registra el resultado de pruebas de dominio, arquitectura, HTTP/SDK/DynamoDB Local y adaptador Lambda. Incluye concurrencia, idempotencia, mirrors, versiones, autorización, retiro de contenido, paginación y comparación sobre los mismos candidatos. El recorrido real se guarda en [demo_http.json](evidencia/demo_http.json).

Las pruebas de Swagger y Network Analysis comprueban las 30 operaciones contra respuestas HTTP reales, la identidad de cada entorno, errores, integridad y paginación del histórico. Las cuentas `fb-<id>` usan sus amistades importadas para el feed de simulaciones; las filas de muro no se transforman en contenidos o republicaciones inventadas.

El feed usa `Query` y `BatchGetItem`, con alcance y presupuesto registrados en el snapshot. La procedencia interactiva admite hasta 1 000 eventos por original y responde 422 cuando no puede recuperar el árbol completo. La DFS pura se prueba también con 1 500 eventos. Selección voraz y DFS están trazadas al material del curso; los pesos del feed son decisiones propias.

Nota histórica. Los pendientes de AWS de ese prototipo corresponden a la arquitectura anterior. La app vigente consume FastAPI y la instalación de Google Cloud usa Firebase y PostgreSQL. `/api/health` acredita el proceso. Las pruebas aisladas verifican los contratos sin depender del estado de la demo.

## Aplicación Flutter y análisis estructural · 19/10/2026

La app hermana `outspark-app` ya consume esta API. Añadir el recorrido ficticio sin reset: `.venv/bin/python -m scripts.prepare_experience`. Conserva publicaciones y preferencias existentes; crea sólo contenido y una conexión entre cuentas ficticias necesaria para republicar desde una fuente visible. No modifica amistades históricas.

```bash
.venv/bin/python -m scripts.analyze_network --help
.venv/bin/python -m scripts.analyze_network --nodes 0 --seconds 120 --publish --output .local/analysis-full.json
```

El comando verifica el SHA-256 del gzip de amistades original en el repositorio hermano. `--nodes 1500` o `5000` evalúa un subgrafo inducido por BFS; no sustituye un resultado completo ya publicado. Las peticiones GET leen resultados almacenados, no ejecutan el cálculo. El método vigente es `outspark-bfs-components/2.0`: componentes conexas por BFS y ranking por grado. La evidencia vigente está en `evidencia/curso-2026-10-21/analisis-bfs-completo.json`; sus 144 componentes no representan comunidades por afinidad. Los resultados de modularidad en `evidencia/mejora/` son antecedentes del método retirado y no validan esta versión.

El perfil Flutter consulta ahora `GET /api/me/publications`: historial paginado por el índice de actividad existente, sin depender de las diez tarjetas del feed. Las pruebas incluyen páginas vacías, identidad, cursores, originales retirados e hidratación incompleta. Desde la conversación, el autor puede retirar un original mediante el endpoint ya existente.

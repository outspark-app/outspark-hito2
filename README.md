# Outspark · base de trabajo del Hito 2

Aplicación universitaria de Complejidad Algorítmica (1ACC0184, UPC, 2026-20). Esta copia reúne el código del simulador y los componentes que necesita Kamil. La versión validada en [Firebase Hosting](https://outspark-universidad.web.app/app/) corresponde a la iteración anterior al rediseño. Las capturas finales se hicieron con el frontend de esta copia en una compilación local conectada a la API publicada. Para repetir el flujo con la misma interfaz, ejecuta este código con PostgreSQL local e importa el dataset completo.

## Componentes

| Carpeta | Qué contiene |
| --- | --- |
| `outspark-app/` | Frontend activo en Flutter. El simulador vive en `lib/features/diffusion_simulator.dart`. `src/` corresponde al prototipo React anterior. |
| `outspark-backend/` | FastAPI y núcleo Python, adaptadores de persistencia, importación, pruebas y Dockerfile de Cloud Run. |
| `outspark-landing/` | Landing web independiente en React/Vite. |
| `outspark-facebook-grafo/` | Notebook de la variante apegada a clase y código de preparación del grafo. |

## Estado técnico

Flutter web en Firebase Hosting, Firebase Authentication, FastAPI en Cloud Run y PostgreSQL en Cloud SQL. El perfil se crea con el primer acceso autenticado. Los perfiles históricos son anónimos, y las nuevas cuentas y publicaciones de Outspark tienen su propio registro. La persistencia DynamoDB Local sirve al entorno histórico de desarrollo. La prioridad para el trabajo actual es PostgreSQL.

El usuario abre **Simular difusión** en una publicación activa propia. Elige perfil histórico, cupo de 1 a 10 contactos directos y de 1 a 3 saltos. **Más conexiones** ordena por grado. **Mayor alcance** usa selección voraz por cobertura marginal. **Mi plan** permite elegir contactos y comparar con la selección anterior. El primer salto parte del origen hacia los contactos elegidos. Estos cuentan como alcanzados y el origen queda excluido. El resultado representa alcance potencial y la simulación queda como vista previa.

La consigna exige que el núcleo sea explicable con los algoritmos de clase. Conserva BFS sobre listas de adyacencia y la selección voraz en Python. Consulta `outspark-backend/ALGORITMOS.md` para los anclajes de clase y las adaptaciones. Las notas antiguas del proyecto sobre AWS, Cognito y la demo describen etapas previas.

## Ejecutar localmente

Requisitos del backend, Python 3.12 y PostgreSQL 17. Para Flutter web, Flutter con Dart compatible con `pubspec.yaml`, Python 3 y Node. Los comandos usan una terminal POSIX.

1. Crea una base local de desarrollo en PostgreSQL 17, por ejemplo con `createdb outspark` usando un rol local con permisos. Desde `outspark-backend/`, crea el entorno de Python y configura el DSN con tu conexión local.

   ```sh
   python3.12 -m venv .venv
   .venv/bin/python -m pip install -r requirements-dev.txt
   export OUTSPARK_POSTGRES_DSN='postgresql://usuario:clave@127.0.0.1:5432/outspark'
   ```

2. Para probar el simulador con el grafo completo, descarga comprimidos **Facebook Links** y **Facebook Wall Posts** desde [MPI-SWS, WOSN 2009](https://socialnetworks.mpi-sws.org/data-wosn2009.html). Guárdalos como `facebook-links.txt.gz` y `facebook-wall.txt.gz` en la carpeta hermana `outspark-facebook-grafo/`. Para archivos ubicados aparte, usa `--links` y `--wall`. El importador valida los hashes de la fuente. La preparación de la demo social funciona también en una base sin el histórico.

   ```sh
   .venv/bin/python -m scripts.import_dataset --postgres
   .venv/bin/python -m outspark.local --postgres --prepare
   ```

   El último comando prepara las cuentas ficticias y deja la API escuchando en `127.0.0.1:18080`. Mantén esa terminal abierta.

3. En otra terminal, desde `outspark-app/`, ejecuta `sh start.sh` y abre [la app local](http://127.0.0.1:5178/app/). El selector de demo permite elegir Ana u otra cuenta ficticia en la API loopback. Abre el historial de una publicación propia activa o crea una desde Inicio. Los enlaces de la landing local funcionan si también se ejecuta la landing desde su carpeta con `npm ci` y `npm run dev`.

## Verificaciones

- Backend desde `outspark-backend/`: inicia DynamoDB Local con `docker compose up -d dynamodb` para las pruebas del adaptador y de compatibilidad. Ejecuta `.venv/bin/python -m unittest discover -s tests -v`. Para incorporar también PostgreSQL, exporta `OUTSPARK_POSTGRES_TEST_DSN` con una base local de pruebas. El conjunto crea y elimina esquemas temporales.
- Frontend desde `outspark-app/`: `python3 scripts/flutter_project.py check`.
- Contrato del simulador: `POST /api/publications/{publication_id}/diffusion`. Ejemplo, `{"origin":1,"slots":3,"max_hops":2,"custom_contacts":[3,4,5]}`. Ejecuta desde una publicación propia. Con los archivos completos, los dos planes automáticos alcanzan 1 261 perfiles en ese escenario y los contactos 3, 4 y 5 alcanzan 71.
- Para ajustar la entrega académica, abre el ZIP de traspaso. Allí están el informe PDF, el texto editable, las figuras y el prompt de trabajo.

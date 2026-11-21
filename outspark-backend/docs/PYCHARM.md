# Trabajar en PyCharm

Abre **la carpeta `outspark-backend`**, que contiene `pyproject.toml`, `outspark/`, `tests/` y `compose.yaml`. Las configuraciones compartidas viven en `.run/`; `.idea/` y `.venv/` son locales y quedan fuera de Git.

## Intérprete y paquetes

En este equipo está registrado **Python 3.12 (outspark-backend)**, con `.venv/bin/python` de esta carpeta. El proyecto está instalado en modo editable, por lo que los imports usan los archivos que estás editando. En otro equipo:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
```

En Settings → Python Interpreter selecciona ese intérprete existente. El directorio de trabajo de todas las configuraciones es `$PROJECT_DIR$` y usan el intérprete del módulo, sin rutas absolutas compartidas. La raíz es fuente de Python, `tests/` es fuente de pruebas y el entorno virtual se excluye del índice.

## Revisar DynamoDB Local

En este equipo está guardada la fuente **Outspark local** en la ventana **Database** de PyCharm. Usa Amazon DynamoDB, host `127.0.0.1`, puerto `18000`, región `us-east-2` y autenticación **No auth**. URL JDBC: `jdbc:dynamodb://127.0.0.1:18000?region=us-east-2`. El controlador se descarga desde el diálogo del IDE; la configuración `.idea/` queda fuera de Git y no usa perfiles AWS.

La API usa seis tablas: **Outspark-local-profiles**, **connections**, **communities**, **publishing**, **discovery** y **network-analysis**, todas con el prefijo `Outspark-local-` y clave `(PK, SK)`. Solo Publishing tiene **ActivityByActor** y **PublicationsByCommunity**. La tabla inicial **Outspark-local** se conserva como recuperación; la API ya no la consulta. [Decisión y migración](PERSISTENCIA.md).

La consola de la conexión contiene [22 consultas de lectura por clave](consultas_dynamodb_local.sql), comentadas y verificadas con datos locales: perfiles, preferencias, contactos, comunidades, publicación/republicación, snapshots y dataset. Selecciona una consulta y pulsa **⌘ Enter**. Abre los valores JSON para inspeccionar mapas y listas. Las consultas 15–20 permiten seguir una publicación real de la demo HTTP tras migrar. Tras cambiar las tablas, pulsa Refresh en la conexión para actualizar el árbol.

**PK** es la clave de partición y agrupa ítems relacionados; **SK** es la clave de ordenación y distingue los ítems dentro de ese grupo. En Profiles, `USER#ana / PROFILE` guarda el perfil y `USER#ana / PREFS` guarda sus preferencias. En Publishing, `POST#<id> / META` guarda el original, `POST#<id> / EVENT#<id>` un evento de publicación o republicación y `POST#<id> / ACTOR#<uid>` la participación de ese usuario. La pareja PK + SK identifica un ítem **dentro de cada tabla**. Los prefijos y valores son convenciones del modelo de Outspark.

Con el dataset completo, la apertura general de la tabla inicial ejecutó `SELECT *` sin filtro y se bloqueó. Para explorarlo, usa las consultas por `PK` y `SK`; los bloques históricos contienen varios registros lógicos por ítem. El servicio local se recuperó conservando el volumen y el manifiesto READY.

Referencia técnica: [conexión DynamoDB desde PyCharm](https://www.jetbrains.com/help/pycharm/dynamodb.html).

## Configuraciones Run/Debug

| Nombre | Ejecución | Uso |
| --- | --- | --- |
| Outspark · API local | `python -m outspark.local --prepare` | Inicia Docker, conserva la semilla y sirve FastAPI en 18080; admite breakpoints |
| Outspark · Preparar datos | `python -m outspark.prepare` | Prepara DynamoDB Local y datos ficticios sin iniciar HTTP |
| Outspark · Pruebas | `python -m unittest discover -s tests -v` | Ejecuta todas las pruebas; prepara Docker antes de lanzarlas |
| Outspark · Demo HTTP | `python -m scripts.demo_http` | Recorre la API ya iniciada y guarda evidencia |
| Outspark · Importar dataset completo | `python -m scripts.import_dataset` | Carga y verifica el histórico completo; repetir conserva los datos y vuelve a comprobarlos |

Para depurar, selecciona **Outspark · API local** y pulsa Debug. La API no usa recarga automática, de modo que los breakpoints pertenecen al mismo proceso. Detén la API antes de ejecutar otra configuración que escuche en 18080. La preparación conserva el volumen; no ejecutes `docker compose down -v` si necesitas los datos.

El contrato se explora en [Swagger](http://127.0.0.1:18080/docs). Pulsa **Authorize** e introduce `ana`, `bruno`, `carla`, `diego` o `elena`; Swagger enviará `X-Demo-User`. Usa **Try it out → Execute** para ejecutar una operación. Las escrituras de publicaciones/reposts/comentarios también requieren `Idempotency-Key`. [Recorrido y ejemplos](../API.md#probar-desde-swagger). No agregues perfiles AWS ni claves reales a las configuraciones locales.

Si editas routers o recursos, detén y vuelve a ejecutar la API, después recarga Swagger. Para actualizar la copia OpenAPI del repositorio, ejecuta `.venv/bin/python -m scripts.export_openapi` desde la terminal del IDE. **Outspark · Pruebas** incluye las comprobaciones de Swagger junto con las de dominio, arquitectura e integración.

La carga completa se ejecuta por separado y no forma parte de cada inicio de API ni de las pruebas. [Modelo, integridad y cuentas fb-&lt;id&gt;](DATASET.md). Los recibos y respaldos locales de datos se guardan en `.local/`, excluido de Git.

Ruff está fijado como dependencia de desarrollo y configurado en `pyproject.toml`. Puede ejecutarse desde la terminal del IDE; no requiere instalar un plugin adicional:

```bash
.venv/bin/ruff check outspark tests scripts
.venv/bin/ruff format outspark tests scripts
```

Referencias: [intérprete existente](https://www.jetbrains.com/help/pycharm/configuring-python-interpreter.html), [configuraciones Python](https://www.jetbrains.com/help/pycharm/run-debug-configuration-python.html).

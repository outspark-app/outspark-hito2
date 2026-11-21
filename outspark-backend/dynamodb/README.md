# Contratos DynamoDB de Outspark

Referencia del modelo v2, no backend HTTP. Se ejecutó contra DynamoDB Local con el SDK real: 33 comprobaciones PASS. No usa mocks ni escribe en una cuenta AWS. [Reporte](validacion_dynamodb.json) y [transacciones ejecutadas](transacciones_ejemplo.json).

## Archivos

- `tabla_dynamodb.json`: tabla on-demand con dos GSI; contrato CreateTable.
- `contratos_dynamodb.py`: publicar, republicar, lectura de procedencia, snapshot cerrado y transacciones condicionadas.
- `validar_dynamodb.py`: crea una tabla temporal única, prepara cuentas ficticias, valida y elimina solo esa tabla en `finally`.
- `compose.yaml`: DynamoDB Local con imagen fijada por digest; memoria desechable y puerto local 18000.
- `requirements.txt`: boto3 fijado; entorno Python 3.12 usado para la validación. Imagen comprobada: DynamoDB Local 3.3.1; versión/digest de referencia incluidos en reporte. Estos campos describen la imagen verificada para esta ejecución, no una detección automática de un endpoint alternativo.

## Reproducir

Desde esta carpeta, con Docker y Python 3.12 disponibles:

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
docker compose up -d
.venv/bin/python validar_dynamodb.py
docker compose down
```

La ejecución acepta únicamente un endpoint HTTP de loopback y suministra credenciales ficticias explícitas. No utiliza el perfil AWS personal. Puede cambiarse el puerto local con `--endpoint http://127.0.0.1:PUERTO` y un mapeo Docker correspondiente. La tabla temporal usa prefijo `Outspark-test-` con UUID. No tocar tablas o contenedores de otros proyectos.

Las transacciones de ejemplo contienen las claves y condiciones efectivamente ejecutadas; IDs aleatorios y nombres de tabla temporal cambian al repetir. No son solicitudes listas para producción: Lambda debe aportar identidad/fecha del servidor y la tabla de entorno.

## Alcance y límites

Se verifican atomicidad, reintentos secuenciales, unicidad de participación, rutas, corrupción detectada, snapshots cerrados, lectura por dueño, retirada de amistad y rollback si una condición cambia antes de confirmar. La tabla Local ejercita GSI, pero no mide el retraso de propagación en AWS.

No incluye handlers Lambda/Cognito/IAM, creación de todos los CRUD, selector voraz completo, frontend integrado o pruebas de carga. El recuperador de idempotencia concurrente está incluido en el contrato, pero no se probó una carrera simultánea entre procesos. El tamaño JSON conservador de transacciones no es un calculador exacto de facturación DynamoDB. Solo se admite `Update` de estado desde funciones autorizadas; administradores pueden escribir fuera del contrato.

No modificar la referencia SQLite ni mezclar sus 30 comprobaciones con las de este modelo. [DynamoDB Local oficial](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/DynamoDBLocal.DownloadingAndRunning.html).


## Modelo vigente por contextos

Los scripts y 33 comprobaciones anteriores conservan la validación del modelo inicial. El backend activo usa [seis contratos CreateTable](tablas_dynamodb.json): [tabla_dynamodb.json](tabla_dynamodb.json) corresponde ahora a Publishing, con dos GSI; [base_table.json](base_table.json) corresponde a los otros cinco contextos, sin GSI. Las copias empaquetadas deben ser idénticas a sus contratos.

Usa `python -m outspark.prepare` para una instalación nueva. Para la tabla inicial existente, detén la API y ejecuta `python -m scripts.migrate_context_tables --source-quiesced`. No vuelvas a importar el dataset para cambiar de tablas. [Decisión y recuperación](../docs/PERSISTENCIA.md).

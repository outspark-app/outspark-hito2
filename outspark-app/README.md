# Outspark — aplicación Flutter

Aplicación final en **Flutter web**, conectada por HTTP a la API Python/FastAPI con PostgreSQL. La dirección «círculos con memoria» conserva la imagen 3 elegida: blanco, tinta y amarillo suave; las conexiones representan procedencia registrada. [Decisiones de producto](PRODUCT.md) · [Sistema visual](DESIGN.md).

## Desarrollo local

Requisitos: Flutter 3.44 / Dart 3.12, Python 3 y Node para el empaquetado existente. Primero inicia la API con PostgreSQL siguiendo el [README del repositorio consolidado](../README.md#ejecutar-localmente). Para añadir el recorrido ficticio persistente sin borrar datos: `.venv/bin/python -m scripts.prepare_experience` desde el backend.

```bash
./start.sh
```

La app queda en <http://127.0.0.1:5178/app/>; la landing independiente, en <http://127.0.0.1:5177/>. `start.sh` compila la demo local, apunta a `http://127.0.0.1:18080/api` y sirve el resultado. El selector Ana/Bruno/Carla/Diego/Elena y `fb-<id>` cambia la identidad ficticia en `X-Demo-User`, permitido únicamente contra loopback.

```bash
python3 scripts/flutter_project.py check
npm run build:demo
npm run test:sites
```

El helper verifica hashes y ejecuta el SDK sobre una copia ASCII cuando la ruta tiene Unicode: evita un fallo del analizador LSP en esta ruta del curso. Las fuentes canónicas siguen en este repositorio. El build genera `dist/client`, `dist/server/index.js` y `dist/.openai/hosting.json`.

## Recorridos conectados

- Publicar con comunidad y 1–3 temas; comentar el original; republicar eligiendo un evento fuente visible. Las claves de idempotencia se conservan al reintentar un mismo envío.
- Inicio, Descubrir y comparación cronológico/diverso sobre el mismo conjunto de candidatos. Métricas y parámetros consultables.
- «Cómo llegó a mí»: origen, eventos reales de republicación y destinatario diferenciados; rutas apiladas en móvil. La llegada no demuestra lectura o influencia.
- Unirse/salir de comunidades, guardar temas con control de versión, consultar conexiones. Perfil consulta el historial propio paginado, independiente del feed. Permite actualizar, avanzar y volver entre páginas. El autor puede retirar un original desde la conversación, con confirmación; el texto y los comentarios dejan de mostrarse en todos sus recorridos.
- Explorar el histórico: manifiesto, vecinos reales, eventos de muro sin contenido, alcance BFS y resultados precalculados de componentes conexas y grados. Las 63 891 cuentas históricas son simulaciones, no usuarios activos.

Los cambios confirmados se guardan en la base y sobreviven a recargar. El borrador se conserva por cuenta mientras la pestaña siga abierta y se pierde al recargar. No hay botón para borrar la base ni reiniciar datos del usuario.

## Organización

`lib/domain` contiene DTO inmutables; `lib/data` contiene el cliente HTTP y repositorio; `lib/application` controla sesiones y estados; `lib/features` contiene las vistas; `lib/ui` comparte tokens y componentes. Las reglas y algoritmos del producto siguen en Python. `test/api_client_test.dart` comprueba contrato, identidad, errores y reintentos sin duplicación.

`src/` conserva el boceto React anterior como referencia; no es la aplicación activa. `npm run dev:prototype` lo abre en 5190; `npm run build:prototype` escribe sólo en `.local/react-prototype`. No mezclar el estado en memoria de ese boceto con el Flutter conectado.

## Destino de producción

Firebase Hosting sirve Flutter en `/app/`. Firebase Authentication gestiona el acceso y la API de Cloud Run valida sus tokens. Para compilar otra instalación, configura las variables `API_BASE_URL`, `LANDING_URL` y `FIREBASE_*` mediante los argumentos de compilación que lee `lib/main.dart`. Usa la configuración de esa instalación. La demo usa el servidor local.

La configuración `.openai/hosting.json`, `worker/`, `scripts/prepare-sites-build.mjs` y `tests/sites-worker.test.mjs` se conserva. Este trabajo no reemplaza el sitio experimental publicado anteriormente.

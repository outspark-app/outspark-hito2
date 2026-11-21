# Outspark — landing

[Organización](https://github.com/outspark-app) · [Aplicativo](https://github.com/outspark-app/outspark-app) · [Diseño e informe](https://github.com/outspark-app/outspark-report).

Página de presentación React/Vite independiente, con la composición espacial imagen 3 elegida para Outspark. Explica publicar, republicar y consultar el recorrido de una idea; sus botones conducen al aplicativo.

```bash
npm ci --no-audit --no-fund
npm run dev
```

Landing: <http://127.0.0.1:5177/>. Los botones «Entrar» abren <http://127.0.0.1:5178/app/>. El destino es configurable con `VITE_APP_URL`; ver `.env.example`. En build estático el destino por defecto es `/app/` para servir landing y app bajo el mismo dominio.

```bash
npm run build
npm run test:sites
```

`src/` contiene la landing y sus estilos, `public/assets/` la marca. Los nodos Ana, Bruno, Carla y Diego son un ejemplo ficticio. No hay autenticación ni llamadas al backend. El build emite `dist/client`, `dist/server` y metadatos de Sites; AWS S3/CloudFront está pendiente de desplegar.

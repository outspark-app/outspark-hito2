import { useLayoutEffect, useRef, useState } from "react";
import { ArrowRight, ArrowUpRight, Path, Repeat } from "@phosphor-icons/react";

function Avatar({ name }) {
  return (
    <span className={"avatar " + name.toLowerCase()} aria-hidden="true">
      {name.slice(0, 2).toUpperCase()}
    </span>
  );
}
function Brand() {
  return (
    <a className="brand" href="#inicio" aria-label="Outspark, inicio">
      <img src="/assets/outspark.svg" alt="" width="34" height="34" />
      <span translate="no">Outspark</span>
    </a>
  );
}
function Constellation() {
  const container = useRef(null);
  const [route, setRoute] = useState("carla");
  const [lines, setLines] = useState(null);
  useLayoutEffect(() => {
    const root = container.current;
    const measure = () => {
      const r = root.getBoundingClientRect();
      const box = (selector) => {
        const b = root.querySelector(selector).getBoundingClientRect();
        return {
          x: b.left - r.left,
          y: b.top - r.top,
          w: b.width,
          h: b.height,
        };
      };
      const a = box(".origin"),
        b = box(".bruno-node"),
        c = box(".carla-node"),
        d = box(".recipient");
      const endX = d.x + d.w * 0.5,
        endY = d.y;
      const curve = (x, y, xx, yy) =>
        "M" +
        x +
        " " +
        y +
        " C" +
        (x + 35) +
        " " +
        y +
        " " +
        (xx - 35) +
        " " +
        yy +
        " " +
        xx +
        " " +
        yy;
      setLines({
        w: r.width,
        h: r.height,
        ab: curve(a.x + a.w, a.y + a.h * 0.35, b.x, b.y + b.h / 2),
        bc:
          "M" +
          (b.x + b.w / 2) +
          " " +
          (b.y + b.h) +
          " L" +
          (c.x + c.w / 2) +
          " " +
          c.y,
        bd: curve(b.x + b.w, b.y + b.h / 2, endX, endY),
        cd: curve(c.x + c.w / 2, c.y + c.h, endX, endY),
      });
    };
    const observer = new ResizeObserver(measure);
    observer.observe(root);
    root
      .querySelectorAll("article,button,.recipient")
      .forEach((el) => observer.observe(el));
    measure();
    return () => observer.disconnect();
  }, []);
  return (
    <div className="constellation-wrap">
      <div className="constellation" ref={container}>
        <div className="circle-ground" aria-hidden="true" />
        {lines && (
          <svg
            className="connections"
            viewBox={"0 0 " + lines.w + " " + lines.h}
            preserveAspectRatio="none"
            aria-hidden="true"
          >
            <path d={lines.ab} />
            <path
              d={lines.bc}
              className={route === "carla" ? "" : "inactive"}
            />
            <path
              d={lines.bd}
              className={"arrival " + (route === "bruno" ? "" : "inactive")}
            />
            <path
              d={lines.cd}
              className={"arrival " + (route === "carla" ? "" : "inactive")}
            />
          </svg>
        )}
        <article className="origin">
          <div className="author">
            <Avatar name="Ana" />
            <div>
              <strong>Ana</strong>
              <span>en Diseño</span>
            </div>
          </div>
          <p>¿Y si diseñamos una ciudad donde dé gusto encontrarnos?</p>
          <span className="origin-label">Aquí comienza la idea</span>
        </article>
        <button
          className={
            "person bruno-node " + (route === "bruno" ? "selected" : "")
          }
          onClick={() => setRoute("bruno")}
          aria-pressed={route === "bruno"}
        >
          <Avatar name="Bruno" />
          <strong>Bruno</strong>
          <span>Comparte desde Ana</span>
        </button>
        <button
          className={
            "person carla-node " + (route === "carla" ? "selected" : "")
          }
          onClick={() => setRoute("carla")}
          aria-pressed={route === "carla"}
        >
          <Avatar name="Carla" />
          <strong>Carla</strong>
          <span>Comparte desde Bruno</span>
        </button>
        <div className="recipient">
          <Avatar name="Diego" />
          <div>
            <strong>Diego</strong>
            <span>Una idea, dos caminos</span>
          </div>
        </div>
      </div>
      <p className="route-reading" aria-live="polite">
        {route === "carla"
          ? "Ana publica. Bruno comparte. Carla continúa el recorrido."
          : "Ana publica. Bruno acerca la idea a Diego."}
      </p>
      <p className="example-note">
        Ejemplo con cuentas ficticias. Diego recibe; no se cuenta como
        republicador.
      </p>
    </div>
  );
}
export function App() {
  const appUrl =
    import.meta.env.VITE_APP_URL ||
    (import.meta.env.DEV ? "http://127.0.0.1:5178/app/" : "/app/");
  const networkUrl = new URL(appUrl, window.location.href);
  networkUrl.searchParams.set("view", "red");
  return (
    <div id="inicio">
      <a className="skip" href="#contenido">
        Ir al contenido
      </a>
      <header className="header">
        <Brand />
        <nav aria-label="Navegación principal">
          <a href="#como-funciona">La idea</a>
          <a href="#circulos">Los círculos</a>
        </nav>
        <a className="button quiet" href={appUrl}>
          Entrar <ArrowUpRight aria-hidden="true" size={18} />
        </a>
      </header>
      <main id="contenido">
        <section className="hero">
          <div className="hero-copy">
            <h1>
              Una idea.
              <br />
              Más de
              <br />
              un círculo.
            </h1>
            <p>
              Las conversaciones se mueven. En Outspark, su origen y los caminos
              que recorren van con ellas.
            </p>
            <div className="hero-actions">
              <a className="button yellow" href={appUrl}>
                Entrar a Outspark <ArrowRight aria-hidden="true" size={20} />
              </a>
              <a className="underlined" href="#como-funciona">
                Sigue una idea
              </a>
            </div>
          </div>
          <Constellation />
        </section>
        <section className="manifesto" id="como-funciona">
          <div>
            <Path aria-hidden="true" size={36} weight="light" />
            <h2>
              Que viaje la idea.
              <br />
              Que se conserve
              <br />
              su historia.
            </h2>
          </div>
          <div className="manifesto-copy">
            <p>
              Una publicación puede llegar por varias personas. La ves una sola
              vez, con sus rutas disponibles.
            </p>
            <p>
              Abre «Cómo llegó a mí» para recorrerlas. La autoría y la
              conversación permanecen en el original.
            </p>
            <a href={appUrl}>
              Explorar una conversación{" "}
              <ArrowUpRight aria-hidden="true" size={20} />
            </a>
          </div>
        </section>
        <section className="how" id="circulos">
          <div className="section-heading">
            <h2>
              Un comienzo propio.
              <br />
              Una conversación común.
            </h2>
            <p>
              Elige tus comunidades y temas. Comparte desde una persona
              concreta. Abre espacio a otras perspectivas.
            </p>
          </div>
          <ol className="steps">
            <li>
              <span>1</span>
              <h3>Encuentra tu círculo</h3>
              <p>
                Diseño, tecnología o sostenibilidad. Tú eliges dónde participar
                y qué temas te interesan.
              </p>
            </li>
            <li>
              <span>2</span>
              <h3>Haz que una idea siga</h3>
              <p>
                Publica o republica desde quien te la compartió. El contenido
                conserva su origen y sus comentarios.
              </p>
            </li>
            <li>
              <span>3</span>
              <h3>Mira más allá</h3>
              <p>
                Alterna entre un feed reciente y uno diverso. Consulta por qué
                apareció una conversación y qué camino siguió.
              </p>
            </li>
          </ol>
        </section>
        <section className="network-note">
          <Repeat aria-hidden="true" size={30} weight="light" />
          <div>
            <h2>
              Personas conectadas.
              <br />
              Datos con contexto.
            </h2>
            <p>
              El proyecto también permite explorar una red histórica de Facebook
              y calcular su alcance. Amistades históricas y acciones nuevas de
              Outspark se muestran por separado.
            </p>
            <p className="small">
              La procedencia registra un recorrido; no verifica la verdad del
              contenido ni demuestra que alguien lo leyó.
            </p>
          </div>
          <a className="button quiet" href={networkUrl.toString()}>
            Conocer la red <ArrowUpRight aria-hidden="true" size={18} />
          </a>
        </section>
        <section className="close">
          <h2>
            La próxima idea
            <br />
            puede empezar contigo.
          </h2>
          <a className="button yellow" href={appUrl}>
            Entrar a Outspark <ArrowRight aria-hidden="true" size={20} />
          </a>
        </section>
        <section className="questions" aria-label="Sobre el proyecto">
          <details>
            <summary>¿Qué puedo probar?</summary>
            <p>
              Publicar, comentar, republicar y consultar recorridos con cuentas
              ficticias, además de comunidades, preferencias y exploración del
              dataset. Las acciones se guardan en la API de la demostración
              local.
            </p>
          </details>
          <details>
            <summary>¿Es una red social abierta al público?</summary>
            <p>
              Es un proyecto universitario de Complejidad Algorítmica de la UPC.
              El acceso actual usa cuentas de demostración locales; la
              autenticación y el despliegue público todavía están pendientes.
            </p>
          </details>
        </section>
      </main>
      <footer>
        <Brand />
        <p>Proyecto UPC · Complejidad Algorítmica 2026-20</p>
        <a href={appUrl}>
          Abrir la aplicación <ArrowUpRight aria-hidden="true" size={16} />
        </a>
      </footer>
    </div>
  );
}

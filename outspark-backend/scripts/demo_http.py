"""Publicar → republicar → cómo llegó a mí mediante respuestas HTTP reales."""

import argparse
import json
from pathlib import Path
from urllib.request import Request, urlopen
from uuid import uuid4


def run(base="http://127.0.0.1:18080"):
    token = "http-demo-" + uuid4().hex

    def call(method, path, actor, data=None, suffix=None):
        headers = {"Content-Type": "application/json", "X-Demo-User": actor}
        if suffix:
            headers["Idempotency-Key"] = token + suffix
        request = Request(
            base + "/api" + path,
            method=method,
            headers=headers,
            data=json.dumps(data).encode() if data is not None else None,
        )
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read())

    call("PUT", "/me/communities/diseno", "ana")
    publication = call(
        "POST",
        "/publications",
        "ana",
        {
            "community_id": "diseno",
            "body": "Una idea conecta comunidades.",
            "topic_ids": ["diseno"],
        },
        "-publish",
    )
    bruno = call(
        "POST", "/reposts", "bruno", {"parent_event_id": publication["event_id"]}, "-bruno"
    )
    call("POST", "/reposts", "carla", {"parent_event_id": bruno["event_id"]}, "-carla")
    feed = call("POST", "/feed/snapshots", "diego", {"strategy": "chronological"})
    pid = publication["publication_id"]
    if not any(c["publication_id"] == pid for c in feed["cards"]):
        raise RuntimeError(
            "La demo requiere los contactos ficticios de Diego y el original entre las diez tarjetas seleccionadas."
        )
    provenance = call("GET", f"/feed/{feed['snapshot_id']}/cards/{pid}/provenance", "diego")
    routes = [[e["actor_id"] for e in route["events"]] for route in provenance["routes"]]
    assert ["ana", "bruno"] in routes and ["ana", "bruno", "carla"] in routes, routes
    assert provenance["tree"]["event_count"] == 3
    return {
        "status": "PASS",
        "publication_id": pid,
        "snapshot_id": feed["snapshot_id"],
        "routes": routes,
        "event_count": provenance["tree"]["event_count"],
        "query_pages": feed["selection"]["retrieval"]["query_pages"],
        "source": "HTTP + FastAPI/Uvicorn + DynamoDB Local",
        "base_url": base,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:18080")
    parser.add_argument("--output", default="evidencia/demo_http.json")
    args = parser.parse_args()
    from urllib.parse import urlparse

    url = urlparse(args.base)
    if url.scheme != "http" or url.hostname not in ("127.0.0.1", "localhost"):
        parser.error("La demo solo admite una API HTTP local")
    result = run(args.base)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

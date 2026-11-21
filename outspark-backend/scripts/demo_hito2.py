"""Verificar el Hito 2 por HTTP local sin borrar ni reemplazar contenido existente."""

import argparse
import json
import re
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


def check(condition, message):
    if not condition:
        raise RuntimeError(message)


def run(base, scenario):
    def call(method, path, actor="diego", body=None, key=None):
        headers = {"Content-Type": "application/json", "X-Demo-User": actor}
        if key:
            headers["Idempotency-Key"] = f"{scenario}-{key}"
        request = Request(
            base + "/api" + path,
            method=method,
            headers=headers,
            data=json.dumps(body).encode() if body is not None else None,
        )
        with urlopen(request, timeout=90) as response:
            return json.load(response) if response.status != 204 else None

    viewer = call("GET", "/me")
    contacts = call("GET", "/me/contacts")
    check(
        {"bruno", "carla"} <= {item["contact_id"] for item in contacts["items"]},
        "Faltan contactos Diego–Bruno/Carla. No se restablecen relaciones retiradas.",
    )
    dataset_path = "/network/datasets/facebook-wosn2009"
    manifest = call("GET", dataset_path)
    analysis = call("GET", dataset_path + "/analysis")
    check(
        manifest["status"] == "READY" and manifest["full_dataset"],
        "Falló la comprobación: manifest['status'] == 'READY' and manifest['full_dataset']",
    )
    counts = manifest["counts"]
    check(counts["friendship_rows"] == 1545686, "Filas originales de amistades distintas")
    check(counts["nodes"] == 63891, "Unión de identificadores distinta")
    check(counts["wall_only_nodes"] == 160, "IDs exclusivos del muro distintos")
    membership = call("GET", dataset_path + "/analysis/nodes/1")
    check(membership["group_size"] == 63392, "Tamaño de la mayor componente distinto")
    check(
        counts["friendship_nodes"] == 63731,
        "Falló la comprobación: counts['friendship_nodes'] == 63731",
    )
    check(
        counts["unique_friendships"] == 817090,
        "Falló la comprobación: counts['unique_friendships'] == 817090",
    )
    check(counts["wall_events"] == 876993, "Falló la comprobación: counts['wall_events'] == 876993")
    check(
        analysis["nodes"] == 63731 and analysis["edges"] == 817090,
        "Falló la comprobación: analysis['nodes'] == 63731 and analysis['edges'] == 817090",
    )
    check(
        analysis["groups"] == 144 and analysis["full_graph"] and analysis["complete"],
        "Falló la comprobación: analysis['groups'] == 144 and analysis['full_graph'] and analysis['complete']",
    )
    check(
        analysis["method"] == "outspark-bfs-components/2.0",
        "Falló la comprobación: analysis['method'] == 'outspark-bfs-components/2.0'",
    )
    check(
        analysis["source_sha256"] == manifest["files"]["links"]["sha256"],
        "Falló la comprobación: analysis['source_sha256'] == manifest['files']['links']['sha256']",
    )
    reach = call("GET", dataset_path + "/nodes/1/reach?max_hops=3")
    check(
        [row["new_nodes"] for row in reach["rounds"]] == [26, 1694, 25649],
        "Falló la comprobación: [row['new_nodes'] for row in reach['rounds']] == [26, 1694, 25649]",
    )

    # Las cuentas son ficticias. Las membresías existentes permanecen intactas.
    examples = []
    communities = ("diseno", "tecnologia", "sostenibilidad")
    for actor in ("bruno", "carla", "elena"):
        for community in communities:
            call("PUT", "/me/communities/" + community, actor)
            examples.append(
                call(
                    "POST",
                    "/publications",
                    actor,
                    {
                        "community_id": community,
                        "topic_ids": [community],
                        "body": f"Hito 2 · {scenario} · Idea de {actor} sobre {community}. "
                        "Contenido ficticio para comparar las dos estrategias de feed.",
                    },
                    f"example-{actor}-{community}",
                )
            )
    call("PUT", "/me/communities/diseno", "ana")
    payload = {
        "community_id": "diseno",
        "topic_ids": ["diseno"],
        "body": f"Hito 2 · {scenario} · Una idea conserva su origen. "
        "¿Cómo llegó esta conversación hasta tu feed? Demostración ficticia de Outspark.",
    }
    original = call("POST", "/publications", "ana", payload, "original")
    replay = call("POST", "/publications", "ana", payload, "original")
    check(
        replay["publication_id"] == original["publication_id"] and replay["replayed"],
        "Falló la comprobación: replay['publication_id'] == original['publication_id'] and replay['replayed']",
    )
    bruno = call("POST", "/reposts", "bruno", {"parent_event_id": original["event_id"]}, "bruno")
    carla = call("POST", "/reposts", "carla", {"parent_event_id": bruno["event_id"]}, "carla")
    pid = original["publication_id"]
    expected_routes = {("ana", "bruno"), ("ana", "bruno", "carla")}
    # Los GSI son eventualmente consistentes: no se alteran fechas para acelerarlos.
    for attempt in range(20):
        feed = call("POST", "/feed/snapshots", body={"strategy": "chronological"})
        matches = [card for card in feed["cards"] if card["publication_id"] == pid]
        if matches:
            provenance = call("GET", f"/feed/{feed['snapshot_id']}/cards/{pid}/provenance")
            paths = {
                tuple(event["actor_id"] for event in r["events"]) for r in provenance["routes"]
            }
            if expected_routes <= paths:
                break
        if attempt == 19:
            raise AssertionError("El feed no recuperó ambas rutas; revisa conexiones o ventanas.")
        time.sleep(0.25)
    check(len(matches) == 1, "Falló la comprobación: len(matches) == 1")
    check(
        provenance["tree"]["event_count"] == 3,
        "Falló la comprobación: provenance['tree']['event_count'] == 3",
    )
    check(
        all(("diego" not in route for route in paths)),
        "Falló la comprobación: all(('diego' not in route for route in paths))",
    )
    root_sources = [r for r in provenance["routes"] if len(r["events"]) == 1]
    check(
        any(
            reason["type"] in ("discovery", "community")
            for route in root_sources
            for reason in route["source"]["reasons"]
        ),
        "No se recuperó la fuente del original por catálogo o comunidad.",
    )
    saved = call("GET", f"/feed/{feed['snapshot_id']}")
    check(
        saved["selection"] == feed["selection"],
        "Falló la comprobación: saved['selection'] == feed['selection']",
    )
    check(
        [c["publication_id"] for c in saved["cards"]]
        == [c["publication_id"] for c in feed["cards"]],
        "Falló la comprobación: [c['publication_id'] for c in saved['cards']] == [c['publication_id'] for c in feed['cards']]",
    )
    try:
        call("GET", f"/feed/{feed['snapshot_id']}", "ana")
    except HTTPError as error:
        check(error.code == 403, "Falló la comprobación: error.code == 403")
    else:
        raise AssertionError("Otra cuenta pudo consultar el snapshot privado.")
    comparison = call("POST", "/feed/comparisons")
    selected = comparison["feeds"]
    left, right = selected["chronological"], selected["diverse"]
    check(
        left["selection"]["candidate_originals"] == right["selection"]["candidate_originals"],
        "Las cantidades de candidatos difieren entre estrategias",
    )
    check(not left["selection"]["retrieval"]["truncated"], "Recuperación de candidatos truncada")
    check(not right["selection"]["retrieval"]["truncated"], "Recuperación de candidatos truncada")
    for field in ("candidate_hash", "reference_at", "preferences", "parameters"):
        check(
            left["selection"][field] == right["selection"][field],
            "Falló la comprobación: left['selection'][field] == right['selection'][field]",
        )
    check(
        comparison["candidate_hash"] == left["selection"]["candidate_hash"],
        "Falló la comprobación: comparison['candidate_hash'] == left['selection']['candidate_hash']",
    )
    for result in selected.values():
        ids = [card["publication_id"] for card in result["cards"]]
        check(
            len(ids) == len(set(ids)) <= 10,
            "Falló la comprobación: len(ids) == len(set(ids)) <= 10",
        )
        authors = Counter(card["publication"]["author_id"] for card in result["cards"])
        check(
            max(authors.values(), default=0) <= 2,
            "Falló la comprobación: max(authors.values(), default=0) <= 2",
        )
    return {
        "status": "PASS",
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "scenario": scenario,
        "preconditions": {"viewer": viewer, "contacts": contacts},
        "environment": "HTTP local + FastAPI + DynamoDB Local; cuentas y contenido ficticios",
        "historical": {"manifest": manifest, "analysis": analysis, "reach_seed_1": reach},
        "journey": {
            "publication_id": pid,
            "snapshot_id": feed["snapshot_id"],
            "bruno_event_id": bruno["event_id"],
            "carla_event_id": carla["event_id"],
            "routes": [list(route) for route in sorted(paths)],
            "provenance": provenance,
            "one_card_per_original": True,
            "replay_same_original": True,
            "snapshot_readback": True,
            "other_viewer_rejected": True,
        },
        "comparison": comparison,
        "example_ids": [p["publication_id"] for p in examples],
        "limits": [
            "La comparación usa los candidatos disponibles; no demuestra optimalidad ni satisfacción.",
            "Los snapshots nuevos se crean en cada ejecución; publicaciones y republicaciones son idempotentes.",
            "Las cifras BFS son alcance potencial; los eventos del muro no identifican republicaciones.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:18080")
    parser.add_argument("--scenario", default="hito2-20261108")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    endpoint = urlparse(args.base)
    if endpoint.scheme != "http" or endpoint.hostname not in ("localhost", "127.0.0.1"):
        parser.error("La demostración solo admite HTTP en loopback.")
    if not re.fullmatch(r"[a-z0-9-]{1,50}", args.scenario):
        parser.error("El escenario debe tener 1–50 letras minúsculas, dígitos o guiones.")
    if args.output is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        args.output = Path("evidencia/hito2") / f"demo-http-{stamp}.json"
    if args.output.exists():
        parser.error("La evidencia ya existe. Elige otro --output; no se sobrescribe.")
    result = run(args.base.rstrip("/"), args.scenario)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as output:
        output.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()

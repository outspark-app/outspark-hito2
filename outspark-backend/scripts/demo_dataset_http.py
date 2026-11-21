"""Demostración HTTP con cuentas de simulación elegidas de la topología real importada."""

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from uuid import uuid4


def run(base):
    dataset = "facebook-wosn2009"
    path = "/network/datasets/" + dataset
    key = "dataset-demo-" + uuid4().hex

    def call(method, route, actor="ana", body=None, operation=None):
        headers = {"Content-Type": "application/json", "X-Demo-User": actor}
        if operation:
            headers["Idempotency-Key"] = key + "-" + operation
        request = Request(
            base + "/api" + route,
            method=method,
            headers=headers,
            data=json.dumps(body).encode() if body is not None else None,
        )
        with urlopen(request, timeout=60) as response:
            return json.load(response)

    manifest = call("GET", path)
    assert manifest["status"] == "READY" and manifest["full_dataset"]
    first = 1
    neighbors = call("GET", path + "/nodes/1/neighbors?limit=50")["items"]
    second = neighbors[0]["node_id"]
    third = next(
        row["node_id"]
        for row in call("GET", f"{path}/nodes/{second}/neighbors?limit=50")["items"]
        if row["node_id"] not in (first, second)
    )
    publisher, republisher, viewer = [f"fb-{uid}" for uid in (first, second, third)]
    call("PUT", "/me/communities/diseno", publisher)
    original = call(
        "POST",
        "/publications",
        publisher,
        {
            "community_id": "diseno",
            "body": "Simulación nueva sobre las amistades del dataset importado.",
            "topic_ids": ["diseno"],
        },
        "publish",
    )
    call("POST", "/reposts", republisher, {"parent_event_id": original["event_id"]}, "repost")
    feed = call("POST", "/feed/snapshots", viewer, {"strategy": "chronological"})
    pid, sid = original["publication_id"], feed["snapshot_id"]
    assert any(card["publication_id"] == pid for card in feed["cards"])
    provenance = call("GET", f"/feed/{sid}/cards/{pid}/provenance", viewer)
    routes = [[event["actor_id"] for event in route["events"]] for route in provenance["routes"]]
    assert [publisher, republisher] in routes
    reach = call("GET", path + "/nodes/1/reach?max_hops=3")
    assert [round_["new_nodes"] for round_ in reach["rounds"]] == [26, 1694, 25649]
    return {
        "status": "PASS",
        "source": "HTTP + FastAPI/Uvicorn + complete imported dataset",
        "dataset_id": dataset,
        "actors": {"publisher": publisher, "republisher": republisher, "viewer": viewer},
        "publication_id": pid,
        "snapshot_id": sid,
        "routes": routes,
        "bfs_seed_1": reach,
        "historical_wall_content_invented": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:18080")
    parser.add_argument("--output", type=Path, default=Path("evidencia/demo_dataset_http.json"))
    args = parser.parse_args()
    endpoint = urlparse(args.base)
    if endpoint.scheme != "http" or endpoint.hostname not in ("127.0.0.1", "localhost"):
        parser.error("La demostración solo admite la API HTTP local.")
    result = run(args.base)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

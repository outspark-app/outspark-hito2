"""Add a reproducible fictional journey; never reset existing profiles or content."""

import json
from urllib.request import Request, urlopen

from outspark.persistence import local_storage
from outspark.shared.infrastructure.dynamodb import operations as db


def main():
    storage = local_storage()["connections"]
    lo, hi = "bruno", "carla"
    canonical = storage.get(f"FRIEND#{lo}#{hi}", "META")
    if canonical and canonical["status"] != "ACTIVE":
        raise RuntimeError(
            "La conexión Bruno–Carla fue retirada. No se restablece automáticamente."
        )
    if not canonical:
        db.commit(
            storage.client,
            [
                db.put(storage.table, dict(PK=pk, SK=sk, entity_type="FRIENDSHIP", status="ACTIVE"))
                for pk, sk in [
                    (f"FRIEND#{lo}#{hi}", "META"),
                    (f"USER#{lo}", f"CONTACT#{hi}"),
                    (f"USER#{hi}", f"CONTACT#{lo}"),
                ]
            ],
        )

    def call(method, path, actor, body=None, key=None):
        headers = {"Content-Type": "application/json", "X-Demo-User": actor}
        if key:
            headers["Idempotency-Key"] = "outspark-experience-v1-" + key
        request = Request(
            "http://127.0.0.1:18080/api" + path,
            method=method,
            headers=headers,
            data=json.dumps(body).encode() if body is not None else None,
        )
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read()) if response.status != 204 else None

    examples = [
        (
            "ana",
            "diseno",
            "¿Y si diseñamos una ciudad donde dé gusto encontrarnos? Una banca con sombra también puede abrir una conversación.",
        ),
        (
            "bruno",
            "tecnologia",
            "¿Qué herramienta sencilla te habría gustado tener cuando empezaste a crear? A veces una buena pregunta es el mejor punto de partida.",
        ),
        (
            "elena",
            "sostenibilidad",
            "Compartir el barrio también es cuidarlo. ¿Qué pequeño cambio haría más amable el lugar donde vives?",
        ),
    ]
    outputs = []
    for actor, community, text in examples:
        call("PUT", "/me/communities/" + community, actor)
        outputs.append(
            call(
                "POST",
                "/publications",
                actor,
                {"community_id": community, "body": text, "topic_ids": [community]},
                actor + "-publish",
            )
        )
    root = outputs[0]
    bruno = call("POST", "/reposts", "bruno", {"parent_event_id": root["event_id"]}, "bruno-repost")
    carla = call(
        "POST", "/reposts", "carla", {"parent_event_id": bruno["event_id"]}, "carla-repost"
    )
    call(
        "POST",
        "/publications/" + root["publication_id"] + "/comments",
        "carla",
        {"body": "Me gusta pensar la ciudad como un lugar para compartir, además de transitar."},
        "carla-comment",
    )
    print(
        json.dumps(
            {
                "status": "PASS",
                "fictional": True,
                "publication_id": root["publication_id"],
                "bruno_event": bruno["event_id"],
                "carla_event": carla["event_id"],
                "replayed": root["replayed"],
                "changed": "Only fictional connection/content; existing data preserved.",
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()

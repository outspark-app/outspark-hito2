"""Semilla ficticia y no destructiva para la demo local."""

import argparse

from .persistence import local_storage
from .shared.application.models import now
from .shared.infrastructure.dynamodb import operations as db


def seed(repo):
    repo.ensure_tables()
    if repo["profiles"].get("DEMO#v1", "META"):
        return
    instant, items = now(), []
    writes = []
    for uid, name, topic in [
        ("ana", "Ana", "diseno"),
        ("bruno", "Bruno", "tecnologia"),
        ("carla", "Carla", "diseno"),
        ("diego", "Diego", "diseno"),
        ("elena", "Elena", "sostenibilidad"),
    ]:
        items.extend(
            [
                dict(
                    PK=f"USER#{uid}",
                    SK="PROFILE",
                    entity_type="USER",
                    uid=uid,
                    name=name,
                    status="ACTIVE",
                    is_demo=True,
                    created_at=instant,
                ),
                dict(
                    PK=f"USER#{uid}",
                    SK="PREFS",
                    entity_type="PREFERENCES",
                    topic_ids=[topic],
                    version=1,
                ),
            ]
        )
    writes.extend(db.put(repo["profiles"].table, item) for item in items)
    items = []
    for cid, name in [
        ("diseno", "Diseño"),
        ("tecnologia", "Tecnología"),
        ("sostenibilidad", "Sostenibilidad"),
    ]:
        items.extend(
            [
                dict(
                    PK=f"COMM#{cid}",
                    SK="META",
                    entity_type="COMMUNITY",
                    community_id=cid,
                    name=name,
                    description="Comunidad ficticia de demostración.",
                    status="ACTIVE",
                    creator_id="ana",
                ),
                dict(
                    PK="CATALOG#COMM",
                    SK=f"COMM#{cid}",
                    entity_type="COMMUNITY_CATALOG",
                    community_id=cid,
                    name=name,
                    status="ACTIVE",
                ),
                dict(
                    PK="UNIQUE#COMM_NAME#" + db.digest(name.casefold()),
                    SK="META",
                    normalized_name=name.casefold(),
                ),
                dict(
                    PK="CATALOG#TOPIC",
                    SK=f"TOPIC#{cid}",
                    entity_type="TOPIC",
                    topic_id=cid,
                    name=name,
                ),
            ]
        )
    for uid, cid in [
        ("ana", "diseno"),
        ("bruno", "tecnologia"),
        ("carla", "diseno"),
        ("elena", "sostenibilidad"),
    ]:
        for pk, sk in ((f"USER#{uid}", f"MEMBER#{cid}"), (f"COMM#{cid}", f"MEMBER#{uid}")):
            items.append(
                dict(PK=pk, SK=sk, entity_type="MEMBERSHIP", status="ACTIVE", created_at=instant)
            )
    writes.extend(db.put(repo["communities"].table, item) for item in items)
    items = []
    for other in ("bruno", "carla"):
        lo, hi = sorted(("diego", other))
        for pk, sk in (
            (f"FRIEND#{lo}#{hi}", "META"),
            ("USER#diego", f"CONTACT#{other}"),
            (f"USER#{other}", "CONTACT#diego"),
        ):
            items.append(dict(PK=pk, SK=sk, entity_type="FRIENDSHIP", status="ACTIVE"))
    writes.extend(db.put(repo["connections"].table, item) for item in items)
    writes.append(
        db.put(
            repo["profiles"].table,
            dict(PK="DEMO#v1", SK="META", entity_type="DEMO_SEED", created_at=instant),
        )
    )
    db.commit(repo.client, writes)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", default="http://127.0.0.1:18000")
    parser.add_argument("--table-prefix", default="Outspark-local")
    args = parser.parse_args()
    repo = local_storage(args.endpoint, args.table_prefix)
    seed(repo)
    print("Semilla lista: ana, bruno, carla, diego, elena. Datos anteriores conservados.")


if __name__ == "__main__":
    main()

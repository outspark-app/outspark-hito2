from dataclasses import dataclass

from outspark.shared.domain.value_objects import RuleViolation, identifier


@dataclass(frozen=True)
class FeedSnapshot:
    snapshot_id: str
    viewer_id: str

    def require_owner(self, actor):
        if self.viewer_id != actor:
            raise RuleViolation("snapshot_owner", "Snapshot de otra cuenta.")

    @staticmethod
    def validate(viewer, cards, originals, provenances):
        identifier(viewer)
        if len(cards) > 10 or len({c["publication_id"] for c in cards}) != len(cards):
            raise RuleViolation("invalid_snapshot", "Máximo diez originales distintos.")
        count, contacts, communities = 0, set(), set()
        for position, card in enumerate(cards):
            pid = identifier(card["publication_id"])
            post = originals[pid]
            if (
                card["position"] != position
                or post["status"] != "ACTIVE"
                or post["visibility"] != "public"
            ):
                raise RuleViolation("invalid_snapshot", "Tarjeta no elegible o posición inválida.")
            sources, paths = card["sources"], provenances[pid]["paths"]
            if (
                not sources
                or len({s["event_id"] for s in sources}) != len(sources)
                or len(sources) != len(paths)
            ):
                raise RuleViolation("invalid_sources", "Fuentes vacías, repetidas o incompletas.")
            count += len(sources)
            for source, path in zip(sources, paths):
                if (
                    not path
                    or path[-1]["event_id"] != source["event_id"]
                    or any(e["publication_id"] != pid for e in path)
                ):
                    raise RuleViolation("invalid_sources", "Ruta de otro original o incompleta.")
                reasons = source["reasons"]
                if (
                    not reasons
                    or len(reasons) > 4
                    or len({r["type"] for r in reasons}) != len(reasons)
                ):
                    raise RuleViolation("invalid_reasons", "Razones vacías o repetidas.")
                for reason in reasons:
                    if not 1 <= len(reason.get("text", "")) <= 160:
                        raise RuleViolation("invalid_reasons", "Texto de razón inválido.")
                    kind = reason["type"]
                    if kind == "contact":
                        actor = path[-1]["actor_id"]
                        if reason.get("contact_id") != actor or actor == viewer:
                            raise RuleViolation(
                                "invalid_reasons", "Contacto no corresponde al evento fuente."
                            )
                        contacts.add(actor)
                    elif kind == "community":
                        cid = reason.get("community_id")
                        if cid != post["community_id"]:
                            raise RuleViolation(
                                "invalid_reasons", "Comunidad no corresponde al original."
                            )
                        communities.add(cid)
                    elif kind == "own":
                        if post["author_id"] != viewer:
                            raise RuleViolation(
                                "invalid_reasons", "Original atribuido a otra cuenta."
                            )
                    elif kind == "discovery":
                        if reason.get("community_id") != post["community_id"]:
                            raise RuleViolation(
                                "invalid_reasons", "Comunidad de descubrimiento inválida."
                            )
                    else:
                        raise RuleViolation("invalid_reasons", "Tipo de razón desconocido.")
        if count > 200 or len(contacts) > 20 or len(communities) > 10:
            raise RuleViolation("snapshot_limit", "Se excedió el alcance acotado del feed.")
        return contacts, communities

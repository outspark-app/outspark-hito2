from outspark.shared.application.errors import UseCaseError
from outspark.shared.application.models import QueryBudget, digest

from ...domain.model.aggregates import FeedSnapshot
from ...domain.repositories.snapshots import SnapshotsRepository
from ...domain.services.selection import metrics
from ..outboundservices.network import Communities, Connections, Profiles, Publishing


class FeedCommands:
    def __init__(
        self,
        repository: SnapshotsRepository,
        queries,
        profiles: Profiles,
        connections: Connections,
        communities: Communities,
        publishing: Publishing,
        strategies,
        clock,
    ):
        self.repository, self.queries, self.profiles, self.connections = (
            repository,
            queries,
            profiles,
            connections,
        )
        self.communities, self.publishing, self.strategies, self.clock = (
            communities,
            publishing,
            strategies,
            clock,
        )

    def candidates(self, actor):
        budget = QueryBudget()
        active_contacts = self.connections.contacts(actor, budget)
        contacts = active_contacts[:20]
        member_ids = self.communities.memberships(actor, budget)
        followed = member_ids[:6]
        discoverable = [cid for cid in self.communities.catalog(budget) if cid not in member_ids]
        discovery = discoverable[:4]
        if len(active_contacts) > 20 or len(member_ids) > 6 or len(discoverable) > 4:
            budget.truncated = True
        budget.windows.append(
            {
                "selection": "feed_scope",
                "contacts": contacts,
                "followed_communities": followed,
                "discovery_communities": discovery,
            }
        )
        raw = {}

        def add(event, reason):
            entry = raw.setdefault(event["event_id"], {"event": event, "reasons": []})
            if reason not in entry["reasons"]:
                entry["reasons"].append(reason)

        actors = [actor, *contacts]
        for position, uid in enumerate(actors):
            count = 100 // len(actors) + (position < 100 % len(actors))
            for event in self.publishing.activity(uid, count, budget):
                add(
                    event,
                    {"type": "own", "text": "Tu publicación."}
                    if uid == actor
                    else {
                        "type": "contact",
                        "contact_id": uid,
                        "text": "Un contacto publicó o republicó el contenido.",
                    },
                )
        for ids, total, kind in ((followed, 60, "community"), (discovery, 40, "discovery")):
            for position, cid in enumerate(ids):
                count = total // len(ids) + (position < total % len(ids))
                for root in self.publishing.community_roots(cid, count, budget):
                    add(
                        root,
                        {
                            "type": kind,
                            "community_id": cid,
                            "text": "Sigues esta comunidad."
                            if kind == "community"
                            else "Conversación pública del catálogo.",
                        },
                    )
        ids = sorted({entry["event"]["publication_id"] for entry in raw.values()})
        originals, unprocessed = self.publishing.originals(ids, budget)
        cards = {}
        for ref, entry in raw.items():
            event, post = entry["event"], originals.get(entry["event"]["publication_id"])
            if not post or post["status"] != "ACTIVE":
                continue
            reasons = [
                r for r in entry["reasons"] if r["type"] != "own" or post["author_id"] == actor
            ]
            if not reasons:
                continue
            card = cards.setdefault(
                post["publication_id"], {"sources": [], "latest_at": event["created_at"]}
            )
            card["sources"].append({"event_id": ref, "reasons": reasons})
            card["latest_at"] = max(card["latest_at"], event["created_at"])
        for card in cards.values():
            card["sources"].sort(key=lambda source: source["event_id"])
        return cards, originals, budget, unprocessed

    def generate(self, actor, strategy="chronological", compare=False):
        if strategy not in self.strategies:
            raise UseCaseError(400, "invalid_strategy", "Usa chronological o diverse.")
        instant, profile = self.clock(), self.profiles.actor(actor)
        cards, originals, budget, unprocessed = self.candidates(actor)
        strategies = ("chronological", "diverse") if compare else (strategy,)
        selections = {
            s: self.strategies[s].select(cards, originals, profile["topic_ids"], instant)
            for s in strategies
        }
        # Recover all observed sources once per selected original; compare shares this materialization.
        trees = {}
        for selection in selections.values():
            for card in selection:
                pid = card["publication_id"]
                if pid not in trees:
                    trees[pid] = self.publishing.provenance(
                        pid, [s["event_id"] for s in cards[pid]["sources"]], budget
                    )
        fingerprint = digest(
            [{"publication": originals[pid], **cards[pid]} for pid in sorted(cards)]
        )
        responses = {}
        for name, selection in selections.items():
            contacts, communities = FeedSnapshot.validate(actor, selection, originals, trees)
            guards = (
                profile["active_guard"],
                *(self.publishing.active_guard(c["publication_id"]) for c in selection),
                *(self.connections.active_guard(actor, other) for other in sorted(contacts)),
                *(self.communities.membership_guard(actor, cid) for cid in sorted(communities)),
            )
            metadata = {
                "candidate_hash": fingerprint,
                "candidate_events": sum(len(c["sources"]) for c in cards.values()),
                "candidate_originals": len(cards),
                "reference_at": instant,
                "preferences": {"topic_ids": profile["topic_ids"], "version": profile["version"]},
                "parameters": {
                    "topic_weight": "0.7",
                    "recency_weight": "0.3",
                    "lambda": "0.3",
                    "recency_days": 7,
                    "author_cap": 2,
                    "k": 10,
                },
                "retrieval": {
                    "query_pages": budget.pages,
                    "query_budget": budget.maximum,
                    "truncated": budget.truncated,
                    "windows": budget.windows,
                    "query_batch_read_units": f"{budget.units:.3f}",
                    "unprocessed_originals": unprocessed,
                },
                "metrics": metrics(selection, originals, profile["topic_ids"], instant),
            }
            sid = self.repository.save(actor, selection, instant, name, metadata, guards)
            responses[name] = self.queries.read(actor, sid)
        return (
            {"feeds": responses, "candidate_hash": fingerprint} if compare else responses[strategy]
        )

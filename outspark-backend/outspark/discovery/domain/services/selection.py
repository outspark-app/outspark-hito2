from datetime import datetime


def relevance(post, topics, instant):
    matching = len(set(post["topic_ids"]) & set(topics)) / len(post["topic_ids"])
    age = (
        datetime.fromisoformat(instant.replace("Z", "+00:00"))
        - datetime.fromisoformat(post["created_at"].replace("Z", "+00:00"))
    ).total_seconds()
    recency = max(0.0, min(1.0, 1 - age / (7 * 86400)))
    return 0.7 * matching + 0.3 * recency


def select(cards, originals, topics, instant, strategy, k=10):
    """Mejor elección factible sin revertir: Semana12, pp. 3–4.

    El objetivo de diversidad y los pesos son diseño propio, no un ejemplo
    enseñado ni una garantía de óptimo. Barrido explícito O(kC).
    """
    if strategy not in ("chronological", "diverse"):
        raise ValueError("Estrategia inválida")
    pending = dict(cards)
    authors, communities, selected = {}, set(), []
    while pending and len(selected) < k:
        best_id, best_key = None, None
        for pid, card in pending.items():
            post = originals[pid]
            if authors.get(post["author_id"], 0) >= 2:
                continue
            score = relevance(post, topics, instant)
            gain = score + (0.3 if post["community_id"] not in communities else 0)
            chronological_key = (card["latest_at"], pid)
            key = (gain, *chronological_key) if strategy == "diverse" else chronological_key
            if best_key is None or key > best_key:
                best_id, best_key = pid, key
        if best_id is None:
            break
        post, card = originals[best_id], pending.pop(best_id)
        selected.append(
            {
                "publication_id": best_id,
                "position": len(selected),
                "sources": card["sources"],
                "relevance": f"{relevance(post, topics, instant):.6f}",
                "selection_reason": "Mejor ganancia factible"
                if strategy == "diverse"
                else "Actividad más reciente",
            }
        )
        authors[post["author_id"]] = authors.get(post["author_id"], 0) + 1
        communities.add(post["community_id"])
    return selected


def metrics(cards, originals, topics, instant):
    communities = len({originals[c["publication_id"]]["community_id"] for c in cards})
    total = sum(relevance(originals[c["publication_id"]], topics, instant) for c in cards)
    return {
        "cards": len(cards),
        "communities": communities,
        "objective": f"{total + 0.3 * communities:.6f}",
        "mean_relevance": f"{total / len(cards) if cards else 0:.6f}",
    }


class ChronologicalStrategy:
    name = "chronological"

    def select(self, cards, originals, topics, instant):
        return select(cards, originals, topics, instant, self.name)


class DiverseGreedyStrategy:
    name = "diverse"

    def select(self, cards, originals, topics, instant):
        return select(cards, originals, topics, instant, self.name)

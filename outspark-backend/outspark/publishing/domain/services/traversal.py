"""Adaptaciones del curso. Véase ALGORITMOS.md para fuentes y límites."""


def tree_dfs(events, root_ref):
    """Pila LIFO y visitados: Semana5.1, pp. 8–9; O(R+T), sin ordenar."""
    lookup = {e["event_id"]: e for e in events}
    if len(lookup) != len(events) or root_ref not in lookup:
        raise ValueError("Eventos duplicados o raíz ausente")
    root = lookup[root_ref]
    if root["parent_event_id"] is not None:
        raise ValueError("Raíz con padre")
    children = {ref: [] for ref in lookup}
    for e in events:
        if e["publication_id"] != root["publication_id"]:
            raise ValueError("Eventos de otro original")
        parent = e["parent_event_id"]
        if parent is not None:
            if parent not in lookup:
                raise ValueError("Padre ausente")
            children[parent].append(e["event_id"])
        elif e["event_id"] != root_ref:
            raise ValueError("Raíz adicional")
    stack, visited, order = [(root_ref, 0)], set(), []
    while stack:
        ref, depth = stack.pop()
        if ref in visited:
            raise ValueError("Ciclo en procedencia")
        visited.add(ref)
        order.append({"event_id": ref, "depth": depth})
        for child in reversed(children[ref]):
            stack.append((child, depth + 1))
    if len(visited) != len(lookup):
        raise ValueError("Componente desconectada o ciclo en procedencia")
    return order

"""Componentes conexas por BFS sobre listas de adyacencia.

Base: 01_2_BFS_y_Lista_de_Adyacencia_LA.ipynb, celda 4 (numeración
humana), y Semana5.1, pp. 12–13. Se reinicia BFS en cada nodo no visitado.
La cola usa una lista con índice de lectura para evitar desplazarla con pop(0).
No identifica comunidades por densidad ni mide influencia.
"""

METHOD = "outspark-bfs-components/2.0"


class InvalidGraphError(ValueError):
    """La entrada debe representar un grafo simple no dirigido."""


def _validate_graph(adjacency):
    if not isinstance(adjacency, dict):
        raise InvalidGraphError("Se requiere un diccionario de adyacencias")
    degree_sum = 0
    for node, neighbors in adjacency.items():
        if type(node) is not int or not isinstance(neighbors, (set, list)):
            raise InvalidGraphError(
                "Se requieren identificadores enteros y listas/conjuntos de vecinos"
            )
        seen = set()
        for neighbor in neighbors:
            if type(neighbor) is not int or neighbor == node or neighbor in seen:
                raise InvalidGraphError("Vecino inválido, autoarista o arista repetida")
            seen.add(neighbor)
            if neighbor not in adjacency:
                raise InvalidGraphError("Vecino ausente del grafo")
        degree_sum += len(neighbors)
    # Convertir una vez evita búsquedas lineales por arista si se reciben listas.
    membership = {node: set(neighbors) for node, neighbors in adjacency.items()}
    for node, neighbors in adjacency.items():
        for neighbor in neighbors:
            if node not in membership[neighbor]:
                raise InvalidGraphError("Arista sin su inversa")
    return degree_sum // 2


def connected_components(adjacency, *, should_stop=None):
    """BFS O(V+E); no modifica la entrada. Interrupciones no se publican.

    Los IDs de componentes son sus nodos mínimos; no dependen del orden de
    entrada. Se recorren todas las componentes, incluidos nodos aislados.
    """
    edges = _validate_graph(adjacency)
    if should_stop is not None and not callable(should_stop):
        raise TypeError("should_stop debe ser invocable")
    visited = set()
    groups, group_by_node = [], {}
    complete = True
    for start in adjacency:
        if start in visited:
            continue
        queue = [start]
        visited.add(start)
        head = 0
        interrupted = False
        while head < len(queue):
            if should_stop is not None and should_stop(len(visited)):
                interrupted = True
                break
            current = queue[head]
            head += 1
            for neighbor in adjacency[current]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        if interrupted:
            complete = False
            break
        group_id = min(queue)
        for node in queue:
            group_by_node[node] = group_id
        groups.append(queue)
    return {
        "group_by_node": group_by_node,
        "groups": groups,
        "nodes": len(adjacency),
        "edges": edges,
        "visited_nodes": len(group_by_node),
        "complete": complete,
        "method": METHOD,
    }


def degree_ranking(adjacency, group_by_node):
    """Conteo de vecinos O(V); ordenación O(V log V), sin métrica externa.

    Una componente conexa no tiene aristas a otras componentes. Se muestran
    grados, sin inventar conectores entre componentes ni influencia observada.
    Para una ejecución interrumpida solo se incluyen componentes terminadas.
    """
    rows = []
    for node in group_by_node:
        rows.append(
            {"node_id": node, "group_id": group_by_node[node], "degree": len(adjacency[node])}
        )
    rows.sort(key=lambda row: (-row["degree"], row["node_id"]))
    return rows

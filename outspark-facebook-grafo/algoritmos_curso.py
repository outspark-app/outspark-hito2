"""Núcleo académico: Python básico, listas de adyacencia, BFS y Graphviz."""
import graphviz as gv


def leer_amistades(nombre):
    labels = []
    w2i = {}
    graph = []
    added = set()
    with open(nombre) as archivo:
        for linea in archivo:
            datos = linea.split()
            if not datos:
                continue
            a, b = int(datos[0]), int(datos[1])
            for usuario in [a, b]:
                if usuario not in w2i:
                    w2i[usuario] = len(labels)
                    labels.append(usuario)
                    graph.append([])
            u, v = w2i[a], w2i[b]
            if u != v and (u, v) not in added:
                graph[u].append(v)
                graph[v].append(u)
                added.add((u, v))
                added.add((v, u))
    return graph, labels, w2i


def bfs(graph, start):
    visited = [False] * len(graph)
    path = [-1] * len(graph)
    distance = [-1] * len(graph)
    queue = [start]
    visited[start] = True
    distance[start] = 0
    head = 0
    while head < len(queue):
        u = queue[head]
        head += 1
        for v in graph[u]:
            if not visited[v]:
                visited[v] = True
                path[v] = u
                distance[v] = distance[u] + 1
                queue.append(v)
    return path, distance


def componentes(graph):
    visited = [False] * len(graph)
    groups = []
    for start in range(len(graph)):
        if visited[start]:
            continue
        queue = [start]
        visited[start] = True
        head = 0
        while head < len(queue):
            u = queue[head]
            head += 1
            for v in graph[u]:
                if not visited[v]:
                    visited[v] = True
                    queue.append(v)
        groups.append(queue)
    return groups


def subgrafo(graph, labels, start, limit=45):
    selected = [start]
    for v in graph[start]:
        if len(selected) >= limit:
            break
        selected.append(v)
    indices = {}
    for i in range(len(selected)):
        indices[selected[i]] = i
    result = [[] for _ in selected]
    for u in selected:
        for v in graph[u]:
            if v in indices:
                result[indices[u]].append(indices[v])
    return result, [labels[u] for u in selected]


def subgrafo_bfs(graph, labels, start, limit=1500):
    selected = [start]
    visited = {start}
    head = 0
    while head < len(selected) and len(selected) < limit:
        u = selected[head]
        head += 1
        for v in sorted(graph[u], key=lambda index: labels[index]):
            if v not in visited:
                visited.add(v)
                selected.append(v)
                if len(selected) == limit:
                    break
    indices = {}
    for i in range(len(selected)):
        indices[selected[i]] = i
    result = [[] for _ in selected]
    for u in selected:
        for v in graph[u]:
            if v in indices:
                result[indices[u]].append(indices[v])
    return result, [labels[u] for u in selected]


def dibujar(graph, labels):
    drawing = gv.Graph("Amistades", engine="sfdp")
    drawing.graph_attr["overlap"] = "true" if len(graph) > 100 else "false"
    drawing.graph_attr["start"] = "7"
    drawing.graph_attr["size"] = "12,8!"
    for u in range(len(graph)):
        if len(graph) > 100:
            drawing.node(str(u), label="", shape="point", width="0.02")
        else:
            drawing.node(str(u), str(labels[u]), fontsize="8")
    added = set()
    for u in range(len(graph)):
        for v in graph[u]:
            if (u, v) not in added:
                drawing.edge(str(u), str(v))
                added.add((u, v))
                added.add((v, u))
    return drawing

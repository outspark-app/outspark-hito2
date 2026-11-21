"""Audita y visualiza el grafo Facebook New Orleans de MPI-SWS.

Entrada: facebook-links.txt.gz y facebook-wall.txt.gz originales.
Las amistades se convierten en aristas no dirigidas; cada publicación de muro
mantiene el sentido autor -> dueño del muro y su marca temporal.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import graphviz as gv


def lines(path: Path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="ascii") as stream:
        for number, raw in enumerate(stream, start=1):
            row = raw.rstrip("\r\n").split("\t")
            if len(row) != 3:
                raise ValueError(f"{path.name}:{number}: se esperaban 3 columnas")
            try:
                first, second = int(row[0]), int(row[1])
                stamp = None if row[2] == r"\N" else int(row[2])
            except ValueError as exc:
                raise ValueError(f"{path.name}:{number}: valor inválido") from exc
            yield first, second, stamp


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def date_utc(stamp: int | None) -> str | None:
    if stamp is None:
        return None
    return datetime.fromtimestamp(stamp, timezone.utc).strftime("%Y-%m-%d")


def load_friendships(path: Path):
    graph = {}
    rows = loops = timestamps = 0
    first_time = last_time = None
    for owner, friend, stamp in lines(path):
        rows += 1
        if owner not in graph:
            graph[owner] = set()
        if friend not in graph:
            graph[friend] = set()
        if owner != friend:
            graph[owner].add(friend)
            graph[friend].add(owner)
        if owner == friend:
            loops += 1
        if stamp is not None:
            timestamps += 1
            first_time = stamp if first_time is None else min(first_time, stamp)
            last_time = stamp if last_time is None else max(last_time, stamp)
    return graph, {
        "filas_amistad_dirigidas": rows,
        "aristas_amistad_no_dirigidas_unicas": sum(len(neighbors) for neighbors in graph.values()) // 2,
        "filas_lazo": loops,
        "filas_con_fecha_amistad": timestamps,
        "primera_amistad_utc": date_utc(first_time),
        "ultima_amistad_utc": date_utc(last_time),
    }


def load_wall_posts(path: Path):
    owners: set[int] = set()
    authors: set[int] = set()
    self_posts = rows = 0
    first_time = last_time = None
    for owner, author, stamp in lines(path):
        if stamp is None:
            raise ValueError("Una publicación de muro carece de fecha")
        rows += 1
        owners.add(owner)
        authors.add(author)
        self_posts += owner == author
        first_time = stamp if first_time is None else min(first_time, stamp)
        last_time = stamp if last_time is None else max(last_time, stamp)
    return authors, {
        "filas_publicaciones_muro": rows,
        "autores_distintos": len(authors),
        "duenos_muro_distintos": len(owners),
        "usuarios_muro_distintos": len(authors | owners),
        "publicaciones_muro_propio": self_posts,
        "primera_publicacion_utc": date_utc(first_time),
        "ultima_publicacion_utc": date_utc(last_time),
        "direccion": "segunda columna (autor) -> primera columna (dueño del muro)",
    }, owners | authors


def component_groups(graph):
    visited = set()
    groups = []
    for start in graph:
        if start in visited:
            continue
        queue = [start]
        visited.add(start)
        head = 0
        while head < len(queue):
            current = queue[head]
            head += 1
            for neighbor in graph[current]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        groups.append(queue)
    return groups


def components(graph):
    return sorted([len(group) for group in component_groups(graph)], reverse=True)


def reach_by_hops(graph: dict, seed: int, max_hops: int = 3):
    if seed not in graph:
        raise ValueError(f"El usuario {seed} no aparece en las amistades")
    seen = {seed}
    frontier = {seed}
    rounds = []
    for hop in range(1, max_hops + 1):
        following = set()
        for user in frontier:
            following.update(set(graph[user]) - seen)
        seen.update(following)
        rounds.append({"saltos": hop, "nuevos": len(following), "acumulados_sin_semilla": len(seen) - 1})
        frontier = following
    return rounds


def draw_graph(graph, output, *, authors=None, seed=None, full=False):
    """Graphviz, como drawG_al de los notebooks; no calcula conectividad."""
    drawing = gv.Graph("Facebook", engine="sfdp", format="png")
    drawing.attr(overlap="true" if full else "false", outputorder="edgesfirst", bgcolor="white",
                 start="7", size="12,8!", dpi="120")
    drawing.attr("edge", color="#B8C2CC", penwidth="0.3" if full else "0.8")
    for user in graph:
        if full:
            drawing.node(str(user), label="", shape="point", width="0.015", color="#2679A8")
        else:
            color = "#C62828" if user == seed else "#2679A8" if user in authors else "#AAB8C2"
            drawing.node(str(user), label=str(user), color=color, fontsize="8", width="0.15")
    for user in graph:
        for friend in graph[user]:
            if user < friend:
                drawing.edge(str(user), str(friend))
    drawing.save(filename=str(output.with_suffix(".dot")))
    drawing.render(filename=str(output.with_suffix("")), cleanup=False)


def draw_subgraph(graph: dict, authors: set[int], seed: int, output: Path, limit: int):
    if seed not in graph:
        raise ValueError(f"El usuario {seed} no aparece en las amistades")
    neighbors = sorted(graph[seed], key=lambda user: (-len(graph[user]), user))[: limit - 1]
    selected = set([seed] + neighbors)
    subgraph = {user: graph[user] & selected for user in sorted(selected)}
    draw_graph(subgraph, output, authors=authors, seed=seed)
    return {"nodos": len(subgraph),
            "aristas": sum(len(neighbors) for neighbors in subgraph.values()) // 2,
            "semilla": seed, "criterio": f"semilla y {len(neighbors)} vecinos con mayor grado",
            "layout": "Graphviz sfdp"}


def draw_full_graph(graph: dict, output: Path):
    draw_graph(graph, output, full=True)
    return {"tipo": "grafo de nodos y aristas", "nodos": len(graph),
            "aristas_dibujadas": sum(len(neighbors) for neighbors in graph.values()) // 2,
            "layout": "Graphviz sfdp", "sin_muestreo": True,
            "archivo_dot": output.with_suffix(".dot").name}


def draw_overview(graph, seed, output, limit=1500):
    if seed not in graph:
        raise ValueError("La semilla no pertenece al grafo")
    queue = [seed]
    selected = {seed}
    head = 0
    while head < len(queue) and len(selected) < limit:
        current = queue[head]
        head += 1
        for neighbor in sorted(graph[current]):
            if neighbor not in selected:
                selected.add(neighbor)
                queue.append(neighbor)
                if len(selected) == limit:
                    break
    subgraph = {node: graph[node] & selected for node in queue}
    draw_graph(subgraph, output, full=True)
    return {"nodos": len(subgraph),
            "aristas": sum(len(neighbors) for neighbors in subgraph.values()) // 2,
            "criterio": "subgrafo inducido por los primeros 1500 nodos de BFS",
            "grafo_completo": len(subgraph) == len(graph), "layout": "Graphviz sfdp"}


def export_full_edge_list(graph: dict, output: Path):
    """Escribe el grafo íntegro en formato CSV comprimido para reproducirlo."""
    with gzip.open(output, "wt", encoding="ascii") as stream:
        stream.write("usuario_1,usuario_2\n")
        for user in sorted(graph):
            for friend in sorted(graph[user]):
                if user < friend:
                    stream.write(f"{user},{friend}\n")


def analyze(links: Path, wall: Path, output: Path, seed: int, figure_nodes: int, full_graph=False):
    output.mkdir(parents=True, exist_ok=True)
    graph, link_stats = load_friendships(links)
    authors, wall_stats, wall_users = load_wall_posts(wall)
    sizes = components(graph)
    degrees = sorted(((len(graph[user]), user) for user in graph), reverse=True)
    full_figure = draw_full_graph(graph, output / "grafo_completo_facebook.png") if full_graph else {"generada": False, "motivo": "Opcional: usar --full-graph"}
    overview = draw_overview(graph, seed, output / "vista_general_facebook.png")
    export_full_edge_list(graph, output / "aristas_amistad_completa.csv.gz")
    figure = draw_subgraph(graph, authors, seed, output / "subgrafo_facebook.png", figure_nodes)
    result = {
        "fuente": "MPI-SWS, Facebook New Orleans, WOSN 2009",
        "archivos": {links.name: sha256(links), wall.name: sha256(wall)},
        "amistades": {
            **link_stats,
            "usuarios_nodos": len(graph),
            "componentes_conexas": len(sizes),
            "componente_mayor": sizes[0],
            "cinco_componentes_mayores": sizes[:5],
            "grado_maximo": degrees[0][0],
            "usuario_grado_maximo": degrees[0][1],
            "usuarios_sin_aristas_en_archivo": sum(len(graph[user]) == 0 for user in graph),
            "observacion": "La lista de enlaces no enumera usuarios sin aparición en una arista.",
        },
        "muro": {**wall_stats, "usuarios_muro_presentes_en_amistades": len(wall_users & set(graph))},
        "bfs": {"semilla": seed, "rondas": reach_by_hops(graph, seed)},
        "figura_completa": full_figure,
        "vista_general": overview,
        "figura": figure,
        "limite_interpretacion": "No hay ID de publicación, contenido ni trazas de republicación: no se pueden reconstruir cadenas históricas de compartidos.",
    }
    destination = output / "estadisticas_facebook.json"
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"nodos": len(graph), "aristas": link_stats["aristas_amistad_no_dirigidas_unicas"], "publicaciones_muro": wall_stats["filas_publicaciones_muro"], "estadisticas": str(destination), "grafo_completo": str(output / "grafo_completo_facebook.png") if full_graph else None, "vista_general": str(output / "vista_general_facebook.png"), "subgrafo": str(output / "subgrafo_facebook.png")}, ensure_ascii=False))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--links", type=Path, default=Path("facebook-links.txt.gz"))
    parser.add_argument("--wall", type=Path, default=Path("facebook-wall.txt.gz"))
    parser.add_argument("--out", type=Path, default=Path("salida_facebook"))
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--figure-nodes", type=int, default=45)
    parser.add_argument("--full-graph", action="store_true", help="Render opcional de todos los nodos y aristas; puede tardar varios minutos")
    args = parser.parse_args(argv)
    if args.figure_nodes < 2:
        parser.error("--figure-nodes debe ser al menos 2")
    return analyze(args.links, args.wall, args.out, args.seed, args.figure_nodes, args.full_graph)


if __name__ == "__main__":
    main()

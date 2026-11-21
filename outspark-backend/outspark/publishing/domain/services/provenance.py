"""Cadena de padre único sobre eventos ya cargados."""

from outspark.publishing.domain.model.value_objects import EventReference


def routes(events, sources, root_ref):
    lookup = {e["event_id"]: e for e in events}
    origin = EventReference.parse(root_ref).publication_id
    paths = []
    for source in sources:
        current, seen, path = source, set(), []
        while current is not None:
            if current in seen:
                raise ValueError("Ciclo en datos de procedencia")
            if current not in lookup:
                raise ValueError("Padre ausente al leer procedencia")
            seen.add(current)
            event = lookup[current]
            if (
                EventReference.parse(current).publication_id != origin
                or event["publication_id"] != origin
            ):
                raise ValueError("Referencia cruzada de contenido")
            path.append(event)
            current = event["parent_event_id"]
        if path[-1]["event_id"] != root_ref:
            raise ValueError("Raíz diferente de la registrada")
        paths.append(list(reversed(path)))
    return paths

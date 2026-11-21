import 'dart:math';
import 'package:flutter/material.dart' hide Page;
import '../application/session_controller.dart';
import '../domain/models.dart';
import '../ui/design_system.dart';
import 'structural_view.dart';

class NetworkView extends StatefulWidget {
  const NetworkView({super.key, required this.session});
  final SessionController session;
  @override
  State<NetworkView> createState() => _NetworkViewState();
}

class _NetworkViewState extends State<NetworkView> {
  final input = TextEditingController(text: '1');
  JsonMap? manifest, node, bfs;
  final neighbors = <JsonMap>[], walls = <JsonMap>[];
  String? nextNeighbors, nextWalls, error;
  int seed = 1, hops = 2;
  bool loading = true, calculating = false, more = false;
  int generation = 0;
  @override
  void initState() {
    super.initState();
    load();
  }

  @override
  void dispose() {
    generation++;
    input.dispose();
    super.dispose();
  }

  Future<void> load() async {
    final parsed = int.tryParse(input.text.trim());
    if (parsed == null || parsed < 0) {
      setState(() => error = 'Escribe un identificador entero no negativo.');
      return;
    }
    final own = ++generation;
    setState(() {
      loading = true;
      calculating = false;
      more = false;
      error = null;
      bfs = null;
      node = null;
    });
    final repository = widget.session.repository;
    try {
      final values = await Future.wait<Object>([
        repository.dataset(),
        repository.node(parsed),
        repository.neighbors(parsed),
        repository.wallEvents(parsed),
      ]);
      if (!mounted || own != generation) return;
      final ns = values[2] as Page<JsonMap>, ws = values[3] as Page<JsonMap>;
      setState(() {
        seed = parsed;
        manifest = values[0] as JsonMap;
        node = values[1] as JsonMap;
        neighbors
          ..clear()
          ..addAll(ns.items);
        walls
          ..clear()
          ..addAll(ws.items);
        nextNeighbors = ns.nextCursor;
        nextWalls = ws.nextCursor;
      });
    } catch (e) {
      if (mounted && own == generation) setState(() => error = e.toString());
    } finally {
      if (mounted && own == generation) setState(() => loading = false);
    }
  }

  Future<void> reach() async {
    final own = generation;
    setState(() {
      calculating = true;
      error = null;
      bfs = null;
    });
    try {
      final result = await widget.session.repository.reach(seed, hops);
      if (mounted && own == generation) setState(() => bfs = result);
    } catch (e) {
      if (mounted && own == generation) setState(() => error = e.toString());
    } finally {
      if (mounted && own == generation) setState(() => calculating = false);
    }
  }

  Future<void> moreRecords(bool wall) async {
    final own = generation;
    setState(() => more = true);
    try {
      final result = wall
          ? await widget.session.repository.wallEvents(seed, cursor: nextWalls)
          : await widget.session.repository.neighbors(
              seed,
              cursor: nextNeighbors,
            );
      if (mounted && own == generation) {
        setState(() {
          if (wall) {
            walls.addAll(result.items);
            nextWalls = result.nextCursor;
          } else {
            neighbors.addAll(result.items);
            nextNeighbors = result.nextCursor;
          }
        });
      }
    } catch (e) {
      if (mounted && own == generation) setState(() => error = e.toString());
    } finally {
      if (mounted && own == generation) setState(() => more = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final counts = manifest?['counts'] as Map? ?? {};
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const PageHeading(
          'La red, de cerca.',
          'Explora amistades históricas y mide hasta dónde llega una conexión. Los eventos nuevos de Outspark viven en otra red.',
        ),
        if (manifest != null)
          PaperPanel(
            child: Wrap(
              spacing: 40,
              runSpacing: 22,
              children: [
                _fact(
                  formatCount(counts['friendship_nodes']),
                  'nodos del grafo de amistades',
                ),
                _fact(
                  formatCount(counts['unique_friendships']),
                  'amistades únicas',
                ),
                _fact(
                  formatCount(counts['wall_events']),
                  'eventos de muro, sin texto',
                ),
              ],
            ),
          ),
        const SizedBox(height: 24),
        Wrap(
          spacing: 14,
          runSpacing: 14,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            SizedBox(
              width: 230,
              child: TextField(
                controller: input,
                enabled: !loading && !calculating,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(
                  labelText: 'Identificador histórico',
                  helperText: 'Por ejemplo, 1',
                ),
                onSubmitted: (_) => load(),
              ),
            ),
            FilledButton.icon(
              onPressed: loading || calculating ? null : load,
              icon: const Icon(Icons.search, size: 20),
              label: const Text('Explorar nodo'),
            ),
          ],
        ),
        const SizedBox(height: 22),
        if (error != null)
          Padding(
            padding: const EdgeInsets.only(bottom: 20),
            child: Recovery(message: error!, retry: load),
          ),
        if (loading)
          const LoadingContent()
        else if (node != null) ...[
          LayoutBuilder(
            builder: (context, size) {
              final graph = PaperPanel(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            'El círculo de $seed',
                            style: Theme.of(context).textTheme.titleLarge,
                          ),
                        ),
                        Text(
                          '${formatCount(node!['degree'])} amistades',
                          style: const TextStyle(color: muted, fontSize: 12),
                        ),
                      ],
                    ),
                    const SizedBox(height: 20),
                    Semantics(
                      label:
                          'Subgrafo de amistades. Nodo $seed conectado con ${neighbors.take(24).map((n) => n['node_id']).join(', ')}. No se muestran conexiones entre vecinos.',
                      child: SizedBox(
                        height: 310,
                        child: CustomPaint(
                          painter: _Neighborhood(
                            seed,
                            neighbors
                                .take(24)
                                .map((n) => (n['node_id'] as num).toInt())
                                .toList(),
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(height: 16),
                    Text(
                      'Subgrafo de hasta 24 vecinos recuperados. Solo se dibujan sus enlaces con $seed; no representa el grafo completo.',
                      style: const TextStyle(color: muted, fontSize: 12),
                    ),
                  ],
                ),
              );
              final search = PaperPanel(
                color: const Color(0xFFFFFBEB),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const Icon(Icons.route_outlined, size: 32, color: ink),
                    const SizedBox(height: 18),
                    Text(
                      '¿Hasta dónde conecta?',
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                    const SizedBox(height: 12),
                    const Text(
                      'BFS explora primero las amistades más cercanas. Cada nivel agrega personas todavía no visitadas.',
                      style: TextStyle(color: muted),
                    ),
                    const SizedBox(height: 20),
                    DropdownButtonFormField<int>(
                      initialValue: hops,
                      decoration: const InputDecoration(
                        labelText: 'Saltos máximos',
                      ),
                      items: [1, 2, 3]
                          .map(
                            (n) => DropdownMenuItem(
                              value: n,
                              child: Text('$n ${n == 1 ? 'salto' : 'saltos'}'),
                            ),
                          )
                          .toList(),
                      onChanged: calculating
                          ? null
                          : (n) => setState(() => hops = n!),
                    ),
                    const SizedBox(height: 18),
                    FilledButton(
                      onPressed: calculating ? null : reach,
                      child: Text(
                        calculating
                            ? 'Recorriendo la red…'
                            : 'Calcular alcance BFS',
                      ),
                    ),
                    const SizedBox(height: 16),
                    const Text(
                      'Alcance topológico: no equivale a difusión de un mensaje. Si se supera el presupuesto, se informa el límite y no se presenta un resultado parcial como completo.',
                      style: TextStyle(fontSize: 12, color: muted),
                    ),
                  ],
                ),
              );
              if (size.maxWidth < 850) {
                return Column(
                  children: [graph, const SizedBox(height: 20), search],
                );
              }
              return Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(flex: 3, child: graph),
                  const SizedBox(width: 24),
                  Expanded(flex: 2, child: search),
                ],
              );
            },
          ),
          if (bfs != null)
            Padding(
              padding: const EdgeInsets.only(top: 24),
              child: PaperPanel(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Text(
                      '${formatCount(bfs!['visited_nodes'])} nodos visitados',
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Origen $seed incluido · máximo ${bfs!['max_hops']} saltos · resultado ${bfs!['complete'] == true ? 'completo dentro del límite solicitado' : 'acotado'}',
                      style: const TextStyle(color: muted),
                    ),
                    const SizedBox(height: 20),
                    ...((bfs!['rounds'] as List?) ?? []).map(
                      (round) => Padding(
                        padding: const EdgeInsets.only(bottom: 12),
                        child: Row(
                          children: [
                            SizedBox(
                              width: 82,
                              child: Text(
                                'Salto ${round['hops']}',
                                style: const TextStyle(
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                            ),
                            Expanded(
                              child: Text(
                                '${formatCount(round['new_nodes'])} nuevos · ${formatCount(round['total_without_seed'])} alcanzados sin el origen',
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                    const Divider(),
                    SelectableText(
                      'Dataset: ${bfs!['dataset_id']}\nParámetros e IO: ${bfs!['storage']}',
                      style: const TextStyle(color: muted, fontSize: 12),
                    ),
                  ],
                ),
              ),
            ),
          const SizedBox(height: 30),
          Text(
            'Vecinos del nodo $seed',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 14),
          if (neighbors.isEmpty)
            const Text('Este nodo no tiene amistades registradas.')
          else
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: neighbors
                  .take(150)
                  .map(
                    (n) => ActionChip(
                      label: Text('${n['node_id']}'),
                      onPressed: calculating
                          ? null
                          : () {
                              input.text = '${n['node_id']}';
                              load();
                            },
                    ),
                  )
                  .toList(),
            ),
          if (nextNeighbors != null && neighbors.length < 150)
            Align(
              alignment: Alignment.centerLeft,
              child: TextButton(
                onPressed: more ? null : () => moreRecords(false),
                child: const Text('Cargar más vecinos'),
              ),
            ),
          const SizedBox(height: 30),
          Text(
            'Actividad histórica del muro',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 10),
          const Text(
            'Participantes y fechas originales. El dataset no contiene el texto ni cadenas observadas de republicación.',
            style: TextStyle(color: muted),
          ),
          const SizedBox(height: 18),
          if (walls.isEmpty)
            const Text('Sin eventos recibidos registrados para este nodo.'),
          ...walls
              .take(100)
              .map(
                (w) => Padding(
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Icon(Icons.history, size: 20, color: muted),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              '${w['author_id']} escribió en el muro de ${w['wall_owner_id']}',
                              style: const TextStyle(
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                            Text(
                              '${moment(DateTime.fromMillisecondsSinceEpoch((w['timestamp'] as num).toInt() * 1000, isUtc: true))} · línea ${w['source_line']} · contenido no disponible',
                              style: const TextStyle(
                                color: muted,
                                fontSize: 12,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
          if (nextWalls != null && walls.length < 100)
            Align(
              alignment: Alignment.centerLeft,
              child: OutlinedButton(
                onPressed: more ? null : () => moreRecords(true),
                child: const Text('Cargar más eventos'),
              ),
            ),
        ],
        const SizedBox(height: 34),
        StructuralView(session: widget.session, nodeId: seed),
        if (manifest != null)
          Padding(
            padding: const EdgeInsets.only(top: 30),
            child: ExpansionTile(
              tilePadding: EdgeInsets.zero,
              title: const Text('Origen e integridad de los datos'),
              children: [
                Align(
                  alignment: Alignment.centerLeft,
                  child: SelectableText(
                    '${manifest!['source']}\n${formatCount(counts['nodes'])} nodos totales: ${formatCount(counts['friendship_nodes'])} en amistades y ${formatCount(counts['wall_only_nodes'])} exclusivos del muro.\nVersión de esquema: ${manifest!['schema_version']} · ${manifest!['full_dataset'] == true ? 'Dataset completo verificado' : 'Alcance parcial'}\n${manifest!['interpretation']}\nArchivos y hashes: ${manifest!['files']}',
                    style: const TextStyle(
                      color: muted,
                      fontSize: 12,
                      height: 1.7,
                    ),
                  ),
                ),
              ],
            ),
          ),
      ],
    );
  }

  Widget _fact(String value, String label) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(
        value,
        style: const TextStyle(
          fontSize: 28,
          fontWeight: FontWeight.w700,
          letterSpacing: -.5,
        ),
      ),
      const SizedBox(height: 6),
      Text(label, style: const TextStyle(color: muted, fontSize: 13)),
    ],
  );
}

class _Neighborhood extends CustomPainter {
  const _Neighborhood(this.seed, this.neighbors);
  final int seed;
  final List<int> neighbors;
  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = min(size.width * .4, size.height * .4);
    final edge = Paint()
      ..color = line
      ..strokeWidth = 1.2;
    for (var i = 0; i < neighbors.length; i++) {
      final angle = 2 * pi * i / neighbors.length - pi / 2;
      final p = center + Offset(cos(angle) * radius, sin(angle) * radius);
      canvas.drawLine(center, p, edge);
      canvas.drawCircle(p, 16, Paint()..color = paper);
      canvas.drawCircle(
        p,
        16,
        Paint()
          ..color = line
          ..style = PaintingStyle.stroke,
      );
      _text(canvas, '${neighbors[i]}', p, 11);
    }
    canvas.drawCircle(center, 30, Paint()..color = yellow);
    _text(canvas, '$seed', center, 16);
  }

  void _text(Canvas canvas, String value, Offset p, double size) {
    final painter = TextPainter(
      text: TextSpan(
        text: value,
        style: TextStyle(
          color: ink,
          fontSize: size,
          fontWeight: FontWeight.w600,
        ),
      ),
      textDirection: TextDirection.ltr,
    )..layout();
    painter.paint(canvas, p - Offset(painter.width / 2, painter.height / 2));
  }

  @override
  bool shouldRepaint(_Neighborhood oldDelegate) =>
      oldDelegate.seed != seed ||
      oldDelegate.neighbors.join(',') != neighbors.join(',');
}

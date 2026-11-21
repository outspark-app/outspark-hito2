import 'package:flutter/material.dart';
import '../application/session_controller.dart';
import '../domain/models.dart';
import '../ui/design_system.dart';

class StructuralView extends StatefulWidget {
  const StructuralView({
    super.key,
    required this.session,
    required this.nodeId,
  });
  final SessionController session;
  final int nodeId;
  @override
  State<StructuralView> createState() => _StructuralViewState();
}

class _StructuralViewState extends State<StructuralView> {
  JsonMap? analysis, group;
  String? error, groupError;
  bool loading = true;
  int generation = 0, shown = 10;
  @override
  void initState() {
    super.initState();
    load();
  }

  @override
  void didUpdateWidget(covariant StructuralView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.nodeId != widget.nodeId) {
      load();
    }
  }

  Future<void> load() async {
    final own = ++generation;
    setState(() => loading = true);
    try {
      final summary = await widget.session.repository.structuralAnalysis();
      JsonMap? membership;
      String? membershipError;
      try {
        membership = await widget.session.repository.structuralGroup(
          widget.nodeId,
        );
      } catch (e) {
        membershipError = e.toString();
      }
      if (mounted && own == generation) {
        setState(() {
          analysis = summary;
          group = membership;
          groupError = membershipError;
          error = null;
        });
      }
    } catch (e) {
      if (mounted && own == generation) {
        setState(() => error = e.toString());
      }
    } finally {
      if (mounted && own == generation) {
        setState(() => loading = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      Text(
        'Componentes de la red',
        style: Theme.of(context).textTheme.headlineMedium,
      ),
      const SizedBox(height: 12),
      const Text(
        'Cada componente reúne usuarios unidos por algún camino de amistades. Los círculos temáticos de Outspark se eligen por separado.',
        style: TextStyle(color: muted),
      ),
      const SizedBox(height: 20),
      if (loading)
        const LoadingContent()
      else if (error != null)
        Recovery(message: error!, retry: load)
      else if (analysis != null)
        PaperPanel(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Wrap(
                spacing: 35,
                runSpacing: 20,
                children: [
                  _fact(
                    formatCount(analysis!['groups']),
                    'componentes conexas',
                  ),
                  _fact(formatCount(analysis!['nodes']), 'nodos analizados'),
                ],
              ),
              const SizedBox(height: 18),
              Text(
                analysis!['full_graph'] == true
                    ? 'Grafo de amistades completo. Resultado precalculado y guardado.'
                    : 'Subgrafo piloto: este resultado tiene alcance limitado.',
                style: const TextStyle(color: muted),
              ),
              const SizedBox(height: 20),
              if (group != null)
                Text(
                  'El nodo ${widget.nodeId} pertenece a la componente ${group!['group_id']}, de ${formatCount(group!['group_size'])} nodos, y tiene ${group!['degree']} amistades directas.',
                )
              else
                Text(
                  groupError ?? 'Componente no disponible para este nodo.',
                  style: const TextStyle(color: muted),
                ),
              const SizedBox(height: 26),
              Text(
                'Usuarios con más amistades',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 8),
              const Text(
                'Ordenados por número de vecinos directos. Tener más amistades no demuestra influencia ni que una publicación se haya difundido.',
                style: TextStyle(color: muted, fontSize: 13),
              ),
              const SizedBox(height: 14),
              for (final row in (analysis!['degree_ranking'] as List).take(shown))
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 10),
                  child: Row(
                    children: [
                      SizedBox(
                        width: 100,
                        child: Text(
                          'Nodo ${row['node_id']}',
                          style: const TextStyle(fontWeight: FontWeight.w600),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Text(
                          '${row['degree']} amistades directas',
                          style: const TextStyle(fontSize: 13),
                        ),
                      ),
                    ],
                  ),
                ),
              if ((analysis!['degree_ranking'] as List).length > shown)
                Align(
                  alignment: Alignment.centerLeft,
                  child: TextButton(
                    onPressed: () => setState(() => shown = 20),
                    child: const Text('Ver los primeros 20 usuarios'),
                  ),
                ),
              ExpansionTile(
                tilePadding: EdgeInsets.zero,
                title: const Text('Método y reproducibilidad'),
                children: [
                  SelectableText(
                    'Método: ${analysis!['method']}\nEjecución: ${analysis!['run_id']}\nHash: ${analysis!['source_sha256']}\nTiempo de algoritmo y ranking: ${analysis!['elapsed_seconds']} s\nRecorrido completo: ${analysis!['complete']}\n${analysis!['interpretation']}',
                    style: const TextStyle(color: muted, fontSize: 12),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              const Text(
                'Entre componentes diferentes no hay caminos de amistad. Una componente conexa no demuestra afinidad temática ni constituye una comunidad social detectada.',
                style: TextStyle(color: muted, fontSize: 12),
              ),
            ],
          ),
        ),
    ],
  );
  Widget _fact(String value, String label) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(
        value,
        style: const TextStyle(fontSize: 28, fontWeight: FontWeight.w700),
      ),
      const SizedBox(height: 6),
      Text(label, style: const TextStyle(color: muted, fontSize: 13)),
    ],
  );
}

import 'package:flutter/material.dart';
import '../application/session_controller.dart';
import '../domain/models.dart';
import '../ui/design_system.dart';
import 'conversations.dart';

class ProvenanceView extends StatefulWidget {
  const ProvenanceView({
    super.key,
    required this.session,
    required this.snapshotId,
    required this.publicationId,
    required this.onBack,
    required this.onOriginal,
  });
  final SessionController session;
  final String snapshotId, publicationId;
  final VoidCallback onBack;
  final ValueChanged<Publication> onOriginal;
  @override
  State<ProvenanceView> createState() => _ProvenanceViewState();
}

class _ProvenanceViewState extends State<ProvenanceView> {
  late Future<Provenance> future;
  int selected = 0, shown = 40;
  final _mapKey = GlobalKey(),
      _originKey = GlobalKey(),
      _receiverKey = GlobalKey();
  final _eventKeys = <String, GlobalKey>{};
  List<Rect> _rectangles = [];
  List<({Offset from, Offset to, bool delivery, bool vertical})> _edges = [];
  int _measurement = 0;

  void _measure(List<GlobalKey> eventKeys, bool complete) {
    final generation = ++_measurement;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted || generation != _measurement) return;
      final host = _mapKey.currentContext?.findRenderObject();
      if (host is! RenderBox) return;
      Rect? bounds(GlobalKey key) {
        final box = key.currentContext?.findRenderObject();
        return box is RenderBox && box.hasSize
            ? box.localToGlobal(Offset.zero, ancestor: host) & box.size
            : null;
      }

      final boxes = [
        _originKey,
        ...eventKeys,
        _receiverKey,
      ].map(bounds).toList();
      if (boxes.any((box) => box == null)) return;
      final rectangles = boxes.cast<Rect>();
      if (_rectangles.length == rectangles.length &&
          List.generate(
            rectangles.length,
            (i) => rectangles[i] == _rectangles[i],
          ).every((equal) => equal)) {
        return;
      }
      final edges =
          <({Offset from, Offset to, bool delivery, bool vertical})>[];
      for (var i = 0; i < eventKeys.length; i++) {
        final from = rectangles[i], to = rectangles[i + 1];
        edges.add((
          from: i == 0 ? from.centerRight : from.bottomCenter,
          to: i == 0 ? to.centerLeft : to.topCenter,
          delivery: false,
          vertical: i > 0,
        ));
      }
      if (complete) {
        edges.add((
          from: rectangles[rectangles.length - 2].centerRight,
          to: rectangles.last.centerLeft,
          delivery: true,
          vertical: false,
        ));
      }
      setState(() {
        _rectangles = rectangles;
        _edges = edges;
      });
    });
  }

  @override
  void initState() {
    super.initState();
    future = load();
  }

  Future<Provenance> load() => widget.session.repository.provenance(
    widget.snapshotId,
    widget.publicationId,
  );
  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      Align(
        alignment: Alignment.centerLeft,
        child: TextButton.icon(
          onPressed: widget.onBack,
          icon: const Icon(Icons.arrow_back, size: 18),
          label: const Text('Volver al feed'),
        ),
      ),
      const SizedBox(height: 20),
      const PageHeading(
        '¿Cómo te llegó esta idea?',
        'Un mismo origen. Distintos caminos. Estas son las rutas registradas cuando apareció en tu feed.',
      ),
      FutureBuilder<Provenance>(
        future: future,
        builder: (context, state) {
          if (state.hasError) {
            return Recovery(
              message: state.error.toString(),
              retry: () => setState(() => future = load()),
            );
          }
          if (!state.hasData) return const LoadingContent();
          final data = state.data!;
          if (data.routes.isEmpty) {
            return const PaperPanel(
              child: Text(
                'Este snapshot no tiene rutas disponibles. Regresa y actualiza el feed.',
              ),
            );
          }
          final route = data.routes[selected.clamp(0, data.routes.length - 1)];
          final events = route.events.skip(1).take(shown).toList();
          final origin = Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Padding(
                padding: EdgeInsets.only(bottom: 14),
                child: Text(
                  'Aquí comienza',
                  style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
                ),
              ),
              PublicationCard(
                key: _originKey,
                publication: data.publication,
                showActions: false,
                session: widget.session,
                onComments: () => widget.onOriginal(data.publication),
              ),
            ],
          );
          final steps = Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (events.isEmpty)
                const PaperPanel(
                  child: Text(
                    'Llega directamente desde la publicación original.',
                  ),
                ),
              ...events.asMap().entries.map((entry) {
                final event = entry.value;
                final previous = route.events[entry.key];
                return Padding(
                  padding: const EdgeInsets.only(bottom: 16),
                  child: PaperPanel(
                    key: _eventKeys.putIfAbsent(event.eventId, GlobalKey.new),
                    padding: const EdgeInsets.all(20),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            PersonAvatar(event.actorId),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Text(
                                personName(event.actorId),
                                style: const TextStyle(
                                  fontWeight: FontWeight.w700,
                                  fontSize: 16,
                                ),
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 14),
                        Text(
                          'Republicó desde ${personName(previous.actorId)}',
                          style: const TextStyle(color: muted),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          moment(event.createdAt),
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                      ],
                    ),
                  ),
                );
              }),
              if (route.events.length > shown + 1)
                OutlinedButton(
                  onPressed: () => setState(() => shown += 40),
                  child: const Text('Ver más pasos de esta ruta'),
                ),
            ],
          );
          final receiver = PaperPanel(
            key: _receiverKey,
            color: const Color(0xFFFFF8DC),
            padding: const EdgeInsets.all(22),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                PersonAvatar(widget.session.profile!.uid, size: 52),
                const SizedBox(height: 14),
                Text(
                  widget.session.profile!.name,
                  style: const TextStyle(
                    fontWeight: FontWeight.w700,
                    fontSize: 18,
                  ),
                ),
                const SizedBox(height: 6),
                const Text('En tu feed', style: TextStyle(color: muted)),
                const SizedBox(height: 16),
                ...route.source.reasons.map(
                  (reason) => Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: Text(reason.text),
                  ),
                ),
                const SizedBox(height: 8),
                const Text(
                  'Recibir una idea no te convierte en republicador.',
                  style: TextStyle(fontSize: 12, color: muted),
                ),
              ],
            ),
          );
          return Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Wrap(
                spacing: 10,
                runSpacing: 10,
                children: data.routes.asMap().entries.map((entry) {
                  final route = entry.value;
                  final actor = route.events.last.actorId;
                  return ChoiceChip(
                    label: Text(
                      route.events.length == 1
                          ? 'Desde el origen'
                          : 'Por ${personName(actor)}',
                    ),
                    selected: selected == entry.key,
                    onSelected: (_) => setState(() {
                      selected = entry.key;
                      shown = 40;
                    }),
                  );
                }).toList(),
              ),
              const SizedBox(height: 34),
              LayoutBuilder(
                builder: (context, size) {
                  if (size.maxWidth < 950) {
                    return Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        origin,
                        steps,
                        const Padding(
                          padding: EdgeInsets.symmetric(vertical: 14),
                          child: Icon(Icons.south, color: muted),
                        ),
                        receiver,
                      ],
                    );
                  }
                  _measure(
                    events
                        .map(
                          (event) => _eventKeys.putIfAbsent(
                            event.eventId,
                            GlobalKey.new,
                          ),
                        )
                        .toList(),
                    events.length == route.events.length - 1,
                  );
                  return Stack(
                    key: _mapKey,
                    children: [
                      Positioned.fill(
                        child: IgnorePointer(
                          child: CustomPaint(painter: _Connections(_edges)),
                        ),
                      ),
                      Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Expanded(flex: 5, child: origin),
                          const SizedBox(width: 52),
                          Expanded(
                            flex: 4,
                            child: Padding(
                              padding: const EdgeInsets.only(top: 34),
                              child: steps,
                            ),
                          ),
                          const SizedBox(width: 52),
                          Expanded(
                            flex: 3,
                            child: Padding(
                              padding: const EdgeInsets.only(top: 100),
                              child: receiver,
                            ),
                          ),
                        ],
                      ),
                    ],
                  );
                },
              ),
              const SizedBox(height: 30),
              PaperPanel(
                child: Wrap(
                  alignment: WrapAlignment.spaceBetween,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  spacing: 24,
                  runSpacing: 20,
                  children: [
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          '${data.routes.length} ${data.routes.length == 1 ? 'ruta registrada' : 'rutas registradas'}',
                          style: const TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                        const SizedBox(height: 6),
                        Text(
                          '${data.eventCount} eventos en el árbol del original · recorrido DFS',
                          style: const TextStyle(color: muted, fontSize: 13),
                        ),
                      ],
                    ),
                    FilledButton.icon(
                      onPressed: () => widget.onOriginal(data.publication),
                      icon: const Icon(Icons.north_east, size: 18),
                      label: const Text('Abrir conversación original'),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),
              const Text(
                'La procedencia explica una secuencia registrada. No prueba lectura, acuerdo ni veracidad del contenido.',
                style: TextStyle(color: muted, fontSize: 12),
              ),
            ],
          );
        },
      ),
    ],
  );
}

class _Connections extends CustomPainter {
  const _Connections(this.edges);
  final List<({Offset from, Offset to, bool delivery, bool vertical})> edges;
  @override
  void paint(Canvas canvas, Size size) {
    for (final edge in edges) {
      final paint = Paint()
        ..color = edge.delivery ? muted : const Color(0xFFAD8C23)
        ..strokeWidth = 1.5
        ..style = PaintingStyle.stroke;
      final path = Path()..moveTo(edge.from.dx, edge.from.dy);
      if (edge.vertical) {
        path.lineTo(edge.to.dx, edge.to.dy);
      } else {
        path.cubicTo(
          edge.from.dx + 28,
          edge.from.dy,
          edge.to.dx - 28,
          edge.to.dy,
          edge.to.dx,
          edge.to.dy,
        );
      }
      if (edge.delivery) {
        for (final metric in path.computeMetrics()) {
          for (var at = 0.0; at < metric.length; at += 10) {
            canvas.drawPath(metric.extractPath(at, at + 5), paint);
          }
        }
      } else {
        canvas.drawPath(path, paint);
      }
    }
  }

  @override
  bool shouldRepaint(_Connections oldDelegate) => oldDelegate.edges != edges;
}

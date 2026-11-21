import 'package:flutter/material.dart';
import '../application/session_controller.dart';
import '../data/api_client.dart';
import '../domain/models.dart';
import '../ui/design_system.dart';
import 'conversations.dart';

/// Own originals are independent of the ten cards selected for a feed.
class PublicationHistory extends StatefulWidget {
  const PublicationHistory({
    super.key,
    required this.session,
    required this.onOriginal,
    required this.onCompose,
  });
  final SessionController session;
  final ValueChanged<Publication> onOriginal;
  final VoidCallback onCompose;
  @override
  State<PublicationHistory> createState() => _PublicationHistoryState();
}

class _PublicationHistoryState extends State<PublicationHistory> {
  final posts = <Publication>[];
  final starts = <String?>[null];
  int pageIndex = 0, requestedIndex = 0, unavailable = 0;
  String? cursor, error;
  bool loading = true, lastRestart = true;
  int generation = 0;

  @override
  void initState() {
    super.initState();
    load(restart: true);
  }

  Future<void> load({bool restart = false, int? index}) async {
    final own = ++generation;
    final target = restart ? 0 : (index ?? pageIndex + 1);
    final requested = restart
        ? null
        : (target <= pageIndex ? starts[target] : cursor);
    setState(() {
      loading = true;
      error = null;
      lastRestart = restart;
      requestedIndex = target;
    });
    try {
      final page = await widget.session.repository.myPublications(
        cursor: requested,
      );
      if (!mounted || generation != own) return;
      final next = page.nextCursor;
      if (next != null &&
          (next == requested ||
              (target > pageIndex && starts.take(target + 1).contains(next)))) {
        throw const ApiException(
          code: 'pagination_loop',
          message:
              'No pudimos avanzar en tus publicaciones. Actualiza el historial para empezar de nuevo.',
        );
      }
      setState(() {
        if (restart) starts.clear();
        if (target < starts.length) starts.removeRange(target, starts.length);
        starts.add(requested);
        pageIndex = target;
        unavailable = page.unavailableCount;
        posts.clear();
        posts.addAll(
          {for (final post in page.items) post.publicationId: post}.values,
        );
        cursor = next;
      });
    } catch (failure) {
      if (mounted && generation == own) {
        setState(() => error = failure.toString());
      }
    } finally {
      if (mounted && generation == own) setState(() => loading = false);
    }
  }

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      Wrap(
        alignment: WrapAlignment.spaceBetween,
        crossAxisAlignment: WrapCrossAlignment.center,
        spacing: 20,
        runSpacing: 10,
        children: [
          Text(
            'Tus publicaciones',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          TextButton.icon(
            onPressed: loading ? null : () => load(restart: true),
            icon: const Icon(Icons.refresh, size: 18),
            label: const Text('Actualizar historial'),
          ),
        ],
      ),
      const SizedBox(height: 10),
      const Text(
        'Tus originales, del más reciente al más antiguo. Cada idea conserva su conversación, aunque no aparezca en tu feed.',
        style: TextStyle(color: muted),
      ),
      const SizedBox(height: 20),
      if (loading && posts.isEmpty) const LoadingContent(),
      if (!loading && error == null && posts.isEmpty && unavailable == 0)
        PaperPanel(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                cursor == null
                    ? (pageIndex == 0
                          ? 'Una primera idea abre el camino.'
                          : 'Llegaste al comienzo.')
                    : 'Tu actividad sigue más atrás.',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const SizedBox(height: 10),
              Text(
                cursor == null
                    ? (pageIndex == 0
                          ? 'Todavía no aparecen originales tuyos. Si acabas de publicar, actualiza el historial en unos instantes.'
                          : 'No hay más originales en esta página. Puedes volver a las más recientes.')
                    : 'Esta página contiene republicaciones. Continúa para encontrar tus originales anteriores.',
                style: const TextStyle(color: muted),
              ),
              if (cursor == null && pageIndex == 0) ...[
                const SizedBox(height: 16),
                FilledButton(
                  onPressed: widget.onCompose,
                  child: const Text('Publicar una idea'),
                ),
              ],
            ],
          ),
        ),
      if (unavailable > 0)
        Padding(
          padding: const EdgeInsets.only(bottom: 18),
          child: Text(
            'Hay $unavailable originales sin datos disponibles en esta página. Puedes continuar con las publicaciones anteriores.',
            style: const TextStyle(color: muted),
          ),
        ),
      ...posts.map(
        (p) => PublicationCard(
          publication: p,
          session: widget.session,
          onComments: () => widget.onOriginal(p),
        ),
      ),
      if (loading && posts.isNotEmpty) const LinearProgressIndicator(),
      if (error != null)
        Recovery(
          message: error!,
          retry: () => load(restart: lastRestart, index: requestedIndex),
        ),
      if (!loading && error == null)
        Padding(
          padding: const EdgeInsets.only(top: 16),
          child: Wrap(
            spacing: 12,
            runSpacing: 12,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              if (pageIndex > 0)
                OutlinedButton(
                  onPressed: () => load(index: pageIndex - 1),
                  child: const Text('Más recientes'),
                ),
              if (cursor != null)
                OutlinedButton(
                  onPressed: () => load(),
                  child: const Text('Publicaciones anteriores'),
                ),
              if (pageIndex > 0 || cursor != null)
                Text(
                  'Página ${pageIndex + 1}',
                  style: const TextStyle(color: muted, fontSize: 12),
                ),
            ],
          ),
        ),
      if (!loading && error == null && posts.isNotEmpty && cursor == null)
        const Text(
          'Llegaste al comienzo de tus publicaciones.',
          style: TextStyle(color: muted, fontSize: 12),
        ),
    ],
  );
}

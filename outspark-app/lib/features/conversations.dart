import 'dart:math';
import 'package:flutter/material.dart';
import '../application/session_controller.dart';
import '../domain/models.dart';
import '../ui/design_system.dart';
import 'diffusion_simulator.dart';

String operationKey() =>
    'flutter-${DateTime.now().microsecondsSinceEpoch}-${Random.secure().nextInt(0x7fffffff)}';

class PublicationCard extends StatelessWidget {
  const PublicationCard({
    super.key,
    required this.publication,
    required this.session,
    this.card,
    this.onRoute,
    required this.onComments,
    this.onRepost,
    this.showActions = true,
  });
  final bool showActions;
  final Publication publication;
  final SessionController session;
  final FeedCard? card;
  final VoidCallback? onRoute, onRepost;
  final VoidCallback onComments;
  @override
  Widget build(BuildContext context) {
    final removed = publication.status != 'ACTIVE';
    final canSimulate =
        !removed && publication.authorId == session.profile?.uid;
    final actors =
        card?.sources
            .expand((s) => s.reasons)
            .where((r) => r.type == 'contact')
            .map((r) => personName(r.contactId ?? ''))
            .toSet()
            .toList() ??
        [];
    final own =
        publication.authorId == session.profile?.uid ||
        (card?.sources.any((s) => s.reasons.any((r) => r.type == 'own')) ??
            false);
    return Padding(
      padding: const EdgeInsets.only(bottom: 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (actors.isNotEmpty)
            Padding(
              padding: const EdgeInsets.fromLTRB(8, 0, 8, 10),
              child: Row(
                children: [
                  const Icon(Icons.repeat_rounded, size: 18, color: muted),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      '${actors.join(' y ')} ${actors.length == 1 ? 'acercó' : 'acercaron'} esta idea a tu círculo',
                      style: const TextStyle(color: muted, fontSize: 13),
                    ),
                  ),
                ],
              ),
            ),
          PaperPanel(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    PersonAvatar(publication.authorId),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            personName(publication.authorId),
                            style: const TextStyle(
                              fontWeight: FontWeight.w700,
                              fontSize: 16,
                            ),
                          ),
                          Text(
                            'en ${session.communityName(publication.communityId)}',
                            style: const TextStyle(color: muted, fontSize: 13),
                          ),
                          Text(
                            moment(publication.createdAt),
                            style: Theme.of(context).textTheme.bodySmall,
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 22),
                ReadableText(
                  removed ? 'Publicación retirada' : publication.body ?? '',
                  style: TextStyle(
                    fontSize: 18,
                    height: 1.55,
                    color: removed ? muted : ink,
                  ),
                ),
                const SizedBox(height: 18),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: publication.topicIds
                      .map(
                        (id) => Text(
                          '#${session.topicName(id)}',
                          style: const TextStyle(color: muted, fontSize: 13),
                        ),
                      )
                      .toList(),
                ),
                if (showActions || canSimulate) ...[
                  const SizedBox(height: 20),
                  const Divider(height: 1),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 8,
                    runSpacing: 4,
                    children: [
                      if (showActions)
                        TextButton.icon(
                          onPressed: removed ? null : onComments,
                          icon: const Icon(Icons.chat_bubble_outline, size: 19),
                          label: const Text('Conversar'),
                        ),
                      if (showActions)
                        TextButton.icon(
                          onPressed: removed || own ? null : onRepost,
                          icon: const Icon(Icons.repeat_rounded, size: 20),
                          label: Text(own ? 'En tu recorrido' : 'Republicar'),
                        ),
                      if (canSimulate)
                        TextButton.icon(
                          onPressed: () => Navigator.of(context).push(
                            MaterialPageRoute<void>(
                              builder: (_) => DiffusionSimulator(
                                session: session,
                                publication: publication,
                              ),
                            ),
                          ),
                          icon: const Icon(Icons.hub_outlined, size: 19),
                          label: const Text('Simular difusión'),
                        ),
                    ],
                  ),
                ],
              ],
            ),
          ),
          if (onRoute != null)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: TextButton(
                onPressed: onRoute,
                child: Row(
                  children: [
                    const Icon(Icons.route_outlined, size: 21),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        'Cómo llegó a mí · ${card?.sources.length ?? 0} ${(card?.sources.length ?? 0) == 1 ? 'ruta' : 'rutas'}',
                        style: const TextStyle(fontWeight: FontWeight.w600),
                      ),
                    ),
                    const Icon(Icons.north_east, size: 18),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class ComposeDraft {
  String text = '';
  String? community;
  Set<String> topics = {};
  String? key, signature;
  String keyForPayload() {
    final next = '$community|${topics.toList()..sort()}|${text.trim()}';
    if (signature != next) {
      signature = next;
      key = operationKey();
    }
    return key ??= operationKey();
  }

  void clear() {
    text = '';
    topics = {};
    key = null;
    signature = null;
  }
}

class ComposeView extends StatefulWidget {
  const ComposeView({
    super.key,
    required this.session,
    required this.draft,
    required this.onPublished,
    required this.onCommunities,
  });
  final SessionController session;
  final ComposeDraft draft;
  final ValueChanged<CreatedPublication> onPublished;
  final VoidCallback onCommunities;
  @override
  State<ComposeView> createState() => _ComposeViewState();
}

class _ComposeViewState extends State<ComposeView> {
  late final TextEditingController text;
  bool sending = false;
  String? error;
  @override
  void initState() {
    super.initState();
    text = TextEditingController(text: widget.draft.text);
  }

  @override
  void dispose() {
    text.dispose();
    super.dispose();
  }

  Future<void> publish() async {
    final draft = widget.draft;
    setState(() => sending = true);
    try {
      final result = await widget.session.repository.createPublication(
        draft.community!,
        text.text.trim(),
        draft.topics.toList(),
        idempotencyKey: draft.keyForPayload(),
      );
      draft.clear();
      if (mounted) widget.onPublished(result);
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    } finally {
      if (mounted) setState(() => sending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final session = widget.session, draft = widget.draft;
    final choices = session.communities
        .where((c) => session.memberships.contains(c.id))
        .toList();
    if (!choices.any((c) => c.id == draft.community)) {
      draft.community = choices.firstOrNull?.id;
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const PageHeading(
          'Dale un comienzo a tu idea.',
          'La conversación queda en su origen. Los demás pueden abrir nuevos caminos.',
        ),
        if (choices.isEmpty)
          PaperPanel(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Elige primero una comunidad',
                  style: TextStyle(fontSize: 22, fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 12),
                const Text(
                  'Únete a un círculo para publicar allí. Puedes salir cuando quieras.',
                ),
                const SizedBox(height: 20),
                FilledButton(
                  onPressed: widget.onCommunities,
                  child: const Text('Explorar comunidades'),
                ),
              ],
            ),
          )
        else
          ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 780),
            child: PaperPanel(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Row(
                    children: [
                      PersonAvatar(session.profile!.uid),
                      const SizedBox(width: 12),
                      Text(
                        session.profile!.name,
                        style: const TextStyle(fontWeight: FontWeight.w700),
                      ),
                      const Spacer(),
                      const Text(
                        'Publicación pública',
                        style: TextStyle(color: muted, fontSize: 13),
                      ),
                    ],
                  ),
                  const SizedBox(height: 26),
                  DropdownButtonFormField<String>(
                    initialValue: draft.community,
                    decoration: const InputDecoration(labelText: 'Comunidad'),
                    items: choices
                        .map(
                          (c) => DropdownMenuItem(
                            value: c.id,
                            child: Text(c.name),
                          ),
                        )
                        .toList(),
                    onChanged: sending
                        ? null
                        : (id) => setState(() => draft.community = id),
                  ),
                  const SizedBox(height: 22),
                  TextField(
                    controller: text,
                    enabled: !sending,
                    maxLength: 1000,
                    minLines: 6,
                    maxLines: 12,
                    decoration: const InputDecoration(
                      labelText: '¿Qué quieres compartir?',
                      hintText:
                          'Una pregunta, una idea o algo que descubriste…',
                    ),
                    onChanged: (value) => setState(() => draft.text = value),
                  ),
                  const SizedBox(height: 18),
                  const Text(
                    'Temas · elige de 1 a 3',
                    style: TextStyle(fontWeight: FontWeight.w600),
                  ),
                  const SizedBox(height: 10),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: session.topics
                        .map(
                          (t) => FilterChip(
                            label: Text(t.name),
                            selected: draft.topics.contains(t.id),
                            onSelected:
                                sending ||
                                    (!draft.topics.contains(t.id) &&
                                        draft.topics.length >= 3)
                                ? null
                                : (selected) => setState(
                                    () => selected
                                        ? draft.topics.add(t.id)
                                        : draft.topics.remove(t.id),
                                  ),
                          ),
                        )
                        .toList(),
                  ),
                  const SizedBox(height: 22),
                  const Text(
                    'El borrador se conserva al cambiar de pantalla o cuenta. Se pierde al recargar.',
                    style: TextStyle(color: muted, fontSize: 12),
                  ),
                  if (error != null)
                    Padding(
                      padding: const EdgeInsets.only(top: 16),
                      child: Text(
                        error!,
                        style: TextStyle(
                          color: Theme.of(context).colorScheme.error,
                        ),
                      ),
                    ),
                  const SizedBox(height: 22),
                  Align(
                    alignment: Alignment.centerRight,
                    child: FilledButton.icon(
                      onPressed:
                          sending ||
                              text.text.trim().isEmpty ||
                              draft.topics.isEmpty
                          ? null
                          : publish,
                      icon: Icon(
                        sending ? Icons.hourglass_top : Icons.north_east,
                        size: 18,
                      ),
                      label: Text(sending ? 'Publicando…' : 'Publicar'),
                    ),
                  ),
                ],
              ),
            ),
          ),
      ],
    );
  }
}

class ConversationView extends StatefulWidget {
  const ConversationView({
    super.key,
    required this.publication,
    required this.session,
    required this.onBack,
    required this.onRetired,
  });
  final Publication publication;
  final SessionController session;
  final VoidCallback onBack;
  final ValueChanged<Publication> onRetired;
  @override
  State<ConversationView> createState() => _ConversationViewState();
}

class _ConversationViewState extends State<ConversationView> {
  final text = TextEditingController();
  final comments = <Comment>[];
  Publication? current;
  bool loading = true, sending = false, retiring = false;
  String? cursor, error, key, keyText;
  @override
  void initState() {
    super.initState();
    load();
  }

  @override
  void dispose() {
    text.dispose();
    super.dispose();
  }

  Future<void> load() async {
    setState(() => loading = true);
    try {
      final original = await widget.session.repository.getPublication(
        widget.publication.publicationId,
      );
      if (!mounted) return;
      setState(() => current = original);
      if (original.status != 'ACTIVE') {
        setState(() {
          comments.clear();
          cursor = null;
        });
        return;
      }
      final page = await widget.session.repository.comments(
        widget.publication.publicationId,
        cursor: cursor,
      );
      if (mounted) {
        setState(() {
          comments.addAll(
            page.items.where(
              (c) => !comments.any((old) => old.commentId == c.commentId),
            ),
          );
          cursor = page.nextCursor;
          error = null;
        });
      }
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<void> send() async {
    final body = text.text.trim();
    if (body.isEmpty) return;
    if (keyText != body) {
      key = operationKey();
      keyText = body;
    }
    setState(() => sending = true);
    try {
      final result = await widget.session.repository.addComment(
        widget.publication.publicationId,
        body,
        idempotencyKey: key!,
      );
      if (mounted) {
        setState(() {
          if (!comments.any((c) => c.commentId == result.commentId)) {
            comments.add(result);
          }
          text.clear();
          key = null;
          keyText = null;
          error = null;
        });
      }
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    } finally {
      if (mounted) setState(() => sending = false);
    }
  }

  Future<void> retire() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialog) => AlertDialog(
        title: const Text('¿Retirar esta publicación?'),
        content: const Text(
          'El texto y los comentarios dejarán de mostrarse en todos los recorridos. Se conservará la estructura de las republicaciones. Esta acción no se puede deshacer.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialog, false),
            child: const Text('Cancelar'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(dialog, true),
            child: const Text('Retirar publicación'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    setState(() {
      retiring = true;
      error = null;
    });
    try {
      final removed = await widget.session.repository.retirePublication(
        widget.publication.publicationId,
      );
      if (mounted) {
        setState(() {
          current = removed;
          comments.clear();
          cursor = null;
        });
      }
      widget.onRetired(removed);
    } catch (failure) {
      if (mounted) setState(() => error = failure.toString());
    } finally {
      if (mounted) setState(() => retiring = false);
    }
  }

  @override
  Widget build(BuildContext context) => ConstrainedBox(
    constraints: const BoxConstraints(maxWidth: 760),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Align(
          alignment: Alignment.centerLeft,
          child: TextButton.icon(
            onPressed: widget.onBack,
            icon: const Icon(Icons.arrow_back, size: 18),
            label: const Text('Volver'),
          ),
        ),
        const SizedBox(height: 16),
        const PageHeading(
          'Una conversación compartida.',
          'Cada republicación conserva este original y sus comentarios.',
        ),
        if (current != null)
          PublicationCard(
            publication: current!,
            showActions: false,
            session: widget.session,
            onComments: () {},
          ),
        if (current?.status == 'ACTIVE' &&
            current?.authorId == widget.session.profile?.uid)
          Align(
            alignment: Alignment.centerRight,
            child: TextButton.icon(
              onPressed: retiring || sending || loading ? null : retire,
              icon: const Icon(Icons.remove_circle_outline, size: 18),
              label: Text(retiring ? 'Retirando…' : 'Retirar publicación'),
              style: TextButton.styleFrom(
                foregroundColor: Theme.of(context).colorScheme.error,
              ),
            ),
          ),
        if (loading && comments.isEmpty) const LoadingContent(),
        if (!loading && comments.isEmpty && current?.status == 'ACTIVE')
          const Padding(
            padding: EdgeInsets.only(bottom: 20),
            child: Text('Todavía no hay comentarios. Abre la conversación.'),
          ),
        ...comments.map(
          (c) => Padding(
            padding: const EdgeInsets.only(bottom: 20),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                PersonAvatar(c.authorId, size: 34),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        personName(c.authorId),
                        style: const TextStyle(fontWeight: FontWeight.w700),
                      ),
                      ReadableText(c.body),
                      Text(
                        moment(c.createdAt),
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
        if (cursor != null)
          OutlinedButton(
            onPressed: loading ? null : load,
            child: Text(loading ? 'Cargando…' : 'Ver más comentarios'),
          ),
        if (error != null)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 12),
            child: Text(
              error!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          ),
        if (current?.status == 'ACTIVE')
          PaperPanel(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                TextField(
                  controller: text,
                  enabled: !sending && !retiring,
                  maxLength: 1000,
                  minLines: 3,
                  maxLines: 6,
                  decoration: const InputDecoration(labelText: 'Tu comentario'),
                  onChanged: (_) => setState(() {}),
                ),
                const SizedBox(height: 12),
                Align(
                  alignment: Alignment.centerRight,
                  child: FilledButton(
                    onPressed: sending || retiring || text.text.trim().isEmpty
                        ? null
                        : send,
                    child: Text(sending ? 'Enviando…' : 'Comentar'),
                  ),
                ),
              ],
            ),
          ),
      ],
    ),
  );
}

Future<bool> confirmRepost(
  BuildContext context,
  SessionController session,
  FeedCard card, {
  required Map<String, String> sourceActors,
}) async {
  String? selected = card.sources.length == 1
      ? card.sources.first.eventId
      : null;
  String? error;
  bool sending = false;
  final keys = <String, String>{};
  return await showDialog<bool>(
        context: context,
        barrierDismissible: false,
        builder: (dialog) => StatefulBuilder(
          builder: (context, setDialog) => PopScope(
            canPop: !sending,
            child: AlertDialog(
              title: const Text('Haz que la idea siga'),
              content: SizedBox(
                width: 460,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Compartes el original de ${personName(card.publication.authorId)}. Su texto y conversación se conservan.',
                    ),
                    const SizedBox(height: 20),
                    ...card.sources.map(
                      (s) => Padding(
                        padding: const EdgeInsets.only(bottom: 8),
                        child: OutlinedButton(
                          onPressed: sending
                              ? null
                              : () => setDialog(() => selected = s.eventId),
                          style: OutlinedButton.styleFrom(
                            backgroundColor: selected == s.eventId
                                ? yellow.withValues(alpha: .35)
                                : null,
                          ),
                          child: Padding(
                            padding: const EdgeInsets.symmetric(vertical: 10),
                            child: Row(
                              children: [
                                Icon(
                                  selected == s.eventId
                                      ? Icons.radio_button_checked
                                      : Icons.radio_button_off,
                                  size: 20,
                                ),
                                const SizedBox(width: 10),
                                Expanded(
                                  child: Text(
                                    'Desde ${personName(sourceActors[s.eventId]!)}',
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                      ),
                    ),
                    if (error != null)
                      Text(
                        error!,
                        style: TextStyle(
                          color: Theme.of(context).colorScheme.error,
                        ),
                      ),
                  ],
                ),
              ),
              actions: [
                TextButton(
                  onPressed: sending
                      ? null
                      : () => Navigator.pop(dialog, false),
                  child: const Text('Cancelar'),
                ),
                FilledButton(
                  onPressed: sending || selected == null
                      ? null
                      : () async {
                          setDialog(() => sending = true);
                          try {
                            await session.repository.repost(
                              selected!,
                              idempotencyKey: keys.putIfAbsent(
                                selected!,
                                operationKey,
                              ),
                            );
                            if (dialog.mounted) Navigator.pop(dialog, true);
                          } catch (e) {
                            if (dialog.mounted) {
                              setDialog(() {
                                error = e.toString();
                                sending = false;
                              });
                            }
                          }
                        },
                  child: Text(sending ? 'Republicando…' : 'Republicar'),
                ),
              ],
            ),
          ),
        ),
      ) ??
      false;
}

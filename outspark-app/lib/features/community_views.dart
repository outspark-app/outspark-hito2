import 'package:flutter/material.dart';
import '../application/session_controller.dart';
import '../data/api_client.dart';
import '../domain/models.dart';
import 'publication_history.dart';
import '../ui/design_system.dart';

class CommunitiesView extends StatefulWidget {
  const CommunitiesView({
    super.key,
    required this.session,
    required this.onChanged,
    required this.onCompose,
  });
  final SessionController session;
  final ValueChanged<String> onChanged;
  final VoidCallback onCompose;
  @override
  State<CommunitiesView> createState() => _CommunitiesViewState();
}

class _CommunitiesViewState extends State<CommunitiesView> {
  String? busy, error;
  Future<void> change(String id, bool joined) async {
    setState(() => busy = id);
    try {
      if (joined) {
        await widget.session.repository.leaveCommunity(id);
      } else {
        await widget.session.repository.joinCommunity(id);
      }
      await widget.session.refresh();
      if (mounted) {
        widget.onChanged(
          joined
              ? 'Saliste de la comunidad.'
              : 'Ahora formas parte de este círculo.',
        );
      }
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    } finally {
      if (mounted) setState(() => busy = null);
    }
  }

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      const PageHeading(
        'Cada círculo abre una conversación.',
        'Elige dónde participar. Tus comunidades son una elección tuya, no una inferencia del histórico.',
      ),
      if (error != null)
        Padding(
          padding: const EdgeInsets.only(bottom: 16),
          child: Text(
            error!,
            style: TextStyle(color: Theme.of(context).colorScheme.error),
          ),
        ),
      ...widget.session.communities.asMap().entries.map((entry) {
        final c = entry.value;
        final joined = widget.session.memberships.contains(c.id);
        final description =
            const {
              'diseno': 'Ideas para pensar y habitar las cosas de otra manera.',
              'tecnologia':
                  'Lo que construimos y las preguntas que aparecen en el camino.',
              'sostenibilidad':
                  'Pequeñas decisiones para los lugares que compartimos.',
            }[c.id] ??
            'Un espacio para compartir ideas y escuchar otras perspectivas.';
        return Padding(
          padding: const EdgeInsets.only(bottom: 20),
          child: PaperPanel(
            child: LayoutBuilder(
              builder: (context, size) {
                final content = Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(
                      const [
                        Icons.interests_outlined,
                        Icons.hub_outlined,
                        Icons.eco_outlined,
                      ][entry.key % 3],
                      size: 36,
                    ),
                    const SizedBox(height: 20),
                    Text(
                      c.name,
                      style: Theme.of(context).textTheme.headlineMedium,
                    ),
                    const SizedBox(height: 10),
                    Text(description, style: const TextStyle(color: muted)),
                    const SizedBox(height: 10),
                    const Text(
                      'Comunidad de demostración',
                      style: TextStyle(fontSize: 12, color: muted),
                    ),
                  ],
                );
                final action = Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (joined)
                      const Padding(
                        padding: EdgeInsets.only(bottom: 10),
                        child: Text(
                          'Ya formas parte',
                          style: TextStyle(fontWeight: FontWeight.w600),
                        ),
                      ),
                    if (joined)
                      OutlinedButton(
                        onPressed: busy != null
                            ? null
                            : () => change(c.id, true),
                        child: Text(
                          busy == c.id
                              ? 'Actualizando…'
                              : 'Salir de la comunidad',
                        ),
                      )
                    else
                      FilledButton.icon(
                        onPressed: busy != null
                            ? null
                            : () => change(c.id, false),
                        icon: const Icon(Icons.add, size: 18),
                        label: Text(
                          busy == c.id ? 'Uniéndote…' : 'Unirme a este círculo',
                        ),
                      ),
                    if (joined)
                      TextButton(
                        onPressed: widget.onCompose,
                        child: const Text('Compartir una idea'),
                      ),
                  ],
                );
                return size.maxWidth > 650
                    ? Row(
                        children: [
                          Expanded(child: content),
                          const SizedBox(width: 40),
                          action,
                        ],
                      )
                    : Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [content, const SizedBox(height: 24), action],
                      );
              },
            ),
          ),
        );
      }),
    ],
  );
}

class ProfileView extends StatefulWidget {
  const ProfileView({
    super.key,
    required this.session,
    required this.onChanged,
    required this.onOriginal,
    required this.onCompose,
  });
  final SessionController session;
  final ValueChanged<String> onChanged;
  final ValueChanged<Publication> onOriginal;
  final VoidCallback onCompose;
  @override
  State<ProfileView> createState() => _ProfileViewState();
}

class _ProfileViewState extends State<ProfileView> {
  late Set<String> topics;
  late int version;
  bool saving = false;
  String? error;
  @override
  void initState() {
    super.initState();
    topics = widget.session.profile!.topicIds.toSet();
    version = widget.session.profile!.preferencesVersion;
  }

  Future<void> save() async {
    setState(() {
      saving = true;
      error = null;
    });
    try {
      await widget.session.repository.savePreferences(topics.toList(), version);
      await widget.session.refresh();
      if (mounted) {
        version = widget.session.profile!.preferencesVersion;
        widget.onChanged('Tus temas quedaron guardados.');
      }
    } on ApiException catch (e) {
      if (e.statusCode == 409) {
        try {
          final latest = await widget.session.repository.loadProfile();
          if (mounted) {
            setState(() {
              version = latest.preferencesVersion;
              error =
                  'Los temas cambiaron en otra pestaña. Conservamos tu selección; revísala y vuelve a guardar si quieres reemplazarlos.';
            });
          }
        } catch (failure) {
          if (mounted) setState(() => error = failure.toString());
        }
      } else if (mounted) {
        setState(() => error = e.toString());
      }
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    } finally {
      if (mounted) setState(() => saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final p = widget.session.profile!;
    return ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 850),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              PersonAvatar(p.uid, size: 72),
              const SizedBox(width: 20),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      p.name,
                      style: Theme.of(context).textTheme.headlineLarge,
                    ),
                    const SizedBox(height: 6),
                    Text(
                      p.uid.startsWith('fb-')
                          ? 'Cuenta de simulación del histórico'
                          : 'Cuenta ficticia de demostración',
                      style: const TextStyle(color: muted),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 36),
          PaperPanel(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Lo que te interesa',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                const SizedBox(height: 12),
                const Text(
                  'Elige hasta tres temas. El feed diverso usa lo que declaras aquí, junto con la recencia y la variedad de comunidades.',
                  style: TextStyle(color: muted),
                ),
                const SizedBox(height: 20),
                Wrap(
                  spacing: 10,
                  runSpacing: 10,
                  children: widget.session.topics
                      .map(
                        (t) => FilterChip(
                          label: Text(t.name),
                          selected: topics.contains(t.id),
                          onSelected:
                              saving ||
                                  (!topics.contains(t.id) && topics.length >= 3)
                              ? null
                              : (selected) => setState(
                                  () => selected
                                      ? topics.add(t.id)
                                      : topics.remove(t.id),
                                ),
                        ),
                      )
                      .toList(),
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
                const SizedBox(height: 24),
                FilledButton(
                  onPressed: saving ? null : save,
                  child: Text(saving ? 'Guardando…' : 'Guardar mis temas'),
                ),
              ],
            ),
          ),
          const SizedBox(height: 28),
          PublicationHistory(
            session: widget.session,
            onOriginal: widget.onOriginal,
            onCompose: widget.onCompose,
          ),
          const SizedBox(height: 28),
          Text(
            'Tus comunidades',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 14),
          Text(
            widget.session.memberships.isEmpty
                ? 'Todavía no formas parte de una comunidad.'
                : widget.session.memberships
                      .map(widget.session.communityName)
                      .join(', '),
          ),
          const SizedBox(height: 28),
          Text('Tus conexiones', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 14),
          if (widget.session.contacts.isEmpty)
            const Text('Esta cuenta todavía no tiene contactos.')
          else
            Wrap(
              spacing: 10,
              runSpacing: 10,
              children: widget.session.contacts
                  .take(50)
                  .map(
                    (id) => Chip(
                      avatar: PersonAvatar(id, size: 28),
                      label: Text(personName(id)),
                    ),
                  )
                  .toList(),
            ),
          if (widget.session.contacts.length > 50)
            Text(
              'Se muestran 50 de ${widget.session.contacts.length} contactos.',
              style: const TextStyle(color: muted, fontSize: 12),
            ),
        ],
      ),
    );
  }
}

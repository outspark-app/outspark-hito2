import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'application/session_controller.dart';
import 'data/api_client.dart';
import 'data/outspark_repository.dart';
import 'domain/models.dart';
import 'features/conversations.dart';
import 'features/community_views.dart';
import 'features/firebase_sign_in.dart';
import 'features/network_view.dart';
import 'features/provenance_view.dart';
import 'ui/design_system.dart';
import 'ui/browser.dart';

class OutsparkApp extends StatelessWidget {
  const OutsparkApp({
    super.key,
    required this.apiBaseUrl,
    required this.demoMode,
    required this.landingUrl,
    this.firebaseEnabled = false,
  });
  final String apiBaseUrl, landingUrl;
  final bool demoMode, firebaseEnabled;
  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'Outspark',
    locale: const Locale('es', 'PE'),
    supportedLocales: const [Locale('es', 'PE'), Locale('es')],
    localizationsDelegates: const [
      GlobalMaterialLocalizations.delegate,
      GlobalWidgetsLocalizations.delegate,
      GlobalCupertinoLocalizations.delegate,
    ],
    debugShowCheckedModeBanner: false,
    theme: outsparkTheme(),
    home: _AccountHost(
      apiBaseUrl: apiBaseUrl,
      demoMode: demoMode,
      firebaseEnabled: firebaseEnabled,
      landingUrl: landingUrl,
    ),
  );
}

class _AccountHost extends StatefulWidget {
  const _AccountHost({
    required this.apiBaseUrl,
    required this.demoMode,
    required this.firebaseEnabled,
    required this.landingUrl,
  });
  final String apiBaseUrl, landingUrl;
  final bool demoMode, firebaseEnabled;
  @override
  State<_AccountHost> createState() => _AccountHostState();
}

class _AccountHostState extends State<_AccountHost> {
  late String actor;
  late final Stream<User?> identities = FirebaseAuth.instance
      .authStateChanges();
  final drafts = <String, ComposeDraft>{};
  @override
  void initState() {
    super.initState();
    final stored = readSession('outspark.demoUser');
    actor =
        stored != null &&
            RegExp(r'^(ana|bruno|carla|diego|elena|fb-\d+)$').hasMatch(stored)
        ? stored
        : 'diego';
  }

  @override
  Widget build(BuildContext context) {
    if (widget.firebaseEnabled) {
      return StreamBuilder<User?>(
        stream: identities,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Scaffold(
              body: Center(child: CircularProgressIndicator()),
            );
          }
          final user = snapshot.data;
          if (user == null) return const FirebaseSignIn();
          return _Workspace(
            key: ValueKey(user.uid),
            actor: user.uid,
            apiBaseUrl: widget.apiBaseUrl,
            landingUrl: widget.landingUrl,
            draft: drafts.putIfAbsent(user.uid, ComposeDraft.new),
            onAccount: (_) {},
            firebaseUser: user,
          );
        },
      );
    }
    if (!widget.demoMode) {
      return Scaffold(
        body: Center(
          child: ConstrainedBox(
            constraints: BoxConstraints(maxWidth: 520),
            child: Padding(
              padding: EdgeInsets.all(28),
              child: PaperPanel(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Brand(),
                    SizedBox(height: 28),
                    Text(
                      'El acceso a esta instalación aún no está configurado.',
                      style: TextStyle(
                        fontSize: 24,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    SizedBox(height: 14),
                    Text(
                      'La demostración local utiliza cuentas ficticias. El acceso público estará disponible cuando se complete la configuración de identidad del proyecto.',
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      );
    }
    return _Workspace(
      key: ValueKey(actor),
      actor: actor,
      apiBaseUrl: widget.apiBaseUrl,
      landingUrl: widget.landingUrl,
      draft: drafts.putIfAbsent(actor, ComposeDraft.new),
      onAccount: (id) {
        writeSession('outspark.demoUser', id);
        setState(() => actor = id);
      },
    );
  }
}

class _Workspace extends StatefulWidget {
  const _Workspace({
    super.key,
    required this.actor,
    required this.apiBaseUrl,
    required this.landingUrl,
    required this.draft,
    required this.onAccount,
    this.firebaseUser,
  });
  final String actor, apiBaseUrl, landingUrl;
  final ComposeDraft draft;
  final ValueChanged<String> onAccount;
  final User? firebaseUser;
  @override
  State<_Workspace> createState() => _WorkspaceState();
}

class _WorkspaceState extends State<_Workspace> {
  late final ApiClient client;
  late final SessionController session;
  final scroll = ScrollController();
  int page =
      {
        'red': 4,
        'comunidades': 2,
        'perfil': 3,
        'descubrir': 1,
      }[Uri.base.queryParameters['view']] ??
      0;
  int lastDestination = 0;
  bool comparing = false;
  String strategy = 'chronological';
  Publication? conversation, newPublication;
  ({String snapshot, String publication})? route;
  static const destinations = [
    'Inicio',
    'Descubrir',
    'Comunidades',
    'Perfil',
    'Explorar red',
  ];
  static const icons = [
    Icons.circle_outlined,
    Icons.explore_outlined,
    Icons.people_outline,
    Icons.person_outline,
    Icons.hub_outlined,
  ];
  @override
  void initState() {
    super.initState();
    client = ApiClient(
      baseUrl: Uri.base.resolve(widget.apiBaseUrl),
      demoUser: widget.firebaseUser == null ? widget.actor : null,
      tokenProvider: widget.firebaseUser?.getIdToken,
    );
    session = SessionController(OutsparkRepository(client));
    session.refresh();
  }

  @override
  void dispose() {
    session.dispose();
    client.close();
    scroll.dispose();
    super.dispose();
  }

  void navigate(int next) {
    setState(() {
      page = next;
      if (next < 5) lastDestination = next;
      route = null;
      conversation = null;
    });
    if (scroll.hasClients) scroll.jumpTo(0);
  }

  void notify(String message) {
    if (mounted) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(message)));
    }
  }

  Future<void> compare() async {
    setState(() => comparing = true);
    try {
      await session.compare();
    } catch (e) {
      notify(e.toString());
    } finally {
      if (mounted) setState(() => comparing = false);
    }
  }

  Future<void> repost(FeedCard card, FeedSnapshot snapshot) async {
    try {
      final provenance = await session.repository.provenance(
        snapshot.snapshotId,
        card.publication.publicationId,
      );
      if (!mounted) return;
      final actors = {
        for (final route in provenance.routes)
          route.source.eventId: route.events.last.actorId,
      };
      if (card.sources.any((source) => !actors.containsKey(source.eventId))) {
        notify(
          'No pudimos identificar todas las fuentes. Actualiza el feed y vuelve a intentar.',
        );
        return;
      }
      if (await confirmRepost(context, session, card, sourceActors: actors)) {
        if (!mounted) return;
        notify('Republicaste esta publicación. Su origen se conserva.');
        await session.refresh();
      }
    } catch (error) {
      notify(error.toString());
    }
  }

  void openConversation(Publication p) {
    setState(() {
      conversation = p;
      route = null;
    });
    if (scroll.hasClients) scroll.jumpTo(0);
  }

  Widget card(FeedCard card, FeedSnapshot snapshot) => PublicationCard(
    publication: card.publication,
    card: card,
    session: session,
    onComments: () => openConversation(card.publication),
    onRepost: () => repost(card, snapshot),
    onRoute: () {
      setState(
        () => route = (
          snapshot: snapshot.snapshotId,
          publication: card.publication.publicationId,
        ),
      );
      if (scroll.hasClients) scroll.jumpTo(0);
    },
  );

  Widget feed(bool discover) {
    final comparison = session.comparison;
    final snapshot = comparison == null
        ? session.feed!
        : (strategy == 'diverse'
              ? comparison.diverse
              : comparison.chronological);
    final center = Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Wrap(
          alignment: WrapAlignment.spaceBetween,
          crossAxisAlignment: WrapCrossAlignment.center,
          runSpacing: 14,
          spacing: 16,
          children: [
            Text(
              discover ? 'Otros caminos, nuevas ideas.' : 'Conversaciones',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            SegmentedButton<String>(
              segments: const [
                ButtonSegment(value: 'chronological', label: Text('Reciente')),
                ButtonSegment(value: 'diverse', label: Text('Diverso')),
              ],
              selected: {comparison == null ? 'chronological' : strategy},
              onSelectionChanged: comparing || session.loading
                  ? null
                  : (values) async {
                      if (session.comparison == null) await compare();
                      if (mounted && session.comparison != null) {
                        setState(() => strategy = values.first);
                      }
                    },
            ),
          ],
        ),
        const SizedBox(height: 20),
        if (discover)
          Padding(
            padding: const EdgeInsets.only(bottom: 20),
            child: Text(
              'La selección diversa combina tus temas, recencia y comunidades distintas. Cada sugerencia conserva su explicación.',
              style: const TextStyle(color: muted),
            ),
          ),
        if (comparing)
          const Padding(
            padding: EdgeInsets.only(bottom: 18),
            child: LinearProgressIndicator(),
          ),
        if (newPublication != null &&
            !snapshot.cards.any(
              (c) =>
                  c.publication.publicationId == newPublication!.publicationId,
            )) ...[
          const Padding(
            padding: EdgeInsets.only(bottom: 12),
            child: Text(
              'Tu idea acaba de comenzar',
              style: TextStyle(fontWeight: FontWeight.w600),
            ),
          ),
          PublicationCard(
            publication: newPublication!,
            session: session,
            onComments: () => openConversation(newPublication!),
          ),
        ],
        if (snapshot.cards.isEmpty && newPublication == null)
          PaperPanel(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Icon(Icons.forum_outlined, size: 34),
                const SizedBox(height: 18),
                Text(
                  'Tu próximo círculo empieza aquí.',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                const SizedBox(height: 12),
                const Text(
                  'Únete a una comunidad o publica una idea. Las conversaciones de tus contactos también pueden llegar a ti.',
                  style: TextStyle(color: muted),
                ),
                const SizedBox(height: 20),
                FilledButton(
                  onPressed: () => navigate(2),
                  child: const Text('Explorar comunidades'),
                ),
              ],
            ),
          ),
        ...snapshot.cards.map(
          (c) => Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (discover)
                Padding(
                  padding: const EdgeInsets.only(bottom: 10),
                  child: Text(
                    c.selectionReason,
                    style: const TextStyle(color: muted, fontSize: 12),
                  ),
                ),
              card(c, snapshot),
            ],
          ),
        ),
        if (comparison != null)
          ExpansionTile(
            tilePadding: EdgeInsets.zero,
            title: const Text('Comparar cómo se eligieron las ideas'),
            subtitle: const Text('Mismos candidatos, preferencias e instante'),
            children: [_comparison(comparison)],
          ),
      ],
    );
    return LayoutBuilder(
      builder: (context, size) {
        final wide = size.maxWidth > 1100;
        final intro = Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              discover
                  ? 'Mira más allá\nde tu círculo.'
                  : 'Tu círculo,\nen movimiento.',
              style: Theme.of(context).textTheme.headlineLarge,
            ),
            const SizedBox(height: 18),
            Text(
              'Hola, ${session.profile!.name}. ${discover ? 'Una idea puede llevarte a otra conversación.' : 'Lo que compartimos puede acercarnos.'}',
              style: const TextStyle(color: muted, height: 1.6),
            ),
            const SizedBox(height: 24),
            const Divider(),
            const SizedBox(height: 18),
            Text(
              'Cada idea\ntiene una historia.',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 12),
            const Text(
              'Una tarjeta por original. Todos sus caminos disponibles.',
              style: TextStyle(color: muted),
            ),
            const SizedBox(height: 20),
            TextButton.icon(
              onPressed: () => navigate(4),
              icon: const Icon(Icons.hub_outlined, size: 20),
              label: const Text('Explorar la red'),
            ),
          ],
        );
        if (!wide) {
          return Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              PageHeading(
                discover
                    ? 'Mira más allá de tu círculo.'
                    : 'Tu círculo, en movimiento.',
                'Hola, ${session.profile!.name}. Las conversaciones conservan su origen.',
              ),
              center,
            ],
          );
        }
        return Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SizedBox(width: 228, child: intro),
            const SizedBox(width: 50),
            Expanded(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 650),
                child: center,
              ),
            ),
            const SizedBox(width: 36),
            SizedBox(
              width: 190,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(Icons.route_outlined, size: 30),
                  const SizedBox(height: 18),
                  Text(
                    'Conexiones\nque dejan huella.',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  const SizedBox(height: 14),
                  const Text(
                    'Abre «Cómo llegó a mí» en una publicación para recorrer sus ramas.',
                    style: TextStyle(color: muted),
                  ),
                  const SizedBox(height: 24),
                  Wrap(
                    spacing: 6,
                    children: session.contacts
                        .take(4)
                        .map((id) => PersonAvatar(id, size: 38))
                        .toList(),
                  ),
                  const SizedBox(height: 12),
                  Text(
                    '${session.contacts.length} conexiones en esta cuenta',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
              ),
            ),
          ],
        );
      },
    );
  }

  Widget _comparison(FeedComparison data) {
    final a = data.chronological.selection['metrics'] as Map? ?? {},
        b = data.diverse.selection['metrics'] as Map? ?? {};
    return Padding(
      padding: const EdgeInsets.only(bottom: 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: DataTable(
              columns: const [
                DataColumn(label: Text('Medida')),
                DataColumn(label: Text('Reciente')),
                DataColumn(label: Text('Diverso')),
              ],
              rows: [
                for (final entry in const {
                  'cards': 'Publicaciones',
                  'communities': 'Comunidades',
                  'objective': 'Objetivo F',
                  'mean_relevance': 'Relevancia media',
                }.entries)
                  DataRow(
                    cells: [
                      DataCell(Text(entry.value)),
                      DataCell(Text('${a[entry.key]}')),
                      DataCell(Text('${b[entry.key]}')),
                    ],
                  ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          SelectableText(
            'Hash de candidatos: ${data.candidateHash}\nReferencia: ${data.chronological.selection['reference_at']}\nParámetros: ${data.diverse.selection['parameters']}',
            style: const TextStyle(fontSize: 12, color: muted),
          ),
          const SizedBox(height: 12),
          const Text(
            'La selección voraz no garantiza el óptimo. Mayor diversidad en este conjunto no demuestra satisfacción de personas.',
            style: TextStyle(fontSize: 12, color: muted),
          ),
        ],
      ),
    );
  }

  Widget content() {
    if (session.loading) return const LoadingContent();
    if (session.error != null) {
      return Recovery(message: session.error!, retry: session.refresh);
    }
    if (conversation != null) {
      return ConversationView(
        key: ValueKey(conversation!.publicationId),
        publication: conversation!,
        session: session,
        onBack: () => setState(() => conversation = null),
        onRetired: (removed) {
          if (!mounted) return;
          setState(() {
            if (newPublication?.publicationId == removed.publicationId) {
              newPublication = null;
            }
            if (conversation?.publicationId == removed.publicationId) {
              conversation = removed;
            }
          });
          notify('La publicación quedó retirada. Su recorrido se conserva.');
          session.refresh();
        },
      );
    }
    if (route != null) {
      return ProvenanceView(
        key: ValueKey(route),
        session: session,
        snapshotId: route!.snapshot,
        publicationId: route!.publication,
        onBack: () => setState(() => route = null),
        onOriginal: openConversation,
      );
    }
    return switch (page) {
      0 => feed(false),
      1 => feed(true),
      2 => CommunitiesView(
        session: session,
        onChanged: notify,
        onCompose: () => navigate(5),
      ),
      3 => ProfileView(
        session: session,
        onChanged: notify,
        onOriginal: openConversation,
        onCompose: () => navigate(5),
      ),
      4 => NetworkView(session: session),
      _ => ComposeView(
        session: session,
        draft: widget.draft,
        onCommunities: () => navigate(2),
        onPublished: (result) {
          setState(() {
            newPublication = result.publication;
            page = 0;
          });
          notify('Tu publicación quedó guardada.');
          session.refresh();
        },
      ),
    };
  }

  Future<void> historicalAccount() async {
    final id = await showDialog<String>(
      context: context,
      builder: (_) => const _HistoricalAccountDialog(),
    );
    if (id != null && mounted) widget.onAccount(id);
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
    animation: session,
    builder: (context, _) => _buildWorkspace(context),
  );

  Widget _buildWorkspace(BuildContext context) => LayoutBuilder(
    builder: (context, size) {
      final desktop = size.maxWidth >= 980;
      return Scaffold(
        appBar: PreferredSize(
          preferredSize: const Size.fromHeight(88),
          child: SafeArea(
            bottom: false,
            child: Container(
              height: 88,
              decoration: const BoxDecoration(
                color: paper,
                border: Border(bottom: BorderSide(color: line)),
              ),
              padding: EdgeInsets.symmetric(horizontal: desktop ? 40 : 18),
              child: Row(
                children: [
                  InkWell(
                    onTap: () => openLocation(widget.landingUrl),
                    borderRadius: BorderRadius.circular(8),
                    child: Padding(
                      padding: const EdgeInsets.symmetric(vertical: 10),
                      child: Brand(compact: !desktop),
                    ),
                  ),
                  if (desktop) ...[
                    const SizedBox(width: 36),
                    ...List.generate(
                      5,
                      (i) => Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 2),
                        child: TextButton(
                          onPressed: () => navigate(i),
                          style: TextButton.styleFrom(
                            backgroundColor:
                                page == i &&
                                    route == null &&
                                    conversation == null
                                ? yellow.withValues(alpha: .35)
                                : null,
                          ),
                          child: Text(destinations[i]),
                        ),
                      ),
                    ),
                  ],
                  const Spacer(),
                  if (desktop)
                    FilledButton.icon(
                      onPressed: session.loading ? null : () => navigate(5),
                      icon: const Icon(Icons.add, size: 20),
                      label: const Text('Publicar'),
                    ),
                  SizedBox(width: desktop ? 20 : 10),
                  PopupMenuButton<String>(
                    tooltip: widget.firebaseUser == null
                        ? 'Cambiar cuenta ficticia'
                        : 'Mi cuenta',
                    onSelected: (id) {
                      if (id == 'sign-out') {
                        FirebaseAuth.instance.signOut();
                      } else if (id == 'historical') {
                        historicalAccount();
                      } else {
                        widget.onAccount(id);
                      }
                    },
                    itemBuilder: (context) => widget.firebaseUser != null
                        ? [
                            const PopupMenuItem(
                              value: 'sign-out',
                              child: Text('Cerrar sesión'),
                            ),
                          ]
                        : [
                            for (final id in [
                              'ana',
                              'bruno',
                              'carla',
                              'diego',
                              'elena',
                            ])
                              PopupMenuItem(
                                value: id,
                                child: Row(
                                  children: [
                                    PersonAvatar(id, size: 30),
                                    const SizedBox(width: 10),
                                    Text(personName(id)),
                                    if (widget.actor == id) ...[
                                      const SizedBox(width: 10),
                                      const Icon(Icons.check, size: 18),
                                    ],
                                  ],
                                ),
                              ),
                            const PopupMenuDivider(),
                            const PopupMenuItem(
                              value: 'historical',
                              child: Text('Cuenta del histórico…'),
                            ),
                          ],
                    child: Padding(
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          PersonAvatar(
                            session.profile?.uid ?? widget.actor,
                            size: 36,
                          ),
                          const SizedBox(width: 10),
                          ConstrainedBox(
                            constraints: BoxConstraints(
                              maxWidth: desktop ? 120 : 175,
                            ),
                            child: Text(
                              widget.firebaseUser == null
                                  ? personName(widget.actor)
                                  : session.profile?.name ?? 'Mi cuenta',
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ),
                          const SizedBox(width: 6),
                          const Icon(Icons.expand_more, size: 18),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
        body: SafeArea(
          top: false,
          child: Scrollbar(
            controller: scroll,
            child: SingleChildScrollView(
              controller: scroll,
              padding: EdgeInsets.fromLTRB(
                desktop ? 40 : 20,
                desktop ? 48 : 28,
                desktop ? 40 : 20,
                110,
              ),
              child: Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 1320),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      content(),
                      const SizedBox(height: 50),
                      const Divider(),
                      const SizedBox(height: 18),
                      Text(
                        widget.firebaseUser == null
                            ? 'Outspark · Proyecto UPC · Cuentas ficticias. Los cambios se conservan al recargar.'
                            : 'Outspark · Proyecto UPC',
                        style: const TextStyle(color: muted, fontSize: 12),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
        bottomNavigationBar: desktop
            ? null
            : NavigationBar(
                height: 72,
                selectedIndex: page < 5 ? page : lastDestination,
                onDestinationSelected: navigate,
                destinations: List.generate(
                  5,
                  (i) => NavigationDestination(
                    icon: Icon(icons[i]),
                    label: i == 4
                        ? 'Red'
                        : i == 2
                        ? 'Círculos'
                        : destinations[i],
                  ),
                ),
              ),
        floatingActionButton:
            desktop || page == 5 || route != null || conversation != null
            ? null
            : FloatingActionButton.extended(
                onPressed: session.loading ? null : () => navigate(5),
                backgroundColor: yellow,
                foregroundColor: ink,
                icon: const Icon(Icons.add),
                label: const Text('Publicar'),
              ),
      );
    },
  );
}

class _HistoricalAccountDialog extends StatefulWidget {
  const _HistoricalAccountDialog();
  @override
  State<_HistoricalAccountDialog> createState() =>
      _HistoricalAccountDialogState();
}

class _HistoricalAccountDialogState extends State<_HistoricalAccountDialog> {
  final value = TextEditingController();
  String? error;
  @override
  void dispose() {
    value.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: const Text('Explorar una cuenta de simulación'),
    content: TextField(
      controller: value,
      autofocus: true,
      keyboardType: TextInputType.number,
      decoration: InputDecoration(
        labelText: 'ID del histórico',
        helperText:
            'Solo simula actividad nueva; no accede a una persona real.',
        errorText: error,
        helperMaxLines: 3,
      ),
    ),
    actions: [
      TextButton(
        onPressed: () => Navigator.pop(context),
        child: const Text('Cancelar'),
      ),
      FilledButton(
        onPressed: () {
          final id = int.tryParse(value.text.trim());
          if (id != null && id >= 0) {
            Navigator.pop(context, 'fb-$id');
          } else {
            setState(() => error = 'Escribe un ID entero no negativo.');
          }
        },
        child: const Text('Usar cuenta'),
      ),
    ],
  );
}

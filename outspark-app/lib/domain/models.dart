/// Modelos inmutables del contrato HTTP de Outspark.
///
/// Cada `fromJson` valida los tipos de forma estricta y lanza
/// [FormatException] con la ruta del campo inválido (por ejemplo
/// `FeedSnapshot.cards[2].publication.created_at`).
library;

typedef JsonMap = Map<String, dynamic>;

/// Copia profunda e inmodificable de un objeto JSON.
JsonMap freezeJson(JsonMap json) => Map<String, dynamic>.unmodifiable(
  json.map((key, value) => MapEntry(key, _freeze(value))),
);

Object? _freeze(Object? value) => switch (value) {
  Map<String, dynamic>() => freezeJson(value),
  List<dynamic>() => List<dynamic>.unmodifiable(value.map(_freeze)),
  _ => value,
};

/// Lector estricto que conserva la ruta del campo para mensajes de error.
final class _Reader {
  const _Reader(this._json, this._path);

  final JsonMap _json;
  final String _path;

  Never _fail(String key, String expected) => throw FormatException(
    'Respuesta inválida: «$_path.$key» debe ser $expected.',
  );

  String string(String key) {
    final value = _json[key];
    if (value is String) return value;
    _fail(key, 'un texto');
  }

  String? optionalString(String key) {
    final value = _json[key];
    if (value is String?) return value;
    _fail(key, 'un texto o null');
  }

  int integer(String key) {
    final value = _json[key];
    if (value is int) return value;
    _fail(key, 'un entero');
  }

  bool boolean(String key) {
    final value = _json[key];
    if (value is bool) return value;
    _fail(key, 'un booleano');
  }

  DateTime dateTime(String key) {
    final value = _json[key];
    final parsed = value is String ? DateTime.tryParse(value) : null;
    if (parsed != null) return parsed;
    _fail(key, 'una fecha ISO-8601');
  }

  List<String> stringList(String key) {
    final value = _json[key];
    if (value is List && value.every((item) => item is String)) {
      return List<String>.unmodifiable(value);
    }
    _fail(key, 'una lista de textos');
  }

  List<int> integerList(String key) {
    final value = _json[key];
    if (value is List && value.every((item) => item is int)) {
      return List<int>.unmodifiable(value);
    }
    _fail(key, 'una lista de enteros');
  }

  _Reader object(String key) {
    final value = _json[key];
    if (value is Map<String, dynamic>) return _Reader(value, '$_path.$key');
    _fail(key, 'un objeto');
  }

  JsonMap rawObject(String key) => freezeJson(object(key)._json);

  List<T> objects<T>(String key, T Function(_Reader reader) parse) {
    final value = _json[key];
    if (value is! List) _fail(key, 'una lista de objetos');
    return List<T>.unmodifiable([
      for (final (index, item) in value.indexed)
        if (item is Map<String, dynamic>)
          parse(_Reader(item, '$_path.$key[$index]'))
        else
          _fail('$key[$index]', 'un objeto'),
    ]);
  }
}

class Topic {
  const Topic({required this.id, required this.name});

  factory Topic.fromJson(JsonMap json) => Topic._read(_Reader(json, 'Topic'));

  factory Topic._read(_Reader r) =>
      Topic(id: r.string('topic_id'), name: r.string('name'));

  final String id;
  final String name;
}

class Community {
  const Community({required this.id, required this.name});

  factory Community.fromJson(JsonMap json) =>
      Community._read(_Reader(json, 'Community'));

  factory Community._read(_Reader r) =>
      Community(id: r.string('community_id'), name: r.string('name'));

  final String id;
  final String name;
}

class Profile {
  Profile({
    required this.uid,
    required this.name,
    required List<String> topicIds,
    required this.preferencesVersion,
  }) : topicIds = List.unmodifiable(topicIds);

  /// Parsea la respuesta de `GET /me`: `{profile: {...}, preferences: {...}}`.
  factory Profile.fromJson(JsonMap json) {
    final root = _Reader(json, 'Me');
    final profile = root.object('profile');
    final preferences = root.object('preferences');
    return Profile(
      uid: profile.string('uid'),
      name: profile.string('name'),
      topicIds: preferences.stringList('topic_ids'),
      preferencesVersion: preferences.integer('version'),
    );
  }

  final String uid;
  final String name;
  final List<String> topicIds;
  final int preferencesVersion;
}

class Publication {
  Publication({
    required this.publicationId,
    required this.authorId,
    required this.communityId,
    this.body,
    required List<String> topicIds,
    required this.status,
    required this.rootEventId,
    required this.createdAt,
  }) : topicIds = List.unmodifiable(topicIds);

  factory Publication.fromJson(JsonMap json) =>
      Publication._read(_Reader(json, 'Publication'));

  // `body` se omite cuando el original está retirado; no se sustituye por `message`.
  factory Publication._read(_Reader r) => Publication(
    publicationId: r.string('publication_id'),
    authorId: r.string('author_id'),
    communityId: r.string('community_id'),
    body: r.optionalString('body'),
    topicIds: r.stringList('topic_ids'),
    status: r.string('status'),
    rootEventId: r.string('root_event_id'),
    createdAt: r.dateTime('created_at'),
  );

  final String publicationId;
  final String authorId;
  final String communityId;

  /// `null` si el original fue retirado.
  final String? body;
  final List<String> topicIds;
  final String status;
  final String rootEventId;
  final DateTime createdAt;
}

class ArrivalReason {
  const ArrivalReason({
    required this.type,
    required this.text,
    this.contactId,
    this.communityId,
  });

  factory ArrivalReason.fromJson(JsonMap json) =>
      ArrivalReason._read(_Reader(json, 'ArrivalReason'));

  factory ArrivalReason._read(_Reader r) => ArrivalReason(
    type: r.string('type'),
    text: r.string('text'),
    contactId: r.optionalString('contact_id'),
    communityId: r.optionalString('community_id'),
  );

  final String type;
  final String text;
  final String? contactId;
  final String? communityId;
}

class FeedSource {
  FeedSource({required this.eventId, required List<ArrivalReason> reasons})
    : reasons = List.unmodifiable(reasons);

  factory FeedSource.fromJson(JsonMap json) =>
      FeedSource._read(_Reader(json, 'FeedSource'));

  factory FeedSource._read(_Reader r) => FeedSource(
    eventId: r.string('event_id'),
    reasons: r.objects('reasons', ArrivalReason._read),
  );

  /// Referencia opaca; no debe interpretarse como ruta.
  final String eventId;
  final List<ArrivalReason> reasons;
}

class FeedCard {
  FeedCard({
    required this.publication,
    required List<FeedSource> sources,
    required this.selectionReason,
  }) : sources = List.unmodifiable(sources);

  factory FeedCard.fromJson(JsonMap json) =>
      FeedCard._read(_Reader(json, 'FeedCard'));

  factory FeedCard._read(_Reader r) => FeedCard(
    publication: Publication._read(r.object('publication')),
    sources: r.objects('sources', FeedSource._read),
    selectionReason: r.string('selection_reason'),
  );

  final Publication publication;
  final List<FeedSource> sources;
  final String selectionReason;
}

class FeedSnapshot {
  FeedSnapshot({
    required this.snapshotId,
    required this.strategy,
    required List<FeedCard> cards,
    required this.generatedAt,
    required JsonMap selection,
  }) : cards = List.unmodifiable(cards),
       selection = freezeJson(selection);

  factory FeedSnapshot.fromJson(JsonMap json) =>
      FeedSnapshot._read(_Reader(json, 'FeedSnapshot'));

  factory FeedSnapshot._read(_Reader r) => FeedSnapshot(
    snapshotId: r.string('snapshot_id'),
    strategy: r.string('strategy'),
    cards: r.objects('cards', FeedCard._read),
    generatedAt: r.dateTime('generated_at'),
    selection: r.rawObject('selection'),
  );

  final String snapshotId;
  final String strategy;
  final List<FeedCard> cards;
  final DateTime generatedAt;

  /// Metadatos de selección tal como los publica el servidor.
  final JsonMap selection;
}

class FeedComparison {
  const FeedComparison({
    required this.chronological,
    required this.diverse,
    required this.candidateHash,
  });

  /// Parsea `{feeds: {chronological, diverse}, candidate_hash}`.
  factory FeedComparison.fromJson(JsonMap json) {
    final r = _Reader(json, 'FeedComparison');
    final feeds = r.object('feeds');
    return FeedComparison(
      chronological: FeedSnapshot._read(feeds.object('chronological')),
      diverse: FeedSnapshot._read(feeds.object('diverse')),
      candidateHash: r.string('candidate_hash'),
    );
  }

  final FeedSnapshot chronological;
  final FeedSnapshot diverse;
  final String candidateHash;
}

class PublicationEvent {
  const PublicationEvent({
    required this.eventId,
    required this.actorId,
    this.parentEventId,
    required this.createdAt,
  });

  factory PublicationEvent.fromJson(JsonMap json) =>
      PublicationEvent._read(_Reader(json, 'PublicationEvent'));

  factory PublicationEvent._read(_Reader r) => PublicationEvent(
    eventId: r.string('event_id'),
    actorId: r.string('actor_id'),
    parentEventId: r.optionalString('parent_event_id'),
    createdAt: r.dateTime('created_at'),
  );

  final String eventId;
  final String actorId;

  /// `null` únicamente en el evento raíz del original.
  final String? parentEventId;
  final DateTime createdAt;
}

class ArrivalRoute {
  ArrivalRoute({required this.source, required List<PublicationEvent> events})
    : events = List.unmodifiable(events);

  factory ArrivalRoute.fromJson(JsonMap json) =>
      ArrivalRoute._read(_Reader(json, 'ArrivalRoute'));

  factory ArrivalRoute._read(_Reader r) => ArrivalRoute(
    source: FeedSource._read(r.object('source')),
    events: r.objects('events', PublicationEvent._read),
  );

  final FeedSource source;

  /// Ordenados desde el autor original hasta el evento fuente.
  final List<PublicationEvent> events;
}

class Provenance {
  Provenance({
    required this.publication,
    required List<ArrivalRoute> routes,
    required this.eventCount,
  }) : routes = List.unmodifiable(routes);

  factory Provenance.fromJson(JsonMap json) {
    final r = _Reader(json, 'Provenance');
    return Provenance(
      publication: Publication._read(r.object('publication')),
      routes: r.objects('routes', ArrivalRoute._read),
      eventCount: r.object('tree').integer('event_count'),
    );
  }

  final Publication publication;
  final List<ArrivalRoute> routes;
  final int eventCount;
}

class Comment {
  const Comment({
    required this.commentId,
    required this.authorId,
    required this.body,
    required this.createdAt,
  });

  factory Comment.fromJson(JsonMap json) =>
      Comment._read(_Reader(json, 'Comment'));

  factory Comment._read(_Reader r) => Comment(
    commentId: r.string('comment_id'),
    authorId: r.string('author_id'),
    body: r.string('body'),
    createdAt: r.dateTime('created_at'),
  );

  final String commentId;
  final String authorId;
  final String body;
  final DateTime createdAt;
}

class CreatedPublication {
  const CreatedPublication({
    required this.publication,
    required this.eventId,
    required this.replayed,
  });

  factory CreatedPublication.fromJson(JsonMap json) {
    final r = _Reader(json, 'CreatedPublication');
    return CreatedPublication(
      publication: Publication._read(r.object('publication')),
      eventId: r.string('event_id'),
      replayed: r.boolean('replayed'),
    );
  }

  final Publication publication;

  /// Referencia opaca del evento raíz; puede ser padre de una republicación.
  final String eventId;
  final bool replayed;
}

class Page<T> {
  Page({required List<T> items, this.nextCursor, this.unavailableCount = 0})
    : items = List.unmodifiable(items);

  /// Parsea `{items: [...], next_cursor}` aplicando [fromItem] a cada objeto.
  factory Page.fromJson(JsonMap json, T Function(JsonMap item) fromItem) {
    final r = _Reader(json, 'Page');
    final unavailable = json.containsKey('unavailable_count')
        ? r.integer('unavailable_count')
        : 0;
    if (unavailable < 0) r._fail('unavailable_count', 'un entero no negativo');
    return Page(
      unavailableCount: unavailable,
      items: r.objects('items', (item) => fromItem(item._json)),
      nextCursor: r.optionalString('next_cursor'),
    );
  }

  final List<T> items;
  final int unavailableCount;

  /// Cursor opaco; `null` al terminar la lista.
  final String? nextCursor;
}

class DiffusionContact {
  const DiffusionContact(this.id, this.degree);
  final int id, degree;

  static DiffusionContact _read(_Reader r) =>
      DiffusionContact(r.integer('node_id'), r.integer('degree'));
}

class DiffusionRound {
  const DiffusionRound(this.hop, this.newNodes);
  final int hop, newNodes;

  static DiffusionRound _read(_Reader r) =>
      DiffusionRound(r.integer('hop'), r.integer('new_nodes'));
}

class DiffusionPlan {
  const DiffusionPlan(this.contacts, this.reachable, this.rounds);
  final List<int> contacts;
  final int reachable;
  final List<DiffusionRound> rounds;

  static DiffusionPlan _read(_Reader r) => DiffusionPlan(
    r.integerList('contacts'),
    r.integer('reachable'),
    r.objects('rounds', DiffusionRound._read),
  );
}

class DiffusionComparison {
  const DiffusionComparison(
    this.origin,
    this.contacts,
    this.degree,
    this.greedy,
    this.custom,
  );
  final int origin;
  final List<DiffusionContact> contacts;
  final DiffusionPlan degree, greedy;
  final DiffusionPlan? custom;

  factory DiffusionComparison.fromJson(JsonMap json) {
    final r = _Reader(json, 'DiffusionComparison');
    return DiffusionComparison(
      r.integer('origin'),
      r.objects('contacts', DiffusionContact._read),
      DiffusionPlan._read(r.object('degree')),
      DiffusionPlan._read(r.object('greedy')),
      json['custom'] == null ? null : DiffusionPlan._read(r.object('custom')),
    );
  }
}

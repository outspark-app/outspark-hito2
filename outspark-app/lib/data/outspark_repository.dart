import 'package:outspark_app/data/api_client.dart';
import 'package:outspark_app/domain/models.dart';

/// Operaciones de Outspark sobre [ApiClient].
///
/// Los identificadores se codifican uno a uno como segmentos de ruta; los
/// `event_id` y cursores son opacos y nunca se interpretan como rutas.
/// Las respuestas mal formadas se convierten en [ApiException] con código
/// `invalid_response`.
class OutsparkRepository {
  OutsparkRepository(ApiClient client) : _client = client;

  final ApiClient _client;

  static const datasetId = 'facebook-wosn2009';
  static const pageLimit = 50;

  /// Tope defensivo de páginas por listado completo.
  static const _maxPages = 1000;
  static const _datasetPath = '/network/datasets/$datasetId';

  // Profiles

  Future<Profile> loadProfile() async =>
      _parse(await _client.request('GET', '/me'), Profile.fromJson);

  Future<void> savePreferences(List<String> topics, int version) async {
    await _client.request(
      'PUT',
      '/me/preferences',
      body: {'topic_ids': topics, 'version': version},
    );
  }

  // Communities y Connections

  Future<List<Community>> listCommunities() =>
      _collectAll('/communities', Community.fromJson);

  Future<List<Topic>> listTopics() => _collectAll('/topics', Topic.fromJson);

  /// `community_id` de las membresías activas.
  Future<List<String>> listMemberships() async {
    final memberships = await _collectAll(
      '/me/communities',
      (json) =>
          (id: _string(json, 'community_id'), status: _string(json, 'status')),
    );
    return List<String>.unmodifiable([
      for (final m in memberships)
        if (m.status == 'ACTIVE') m.id,
    ]);
  }

  /// `contact_id` de las conexiones activas.
  Future<List<String>> listContacts() async {
    final contacts = await _collectAll(
      '/me/contacts',
      (json) =>
          (id: _string(json, 'contact_id'), status: _string(json, 'status')),
    );
    return List<String>.unmodifiable([
      for (final c in contacts)
        if (c.status == 'ACTIVE') c.id,
    ]);
  }

  Future<void> joinCommunity(String id) async {
    await _client.request('PUT', '/me/communities/${_segment(id, 'id')}');
  }

  Future<void> leaveCommunity(String id) async {
    await _client.request('DELETE', '/me/communities/${_segment(id, 'id')}');
  }

  Future<Page<Publication>> myPublications({String? cursor}) =>
      _page('/me/publications', Publication.fromJson, cursor: cursor);

  Future<DiffusionComparison> simulateDiffusion(
    String id, {
    required int origin,
    required int hops,
    required int slots,
    List<int>? contacts,
  }) async => _parse(
    await _client.request(
      'POST',
      '/publications/${_segment(id, 'id')}/diffusion',
      requestTimeout: const Duration(seconds: 55),
      body: {
        'origin': origin,
        'max_hops': hops,
        'slots': slots,
        'custom_contacts': ?contacts,
      },
    ),
    DiffusionComparison.fromJson,
  );

  // Publishing

  Future<CreatedPublication> createPublication(
    String communityId,
    String body,
    List<String> topics, {
    required String idempotencyKey,
  }) async {
    final json = await _client.request(
      'POST',
      '/publications',
      body: {'community_id': communityId, 'body': body, 'topic_ids': topics},
      idempotencyKey: idempotencyKey,
    );
    return _parse(json, CreatedPublication.fromJson);
  }

  /// Republica desde [parentEventId] y devuelve el `event_id` nuevo.
  Future<String> repost(
    String parentEventId, {
    required String idempotencyKey,
  }) async {
    final json = await _client.request(
      'POST',
      '/reposts',
      body: {'parent_event_id': parentEventId},
      idempotencyKey: idempotencyKey,
    );
    return _parse(json, (data) => _string(data, 'event_id'));
  }

  Future<Publication> retirePublication(String id) async => _parse(
    await _client.request('DELETE', '/publications/${_segment(id, 'id')}'),
    Publication.fromJson,
  );

  Future<Publication> getPublication(String id) async => _parse(
    await _client.request('GET', '/publications/${_segment(id, 'id')}'),
    Publication.fromJson,
  );

  Future<Page<Comment>> comments(String id, {String? cursor}) async => _page(
    '/publications/${_segment(id, 'id')}/comments',
    Comment.fromJson,
    cursor: cursor,
  );

  Future<Comment> addComment(
    String id,
    String body, {
    required String idempotencyKey,
  }) async {
    final json = await _client.request(
      'POST',
      '/publications/${_segment(id, 'id')}/comments',
      body: {'body': body},
      idempotencyKey: idempotencyKey,
    );
    return _parse(json, Comment.fromJson);
  }

  // Discovery

  Future<FeedSnapshot> createFeed(String strategy) async => _parse(
    await _client.request(
      'POST',
      '/feed/snapshots',
      body: {'strategy': strategy},
    ),
    FeedSnapshot.fromJson,
  );

  Future<FeedComparison> compareFeeds() async => _parse(
    await _client.request('POST', '/feed/comparisons'),
    FeedComparison.fromJson,
  );

  Future<FeedSnapshot> readFeed(String id) async => _parse(
    await _client.request('GET', '/feed/${_segment(id, 'id')}'),
    FeedSnapshot.fromJson,
  );

  Future<Provenance> provenance(String snapshotId, String publicationId) async {
    final snapshot = _segment(snapshotId, 'snapshotId');
    final publication = _segment(publicationId, 'publicationId');
    final json = await _client.request(
      'GET',
      '/feed/$snapshot/cards/$publication/provenance',
    );
    return _parse(json, Provenance.fromJson);
  }

  // Network Analysis

  Future<JsonMap> dataset() async =>
      _parse(await _client.request('GET', _datasetPath), freezeJson);

  Future<Page<JsonMap>> nodes({String? cursor}) =>
      _page('$_datasetPath/nodes', freezeJson, cursor: cursor);

  Future<JsonMap> node(int id) async =>
      _parse(await _client.request('GET', _nodePath(id, 'id')), freezeJson);

  Future<Page<JsonMap>> neighbors(int id, {String? cursor}) async =>
      _page('${_nodePath(id, 'id')}/neighbors', freezeJson, cursor: cursor);

  Future<Page<JsonMap>> wallEvents(
    int id, {
    String direction = 'received',
    String? cursor,
  }) async {
    if (direction != 'received' && direction != 'sent') {
      throw ArgumentError.value(
        direction,
        'direction',
        'Debe ser "received" o "sent"',
      );
    }
    return _page(
      '${_nodePath(id, 'id')}/wall-events',
      freezeJson,
      cursor: cursor,
      query: {'direction': direction},
    );
  }

  Future<JsonMap> reach(int seed, int hops) async {
    RangeError.checkValueInInterval(hops, 1, 3, 'hops');
    final json = await _client.request(
      'GET',
      '${_nodePath(seed, 'seed')}/reach',
      query: {'max_hops': '$hops'},
    );
    return _parse(json, freezeJson);
  }

  Future<JsonMap> structuralAnalysis() async => _parse(
    await _client.request('GET', '$_datasetPath/analysis'),
    freezeJson,
  );
  Future<JsonMap> structuralGroup(int id) async => _parse(
    await _client.request('GET', '$_datasetPath/analysis/nodes/$id'),
    freezeJson,
  );

  // Auxiliares

  Future<Page<T>> _page<T>(
    String path,
    T Function(JsonMap item) fromItem, {
    String? cursor,
    Map<String, String> query = const {},
  }) async {
    final json = await _client.request(
      'GET',
      path,
      query: {...query, 'limit': '$pageLimit', 'cursor': ?cursor},
    );
    return _parse(json, (data) => Page.fromJson(data, fromItem));
  }

  /// Recorre todas las páginas y se detiene si el servidor repite un cursor.
  Future<List<T>> _collectAll<T>(
    String path,
    T Function(JsonMap item) fromItem,
  ) async {
    final items = <T>[];
    final seen = <String>{};
    String? cursor;
    for (var pages = 0; pages < _maxPages; pages++) {
      final page = await _page(path, fromItem, cursor: cursor);
      items.addAll(page.items);
      final next = page.nextCursor;
      if (next == null) return List<T>.unmodifiable(items);
      if (!seen.add(next)) {
        throw const ApiException(
          code: 'pagination_loop',
          message:
              'El servidor repitió un cursor de paginación; se detuvo la lectura.',
        );
      }
      cursor = next;
    }
    throw const ApiException(
      code: 'pagination_limit',
      message: 'La lista supera el máximo de páginas admitido por la app.',
    );
  }

  static T _parse<T>(JsonMap json, T Function(JsonMap json) parse) {
    try {
      return parse(json);
    } on FormatException catch (error) {
      throw ApiException(code: 'invalid_response', message: error.message);
    }
  }

  static String _string(JsonMap json, String key) {
    final value = json[key];
    if (value is String) return value;
    throw FormatException('Respuesta inválida: «$key» debe ser un texto.');
  }

  static String _segment(String id, String name) {
    if (id.isEmpty || id == '.' || id == '..') {
      throw ArgumentError.value(id, name, 'Identificador no válido');
    }
    return Uri.encodeComponent(id);
  }

  static String _nodePath(int id, String name) {
    RangeError.checkNotNegative(id, name);
    return '$_datasetPath/nodes/$id';
  }
}

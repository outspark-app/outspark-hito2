import 'dart:async';
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:outspark_app/data/api_client.dart';
import 'package:outspark_app/data/outspark_repository.dart';

final localApi = Uri.parse('http://127.0.0.1:18080/api');

/// Respuesta como la del servidor: bytes UTF-8 sin charset declarado.
http.Response jsonResponse(
  Object? body, {
  int status = 200,
  Map<String, String> headers = const {},
}) => http.Response.bytes(
  utf8.encode(jsonEncode(body)),
  status,
  headers: {'content-type': 'application/json', ...headers},
);

Map<String, dynamic> publicationJson({
  String id = 'pub-1',
  String? body = 'Una idea.',
  String status = 'ACTIVE',
}) => {
  'publication_id': id,
  'author_id': 'ana',
  'community_id': 'diseno',
  'body': ?body,
  'topic_ids': ['diseno'],
  'visibility': 'public',
  'status': status,
  'root_event_id': '$id/root',
  'created_at': '2026-10-19T12:00:00Z',
};

Map<String, dynamic> eventJson(String id, String actor, String? parent) => {
  'publication_id': 'pub-1',
  'actor_id': actor,
  'parent_event_id': parent,
  'event_id': id,
  'created_at': '2026-10-19T12:00:00Z',
};

Map<String, dynamic> snapshotJson(String id, String strategy) => {
  'snapshot_id': id,
  'viewer_id': 'diego',
  'strategy': strategy,
  'algorithm_version': '1',
  'generated_at': '2026-10-19T12:05:00Z',
  'cards': [
    {
      'publication_id': 'pub-1',
      'position': 0,
      'sources': [
        {
          'event_id': 'pub-1/root/bruno',
          'reasons': [
            {
              'type': 'contact',
              'text': 'Bruno lo republicó.',
              'contact_id': 'bruno',
            },
          ],
        },
      ],
      'relevance': '0.75',
      'selection_reason': 'Actividad reciente.',
      'publication': publicationJson(),
    },
  ],
  'source_count': 1,
  'limits': {'cards': 10},
  'selection': {
    'candidate_hash': 'abc',
    'metrics': {'cards': 1},
  },
};

TypeMatcher<ApiException> apiError({int? status, required String code}) =>
    isA<ApiException>()
        .having((e) => e.statusCode, 'statusCode', status)
        .having((e) => e.code, 'code', code);

void main() {
  group('identidad e idempotencia', () {
    test(
      'envía X-Demo-User e Idempotency-Key sin identidad en el JSON',
      () async {
        late http.Request sent;
        final repo = OutsparkRepository(
          ApiClient(
            baseUrl: localApi,
            demoUser: 'ana',
            client: MockClient((request) async {
              sent = request;
              return jsonResponse({
                'publication_id': 'pub-1',
                'event_id': 'pub-1/root',
                'replayed': false,
                'publication': publicationJson(),
              }, status: 201);
            }),
          ),
        );

        final created = await repo.createPublication('diseno', 'Una idea.', [
          'diseno',
        ], idempotencyKey: 'clave-1');

        expect(sent.method, 'POST');
        expect(sent.headers['X-Demo-User'], 'ana');
        expect(sent.headers['Idempotency-Key'], 'clave-1');
        expect(sent.headers['Content-Type'], startsWith('application/json'));
        expect(sent.headers.containsKey('Authorization'), isFalse);
        expect(jsonDecode(sent.body), {
          'community_id': 'diseno',
          'body': 'Una idea.',
          'topic_ids': ['diseno'],
        });
        expect(created.eventId, 'pub-1/root');
        expect(created.replayed, isFalse);
      },
    );

    test('las lecturas no llevan Idempotency-Key', () async {
      late http.Request sent;
      final repo = OutsparkRepository(
        ApiClient(
          baseUrl: localApi,
          demoUser: 'diego',
          client: MockClient((request) async {
            sent = request;
            return jsonResponse({
              'profile': {'uid': 'diego', 'name': 'Diego', 'status': 'ACTIVE'},
              'preferences': {
                'topic_ids': ['tecnologia'],
                'version': 3,
              },
            });
          }),
        ),
      );

      final profile = await repo.loadProfile();

      expect(sent.headers.containsKey('Idempotency-Key'), isFalse);
      expect(profile.uid, 'diego');
      expect(profile.topicIds, ['tecnologia']);
      expect(profile.preferencesVersion, 3);
    });

    test('con bearer token usa Authorization y nunca X-Demo-User', () async {
      late http.Request sent;
      final client = ApiClient(
        baseUrl: Uri.parse('https://api.outspark.example/api'),
        bearerToken: 'jwt.token.value',
        client: MockClient((request) async {
          sent = request;
          return jsonResponse({'items': [], 'next_cursor': null});
        }),
      );

      await OutsparkRepository(client).listTopics();

      expect(sent.headers['Authorization'], 'Bearer jwt.token.value');
      expect(sent.headers.containsKey('X-Demo-User'), isFalse);
    });

    test('rechaza la identidad demo contra hosts externos, incluso https', () {
      final mock = MockClient(
        (_) async => fail('No debe enviarse ninguna petición'),
      );
      for (final url in [
        'https://api.outspark.example/api',
        'http://192.168.1.20:18080/api',
        'http://127.0.0.1.example.com/api',
      ]) {
        expect(
          () =>
              ApiClient(baseUrl: Uri.parse(url), demoUser: 'ana', client: mock),
          throwsArgumentError,
          reason: url,
        );
      }
      for (final url in [
        'http://localhost:18080/api',
        'https://127.0.0.1/api',
        'http://[::1]:18080/api',
      ]) {
        expect(
          () =>
              ApiClient(baseUrl: Uri.parse(url), demoUser: 'ana', client: mock),
          returnsNormally,
          reason: url,
        );
      }
    });
  });

  group('URL', () {
    test(
      'conserva /api y codifica cada identificador opaco como un segmento',
      () async {
        final requests = <http.Request>[];
        final repo = OutsparkRepository(
          ApiClient(
            baseUrl: Uri.parse('http://localhost:18080/api/'),
            demoUser: 'diego',
            client: MockClient((request) async {
              requests.add(request);
              return jsonResponse({
                'snapshot_id': 'snap/1',
                'viewer_id': 'diego',
                'publication': publicationJson(id: 'pub#2?x'),
                'routes': [],
                'tree': {'dfs': [], 'event_count': 1},
              });
            }),
          ),
        );

        await repo.provenance('snap/1', 'pub#2?x');

        final url = requests.single.url;
        expect(url.host, 'localhost');
        expect(url.pathSegments, [
          'api',
          'feed',
          'snap/1',
          'cards',
          'pub#2?x',
          'provenance',
        ]);
        expect(url.hasQuery, isFalse);
        expect(url.hasFragment, isFalse);
      },
    );

    test('el event_id padre viaja en el cuerpo, no en la ruta', () async {
      late http.Request sent;
      final repo = OutsparkRepository(
        ApiClient(
          baseUrl: localApi,
          demoUser: 'bruno',
          client: MockClient((request) async {
            sent = request;
            return jsonResponse({
              'publication_id': 'pub-1',
              'event_id': 'pub-1/root/bruno',
              'replayed': false,
            }, status: 201);
          }),
        ),
      );

      final eventId = await repo.repost('pub-1/root', idempotencyKey: 'r-1');

      expect(sent.url.pathSegments, ['api', 'reposts']);
      expect(jsonDecode(sent.body), {'parent_event_id': 'pub-1/root'});
      expect(eventId, 'pub-1/root/bruno');
    });

    test('query de paginación y filtros de Network Analysis', () async {
      late http.Request sent;
      final repo = OutsparkRepository(
        ApiClient(
          baseUrl: localApi,
          demoUser: 'fb-7',
          client: MockClient((request) async {
            sent = request;
            return jsonResponse({
              'items': [
                {
                  'event_id': 'wall:12',
                  'source_line': 12,
                  'wall_owner_id': 9,
                  'author_id': 7,
                  'timestamp': 1,
                  'content_available': false,
                },
              ],
              'next_cursor': null,
              'dataset_id': 'facebook-wosn2009',
              'node_id': 7,
              'kind': 'wall_sent',
            });
          }),
        ),
      );

      final page = await repo.wallEvents(
        7,
        direction: 'sent',
        cursor: 'a+b/c= d',
      );

      expect(sent.url.pathSegments, [
        'api',
        'network',
        'datasets',
        'facebook-wosn2009',
        'nodes',
        '7',
        'wall-events',
      ]);
      expect(sent.url.queryParameters, {
        'direction': 'sent',
        'limit': '50',
        'cursor': 'a+b/c= d',
      });
      expect(page.items.single['content_available'], isFalse);
      expect(page.nextCursor, isNull);
    });
  });

  group('paginación', () {
    test('recorre dos páginas con cursor opaco y decodifica UTF-8', () async {
      final cursors = <String?>[];
      final repo = OutsparkRepository(
        ApiClient(
          baseUrl: localApi,
          demoUser: 'ana',
          client: MockClient((request) async {
            final cursor = request.url.queryParameters['cursor'];
            cursors.add(cursor);
            expect(request.url.queryParameters['limit'], '50');
            return cursor == null
                ? jsonResponse({
                    'items': [
                      {
                        'community_id': 'diseno',
                        'name': 'Diseño',
                        'status': 'ACTIVE',
                      },
                    ],
                    'next_cursor': 'eyJrIjoiZGlzZW5vIn0=/+',
                  })
                : jsonResponse({
                    'items': [
                      {
                        'community_id': 'tecnologia',
                        'name': 'Tecnología',
                        'status': 'ACTIVE',
                      },
                    ],
                    'next_cursor': null,
                  });
          }),
        ),
      );

      final communities = await repo.listCommunities();

      expect(cursors, [null, 'eyJrIjoiZGlzZW5vIn0=/+']);
      expect(communities.map((c) => c.id), ['diseno', 'tecnologia']);
      expect(communities.map((c) => c.name), ['Diseño', 'Tecnología']);
    });

    test('se detiene si el servidor repite un cursor', () async {
      var calls = 0;
      final repo = OutsparkRepository(
        ApiClient(
          baseUrl: localApi,
          demoUser: 'diego',
          client: MockClient((_) async {
            calls++;
            return jsonResponse({
              'items': [
                {'contact_id': 'bruno', 'status': 'ACTIVE'},
              ],
              'next_cursor': 'otra-vez',
            });
          }),
        ),
      );

      await expectLater(
        repo.listContacts(),
        throwsA(apiError(code: 'pagination_loop')),
      );
      expect(calls, 2);
    });
  });

  group('errores', () {
    test(
      '409 conserva código, mensaje y x-request-id sin reintentar',
      () async {
        var calls = 0;
        final repo = OutsparkRepository(
          ApiClient(
            baseUrl: localApi,
            demoUser: 'ana',
            client: MockClient((_) async {
              calls++;
              return jsonResponse(
                {
                  'error': {
                    'code': 'idempotency_conflict',
                    'message': 'La clave ya se usó con otro contenido.',
                  },
                },
                status: 409,
                headers: {'x-request-id': 'req-42'},
              );
            }),
          ),
        );

        await expectLater(
          repo.addComment('pub-1', 'Hola', idempotencyKey: 'clave-1'),
          throwsA(
            apiError(status: 409, code: 'idempotency_conflict')
                .having(
                  (e) => e.message,
                  'message',
                  'La clave ya se usó con otro contenido.',
                )
                .having((e) => e.requestId, 'requestId', 'req-42'),
          ),
        );
        expect(calls, 1);
      },
    );

    test('error sin cuerpo JSON produce un código genérico', () async {
      final client = ApiClient(
        baseUrl: localApi,
        demoUser: 'ana',
        client: MockClient((_) async => http.Response('Bad gateway', 502)),
      );

      await expectLater(
        client.request('GET', '/me'),
        throwsA(apiError(status: 502, code: 'http_502')),
      );
    });

    test(
      'JSON inválido o con otra forma se convierte en invalid_response',
      () async {
        final responses = [
          http.Response('{"profile": ', 200),
          jsonResponse(['no', 'es', 'objeto']),
        ];
        final client = ApiClient(
          baseUrl: localApi,
          demoUser: 'ana',
          client: MockClient((_) async => responses.removeAt(0)),
        );

        await expectLater(
          client.request('GET', '/me'),
          throwsA(apiError(status: 200, code: 'invalid_response')),
        );
        await expectLater(
          client.request('GET', '/me'),
          throwsA(apiError(status: 200, code: 'invalid_response')),
        );
      },
    );

    test('tipos incorrectos indican el campo afectado', () async {
      final repo = OutsparkRepository(
        ApiClient(
          baseUrl: localApi,
          demoUser: 'ana',
          client: MockClient(
            (_) async =>
                jsonResponse({...publicationJson(), 'created_at': 1760875200}),
          ),
        ),
      );

      await expectLater(
        repo.getPublication('pub-1'),
        throwsA(
          apiError(
            code: 'invalid_response',
          ).having((e) => e.message, 'message', contains('created_at')),
        ),
      );
    });

    test('timeout', () async {
      final client = ApiClient(
        baseUrl: localApi,
        demoUser: 'ana',
        timeout: const Duration(milliseconds: 20),
        client: MockClient((_) => Completer<http.Response>().future),
      );

      await expectLater(
        client.request('GET', '/me'),
        throwsA(apiError(code: 'timeout')),
      );
    });

    test('fallo de red', () async {
      final client = ApiClient(
        baseUrl: localApi,
        demoUser: 'ana',
        client: MockClient(
          (_) => throw http.ClientException('Connection refused'),
        ),
      );

      await expectLater(
        client.request('GET', '/me'),
        throwsA(apiError(code: 'network')),
      );
    });

    test('204 devuelve un objeto vacío', () async {
      final client = ApiClient(
        baseUrl: localApi,
        demoUser: 'diego',
        client: MockClient((_) async => http.Response('', 204)),
      );

      expect(await client.request('DELETE', '/me/contacts/bruno'), isEmpty);
    });
  });

  group('modelos', () {
    test(
      'un original retirado conserva body null sin usar el mensaje',
      () async {
        final repo = OutsparkRepository(
          ApiClient(
            baseUrl: localApi,
            demoUser: 'ana',
            client: MockClient(
              (_) async => jsonResponse({
                ...publicationJson(body: null, status: 'REMOVED'),
                'message': 'Este original fue retirado.',
              }),
            ),
          ),
        );

        final publication = await repo.getPublication('pub-1');

        expect(publication.status, 'REMOVED');
        expect(publication.body, isNull);
        expect(publication.rootEventId, 'pub-1/root');
      },
    );

    test(
      'rutas de procedencia que comparten prefijo se mantienen separadas',
      () async {
        final repo = OutsparkRepository(
          ApiClient(
            baseUrl: localApi,
            demoUser: 'diego',
            client: MockClient(
              (_) async => jsonResponse({
                'snapshot_id': 'snap-1',
                'viewer_id': 'diego',
                'publication': publicationJson(),
                'routes': [
                  {
                    'source': {
                      'event_id': 'pub-1/root/bruno',
                      'reasons': [
                        {
                          'type': 'contact',
                          'text': 'Bruno lo republicó.',
                          'contact_id': 'bruno',
                        },
                      ],
                    },
                    'events': [
                      eventJson('pub-1/root', 'ana', null),
                      eventJson('pub-1/root/bruno', 'bruno', 'pub-1/root'),
                    ],
                  },
                  {
                    'source': {
                      'event_id': 'pub-1/root/bruno/carla',
                      'reasons': [
                        {
                          'type': 'contact',
                          'text': 'Carla lo republicó.',
                          'contact_id': 'carla',
                        },
                      ],
                    },
                    'events': [
                      eventJson('pub-1/root', 'ana', null),
                      eventJson('pub-1/root/bruno', 'bruno', 'pub-1/root'),
                      eventJson(
                        'pub-1/root/bruno/carla',
                        'carla',
                        'pub-1/root/bruno',
                      ),
                    ],
                  },
                ],
                'tree': {
                  'dfs': [
                    {'event_id': 'pub-1/root', 'depth': 0},
                    {'event_id': 'pub-1/root/bruno', 'depth': 1},
                    {'event_id': 'pub-1/root/bruno/carla', 'depth': 2},
                  ],
                  'event_count': 3,
                },
              }),
            ),
          ),
        );

        final provenance = await repo.provenance('snap-1', 'pub-1');

        expect(provenance.eventCount, 3);
        expect(provenance.routes, hasLength(2));
        final [short, long] = provenance.routes;
        expect(short.source.eventId, 'pub-1/root/bruno');
        expect(short.source.reasons.single.contactId, 'bruno');
        expect(short.events.map((e) => e.actorId), ['ana', 'bruno']);
        expect(long.source.eventId, 'pub-1/root/bruno/carla');
        expect(long.events.map((e) => e.actorId), ['ana', 'bruno', 'carla']);
        expect(long.events.first.parentEventId, isNull);
        expect(long.events.last.parentEventId, 'pub-1/root/bruno');
        expect(
          () => short.events.add(long.events.last),
          throwsUnsupportedError,
        );
      },
    );

    test(
      'la comparación conserva ambos snapshots y el hash de candidatos',
      () async {
        final repo = OutsparkRepository(
          ApiClient(
            baseUrl: localApi,
            demoUser: 'diego',
            client: MockClient(
              (_) async => jsonResponse({
                'feeds': {
                  'chronological': snapshotJson('snap-c', 'chronological'),
                  'diverse': snapshotJson('snap-d', 'diverse'),
                },
                'candidate_hash': 'abc',
              }, status: 201),
            ),
          ),
        );

        final comparison = await repo.compareFeeds();

        expect(comparison.candidateHash, 'abc');
        expect(comparison.chronological.snapshotId, 'snap-c');
        expect(comparison.diverse.strategy, 'diverse');
        final card = comparison.diverse.cards.single;
        expect(card.selectionReason, 'Actividad reciente.');
        expect(card.sources.single.reasons.single.type, 'contact');
        expect(
          comparison.diverse.generatedAt,
          DateTime.utc(2026, 10, 19, 12, 5),
        );
        expect(
          () => comparison.diverse.selection['extra'] = 1,
          throwsUnsupportedError,
        );
      },
    );
  });
}

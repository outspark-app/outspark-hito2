import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:outspark_app/application/session_controller.dart';
import 'package:outspark_app/data/api_client.dart';
import 'package:outspark_app/data/outspark_repository.dart';
import 'package:outspark_app/domain/models.dart';
import 'package:outspark_app/features/publication_history.dart';
import 'package:outspark_app/ui/design_system.dart';

Map<String, Object?> original(String id, {bool removed = false}) => {
  'publication_id': id,
  'author_id': 'ana',
  'community_id': 'diseno',
  if (!removed) 'body': 'Idea $id',
  'status': removed ? 'REMOVED' : 'ACTIVE',
  'visibility': 'public',
  'topic_ids': ['diseno'],
  'root_event_id': '$id/root',
  'created_at': '2026-10-19T12:00:00Z',
};
http.Response json(Object body, [int status = 200]) => http.Response.bytes(
  utf8.encode(jsonEncode(body)),
  status,
  headers: {'content-type': 'application/json'},
);

SessionController sessionFor(http.Client client) =>
    SessionController(
        OutsparkRepository(
          ApiClient(
            baseUrl: Uri.parse('http://127.0.0.1:18080/api'),
            demoUser: 'ana',
            client: client,
          ),
        ),
      )
      ..profile = Profile(
        uid: 'ana',
        name: 'Ana',
        topicIds: ['diseno'],
        preferencesVersion: 1,
      )
      ..communities = [Community(id: 'diseno', name: 'Diseño')]
      ..topics = [const Topic(id: 'diseno', name: 'Diseño')];

Future<void> tap(WidgetTester tester, String text) async {
  final target = find.text(text);
  await tester.ensureVisible(target);
  await tester.tap(target);
  await tester.pumpAndSettle();
}

void main() {
  testWidgets(
    'historial conserva página ante error, reintenta cursor y navega por páginas vacías',
    (tester) async {
      final semantics = tester.ensureSemantics();
      try {
        final requested = <String?>[];
        var failed = false;
        final session = sessionFor(
          MockClient((request) async {
            expect(request.url.path, '/api/me/publications');
            expect(request.headers['X-Demo-User'], 'ana');
            final cursor = request.url.queryParameters['cursor'];
            requested.add(cursor);
            if (cursor == null) {
              return json({
                'items': [original('primera')],
                'next_cursor': 'first',
              });
            }
            if (cursor == 'first' && !failed) {
              failed = true;
              return json({
                'error': {
                  'code': 'storage_unavailable',
                  'message': 'Intenta de nuevo.',
                },
              }, 503);
            }
            if (cursor == 'first') {
              return json({'items': [], 'next_cursor': 'older'});
            }
            if (cursor == 'older') {
              return json({
                'items': [original('antigua', removed: true)],
                'next_cursor': null,
              });
            }
            throw StateError('Cursor inesperado');
          }),
        );
        addTearDown(session.dispose);
        await tester.pumpWidget(
          MaterialApp(
            theme: outsparkTheme(),
            home: Scaffold(
              body: SingleChildScrollView(
                child: PublicationHistory(
                  session: session,
                  onOriginal: (_) {},
                  onCompose: () {},
                ),
              ),
            ),
          ),
        );
        await tester.pumpAndSettle();
        expect(find.text('Idea primera'), findsOneWidget);
        expect(find.bySemanticsLabel('Idea primera'), findsOneWidget);
        await tap(tester, 'Publicaciones anteriores');
        expect(find.text('Idea primera'), findsOneWidget);
        expect(find.text('No pudimos completar la consulta'), findsOneWidget);
        await tap(tester, 'Volver a intentar');
        expect(find.text('Tu actividad sigue más atrás.'), findsOneWidget);
        expect(find.text('Idea primera'), findsNothing);
        await tap(tester, 'Publicaciones anteriores');
        expect(find.text('Publicación retirada'), findsOneWidget);
        expect(find.text('Idea antigua'), findsNothing);
        await tap(tester, 'Más recientes');
        expect(find.text('Tu actividad sigue más atrás.'), findsOneWidget);
        await tap(tester, 'Publicaciones anteriores');
        expect(find.text('Publicación retirada'), findsOneWidget);
        expect(requested, [null, 'first', 'first', 'older', 'first', 'older']);
        expect(tester.takeException(), isNull);
      } finally {
        semantics.dispose();
      }
    },
  );

  testWidgets(
    'un original no disponible se informa y permite continuar sin falso estado vacío',
    (tester) async {
      final session = sessionFor(
        MockClient(
          (_) async => json({
            'items': [],
            'next_cursor': 'next',
            'unavailable_count': 1,
          }),
        ),
      );
      addTearDown(session.dispose);
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: PublicationHistory(
                session: session,
                onOriginal: (_) {},
                onCompose: () {},
              ),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(
        find.textContaining('1 originales sin datos disponibles'),
        findsOneWidget,
      );
      expect(find.text('Publicaciones anteriores'), findsOneWidget);
      expect(find.text('Una primera idea abre el camino.'), findsNothing);
    },
  );
}

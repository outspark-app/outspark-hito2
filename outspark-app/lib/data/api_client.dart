import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

/// Error HTTP, de red, de tiempo o de formato al hablar con la API.
///
/// [statusCode] es `null` cuando no hubo respuesta (timeout o red) o cuando
/// el error se detectó al interpretar un cuerpo ya recibido.
final class ApiException implements Exception {
  const ApiException({
    this.statusCode,
    required this.code,
    required this.message,
    this.requestId,
  });

  final int? statusCode;
  final String code;
  final String message;
  final String? requestId;

  @override
  String toString() => message;
}

/// Cliente JSON mínimo para la API de Outspark.
///
/// No reintenta automáticamente. La identidad viaja solo en encabezados:
/// `X-Demo-User` (únicamente contra hosts loopback) o `Authorization: Bearer`.
class ApiClient {
  factory ApiClient({
    required Uri baseUrl,
    String? demoUser,
    String? bearerToken,
    Future<String?> Function()? tokenProvider,
    http.Client? client,
    Duration timeout = const Duration(seconds: 20),
  }) {
    _checkBaseUrl(baseUrl);
    if ((demoUser != null && (bearerToken != null || tokenProvider != null)) ||
        (bearerToken != null && tokenProvider != null)) {
      throw ArgumentError('Usa demoUser o bearerToken, no ambos.');
    }
    if (demoUser != null) {
      _checkHeaderValue(demoUser, 'demoUser');
      if (!_isLoopback(baseUrl.host)) {
        throw ArgumentError.value(
          baseUrl.toString(),
          'baseUrl',
          'X-Demo-User solo se permite contra localhost, 127.0.0.0/8 o ::1',
        );
      }
    }
    if (bearerToken != null && !_tokenValue.hasMatch(bearerToken)) {
      throw ArgumentError.value(
        '***',
        'bearerToken',
        'Debe contener solo caracteres ASCII visibles',
      );
    }
    if (timeout <= Duration.zero) {
      throw ArgumentError.value(timeout, 'timeout', 'Debe ser positivo');
    }
    return ApiClient._(
      baseUrl,
      demoUser,
      bearerToken,
      tokenProvider,
      client ?? http.Client(),
      ownsClient: client == null,
      timeout: timeout,
    );
  }

  ApiClient._(
    this.baseUrl,
    this._demoUser,
    this._bearerToken,
    this._tokenProvider,
    this._client, {
    required bool ownsClient,
    required this.timeout,
  }) : _ownsClient = ownsClient,
       _basePath = baseUrl.path.endsWith('/')
           ? baseUrl.path.substring(0, baseUrl.path.length - 1)
           : baseUrl.path;

  /// URL base, incluido el prefijo `/api`.
  final Uri baseUrl;
  final Duration timeout;
  final String? _demoUser;
  final String? _bearerToken;
  final Future<String?> Function()? _tokenProvider;
  final http.Client _client;
  final bool _ownsClient;
  final String _basePath;

  static const _methods = {'GET', 'POST', 'PUT', 'PATCH', 'DELETE'};
  static const _identityFields = {'author_id', 'viewer_id'};

  /// Envía una petición y devuelve el objeto JSON de la respuesta.
  ///
  /// [path] es relativo a [baseUrl] y debe llevar cada identificador ya
  /// codificado con [Uri.encodeComponent]. Una respuesta 204 o vacía devuelve
  /// un mapa vacío.
  Future<Map<String, dynamic>> request(
    String method,
    String path, {
    Map<String, String>? query,
    Map<String, dynamic>? body,
    String? idempotencyKey,
    Duration? requestTimeout,
  }) async {
    final deadline = requestTimeout ?? timeout;
    final verb = method.toUpperCase();
    if (!_methods.contains(verb)) {
      throw ArgumentError.value(method, 'method', 'Método HTTP no admitido');
    }
    if (idempotencyKey != null) {
      _checkHeaderValue(idempotencyKey, 'idempotencyKey');
    }
    if (body != null && body.keys.any(_identityFields.contains)) {
      throw ArgumentError.value(
        body.keys.where(_identityFields.contains).join(', '),
        'body',
        'La identidad la fija el servidor; no se envía en el JSON',
      );
    }

    final token = _tokenProvider == null
        ? _bearerToken
        : await _tokenProvider();
    if (_tokenProvider != null &&
        (token == null || !_tokenValue.hasMatch(token))) {
      throw const ApiException(
        statusCode: 401,
        code: 'authentication_required',
        message: 'Vuelve a iniciar sesión en Outspark.',
      );
    }
    final abort = Completer<void>();
    final request =
        http.AbortableRequest(
            verb,
            _resolve(path, query),
            abortTrigger: abort.future,
          )
          // Una redirección podría reenviar la identidad a otro origen.
          ..followRedirects = false
          ..headers.addAll({
            'Accept': 'application/json',
            if (body != null) 'Content-Type': 'application/json; charset=utf-8',
            if (_demoUser != null) 'X-Demo-User': _demoUser,
            if (token != null) 'Authorization': 'Bearer $token',
            'Idempotency-Key': ?idempotencyKey,
          });
    if (body != null) request.bodyBytes = utf8.encode(jsonEncode(body));

    final http.Response response;
    try {
      response = await _client
          .send(request)
          .then(http.Response.fromStream)
          .timeout(
            deadline,
            onTimeout: () {
              if (!abort.isCompleted) abort.complete();
              throw TimeoutException(null, deadline);
            },
          );
    } on TimeoutException {
      throw ApiException(
        code: 'timeout',
        message: 'El servidor no respondió en ${deadline.inMilliseconds} ms.',
      );
    } on http.ClientException catch (error) {
      throw ApiException(
        code: 'network',
        message: 'No se pudo conectar con el servidor: ${error.message}',
      );
    }
    return _decode(response);
  }

  /// Cierra el cliente HTTP si lo creó este [ApiClient].
  void close() {
    if (_ownsClient) _client.close();
  }

  Uri _resolve(String path, Map<String, String>? query) {
    if (!path.startsWith('/') || path.contains('?') || path.contains('#')) {
      throw ArgumentError.value(
        path,
        'path',
        'Debe empezar por "/" y no incluir query ni fragmento',
      );
    }
    // Uri normaliza "." y ".."; un identificador así cambiaría la ruta.
    final dotSegment = path
        .split('/')
        .map(Uri.decodeComponent)
        .any((s) => s == '.' || s == '..');
    if (dotSegment) {
      throw ArgumentError.value(
        path,
        'path',
        'No admite segmentos "." ni ".."',
      );
    }
    return baseUrl.replace(
      path: '$_basePath$path',
      queryParameters: query == null || query.isEmpty ? null : query,
    );
  }

  static Map<String, dynamic> _decode(http.Response response) {
    final status = response.statusCode;
    final requestId = response.headers['x-request-id'];
    final success = status >= 200 && status < 300;

    if (success && (status == 204 || response.bodyBytes.isEmpty)) {
      return const <String, dynamic>{};
    }

    Object? decoded;
    try {
      // FastAPI no declara charset; el contrato es JSON UTF-8.
      decoded = jsonDecode(utf8.decode(response.bodyBytes));
    } on FormatException {
      decoded = null;
    }

    if (success) {
      if (decoded is Map<String, dynamic>) return decoded;
      throw ApiException(
        statusCode: status,
        code: 'invalid_response',
        message:
            'El servidor devolvió una respuesta que no es un objeto JSON válido.',
        requestId: requestId,
      );
    }

    final error = decoded is Map<String, dynamic> ? decoded['error'] : null;
    final code = error is Map<String, dynamic> ? error['code'] : null;
    final message = error is Map<String, dynamic> ? error['message'] : null;
    throw ApiException(
      statusCode: status,
      code: code is String && code.isNotEmpty ? code : 'http_$status',
      message: message is String && message.isNotEmpty
          ? message
          : _defaultMessage(status),
      requestId: requestId,
    );
  }

  static String _defaultMessage(int status) => switch (status) {
    400 => 'Datos inválidos.',
    401 => 'Se requiere una sesión.',
    403 => 'No tienes permiso para esta operación.',
    404 => 'El recurso no existe.',
    409 => 'La operación entra en conflicto con el estado actual.',
    410 => 'El contenido fue retirado.',
    413 => 'La solicitud es demasiado grande.',
    422 => 'No se pudo completar la consulta dentro de sus límites.',
    503 => 'El servicio de persistencia no está disponible.',
    >= 500 => 'Error interno del servidor.',
    >= 300 && < 400 => 'Redirección no admitida ($status).',
    _ => 'Respuesta HTTP inesperada ($status).',
  };

  static void _checkBaseUrl(Uri url) {
    if (!(url.isScheme('http') || url.isScheme('https')) || url.host.isEmpty) {
      throw ArgumentError.value(
        url.toString(),
        'baseUrl',
        'Debe ser una URL http(s) absoluta',
      );
    }
    if (url.hasQuery || url.hasFragment) {
      throw ArgumentError.value(
        url.toString(),
        'baseUrl',
        'No admite query ni fragmento',
      );
    }
  }

  static final _headerValue = RegExp(r'^[\x21-\x7E]{1,128}$');
  static final _tokenValue = RegExp(r'^[\x21-\x7E]+$');

  static void _checkHeaderValue(String value, String name) {
    if (!_headerValue.hasMatch(value)) {
      throw ArgumentError.value(
        value,
        name,
        'Debe tener de 1 a 128 caracteres ASCII visibles',
      );
    }
  }

  static bool _isLoopback(String host) {
    final h = host.toLowerCase();
    if (h == 'localhost' || h == '::1' || h == '0:0:0:0:0:0:0:1') return true;
    final octets = h.split('.');
    return octets.length == 4 &&
        octets.first == '127' &&
        octets.every((o) {
          final n = int.tryParse(o);
          return n != null && n >= 0 && n <= 255 && o == '$n';
        });
  }
}

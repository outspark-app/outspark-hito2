import 'package:web/web.dart' as web;

String? readSession(String key) {
  try {
    return web.window.sessionStorage.getItem(key);
  } catch (_) {
    return null;
  }
}

void writeSession(String key, String value) {
  try {
    web.window.sessionStorage.setItem(key, value);
  } catch (_) {
    /* Storage is optional. */
  }
}

void openLocation(String url) => web.window.location.assign(url);

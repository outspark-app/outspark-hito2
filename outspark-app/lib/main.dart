import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/material.dart';
import 'package:flutter/semantics.dart';
import 'outspark_app.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  SemanticsBinding.instance.ensureSemantics();
  const demoMode = bool.fromEnvironment('DEMO_MODE');
  const project = String.fromEnvironment('FIREBASE_PROJECT_ID');
  if (!demoMode && project.isNotEmpty) {
    await Firebase.initializeApp(
      options: const FirebaseOptions(
        apiKey: String.fromEnvironment('FIREBASE_API_KEY'),
        appId: String.fromEnvironment('FIREBASE_APP_ID'),
        messagingSenderId: String.fromEnvironment('FIREBASE_SENDER_ID'),
        projectId: project,
        authDomain: String.fromEnvironment('FIREBASE_AUTH_DOMAIN'),
      ),
    );
  }
  runApp(
    const OutsparkApp(
      apiBaseUrl: String.fromEnvironment('API_BASE_URL', defaultValue: '/api'),
      demoMode: demoMode,
      firebaseEnabled: !demoMode && project != '',
      landingUrl: String.fromEnvironment('LANDING_URL', defaultValue: '/'),
    ),
  );
}

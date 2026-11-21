import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/material.dart';

import '../ui/design_system.dart';

class FirebaseSignIn extends StatefulWidget {
  const FirebaseSignIn({super.key});

  @override
  State<FirebaseSignIn> createState() => _FirebaseSignInState();
}

class _FirebaseSignInState extends State<FirebaseSignIn> {
  final email = TextEditingController();
  final password = TextEditingController();
  final form = GlobalKey<FormState>();
  bool signingUp = false;
  bool submitting = false;
  String? error;

  @override
  void dispose() {
    email.dispose();
    password.dispose();
    super.dispose();
  }

  Future<void> submit() async {
    if (submitting || !form.currentState!.validate()) return;
    setState(() {
      submitting = true;
      error = null;
    });
    try {
      final auth = FirebaseAuth.instance;
      if (signingUp) {
        await auth.createUserWithEmailAndPassword(
          email: email.text.trim(),
          password: password.text,
        );
      } else {
        await auth.signInWithEmailAndPassword(
          email: email.text.trim(),
          password: password.text,
        );
      }
    } on FirebaseAuthException catch (failure) {
      if (!mounted) return;
      setState(() {
        error = switch (failure.code) {
          'invalid-email' => 'Escribe un correo válido.',
          'email-already-in-use' => 'Ya existe una cuenta con ese correo.',
          'weak-password' => 'Elige una contraseña más segura.',
          'too-many-requests' => 'Hubo demasiados intentos. Intenta más tarde.',
          'network-request-failed' => 'No hay conexión. Vuelve a intentar.',
          _ =>
            'No se pudo completar el acceso. Revisa tus datos e intenta de nuevo.',
        };
      });
    } finally {
      if (mounted) setState(() => submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    body: SafeArea(
      child: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 480),
            child: PaperPanel(
              child: AutofillGroup(
                child: Form(
                  key: form,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      const Brand(),
                      const SizedBox(height: 24),
                      Text(
                        signingUp ? 'Crea tu cuenta' : 'Inicia sesión',
                        style: Theme.of(context).textTheme.headlineSmall,
                      ),
                      const SizedBox(height: 16),
                      TextFormField(
                        controller: email,
                        enabled: !submitting,
                        decoration: const InputDecoration(
                          labelText: 'Correo electrónico',
                        ),
                        keyboardType: TextInputType.emailAddress,
                        autofillHints: const [AutofillHints.email],
                        textInputAction: TextInputAction.next,
                        validator: (value) => (value ?? '').trim().contains('@')
                            ? null
                            : 'Escribe un correo válido.',
                      ),
                      const SizedBox(height: 12),
                      TextFormField(
                        controller: password,
                        enabled: !submitting,
                        decoration: const InputDecoration(
                          labelText: 'Contraseña',
                        ),
                        obscureText: true,
                        autofillHints: [
                          signingUp
                              ? AutofillHints.newPassword
                              : AutofillHints.password,
                        ],
                        onFieldSubmitted: (_) => submit(),
                        validator: (value) =>
                            (value ?? '').length >= (signingUp ? 6 : 1)
                            ? null
                            : signingUp
                            ? 'Escribe al menos seis caracteres.'
                            : 'Escribe tu contraseña.',
                      ),
                      if (error != null) ...[
                        const SizedBox(height: 12),
                        Semantics(liveRegion: true, child: Text(error!)),
                      ],
                      const SizedBox(height: 20),
                      FilledButton(
                        onPressed: submitting ? null : submit,
                        child: Text(
                          submitting
                              ? 'Conectando…'
                              : signingUp
                              ? 'Crear cuenta'
                              : 'Entrar',
                        ),
                      ),
                      TextButton(
                        onPressed: submitting
                            ? null
                            : () => setState(() {
                                signingUp = !signingUp;
                                error = null;
                              }),
                        child: Text(
                          signingUp ? 'Ya tengo cuenta' : 'Crear una cuenta',
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    ),
  );
}

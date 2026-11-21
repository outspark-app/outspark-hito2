import 'package:flutter/material.dart';

const ink = Color(0xFF1C1E21);
const muted = Color(0xFF565D68);
const paper = Color(0xFFFFFFFF);
const ground = Color(0xFFF5F6F8);
const yellow = Color(0xFFF5D76E);
const line = Color(0xFFDDE1E6);

ThemeData outsparkTheme() => ThemeData(
  useMaterial3: true,
  fontFamily: 'Arial',
  colorScheme: ColorScheme.fromSeed(
    seedColor: yellow,
    primary: ink,
    secondary: yellow,
    surface: paper,
    onSurface: ink,
    error: const Color(0xFF9E3029),
  ),
  scaffoldBackgroundColor: ground,
  textTheme: const TextTheme(
    headlineLarge: TextStyle(
      fontSize: 36,
      height: 1.13,
      fontWeight: FontWeight.w700,
      letterSpacing: -1,
    ),
    headlineMedium: TextStyle(
      fontSize: 28,
      height: 1.2,
      fontWeight: FontWeight.w700,
      letterSpacing: -.6,
    ),
    titleLarge: TextStyle(fontSize: 22, fontWeight: FontWeight.w700),
    titleMedium: TextStyle(fontSize: 17, fontWeight: FontWeight.w600),
    bodyLarge: TextStyle(fontSize: 16, height: 1.55),
    bodyMedium: TextStyle(fontSize: 14, height: 1.45),
    bodySmall: TextStyle(fontSize: 12, height: 1.5, color: muted),
  ),
  dividerColor: line,
  inputDecorationTheme: InputDecorationTheme(
    filled: true,
    fillColor: paper,
    alignLabelWithHint: true,
    border: OutlineInputBorder(
      borderRadius: BorderRadius.circular(12),
      borderSide: const BorderSide(color: line),
    ),
    enabledBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(12),
      borderSide: const BorderSide(color: line),
    ),
    focusedBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(12),
      borderSide: const BorderSide(color: ink, width: 2),
    ),
    contentPadding: const EdgeInsets.all(16),
  ),
  filledButtonTheme: FilledButtonThemeData(
    style: FilledButton.styleFrom(
      backgroundColor: yellow,
      foregroundColor: ink,
      minimumSize: const Size(44, 48),
      padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 14),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      textStyle: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700),
    ),
  ),
  outlinedButtonTheme: OutlinedButtonThemeData(
    style: OutlinedButton.styleFrom(
      foregroundColor: ink,
      minimumSize: const Size(44, 46),
      side: const BorderSide(color: line),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
    ),
  ),
  chipTheme: ChipThemeData(
    backgroundColor: ground,
    selectedColor: yellow.withValues(alpha: .45),
    side: const BorderSide(color: line),
    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
  ),
  snackBarTheme: const SnackBarThemeData(
    behavior: SnackBarBehavior.floating,
    backgroundColor: ink,
  ),
);

String personName(String id) =>
    const {
      'ana': 'Ana',
      'bruno': 'Bruno',
      'carla': 'Carla',
      'diego': 'Diego',
      'elena': 'Elena',
    }[id] ??
    (id.startsWith('fb-') ? 'Cuenta de simulación ${id.substring(3)}' : id);

String moment(DateTime date) {
  // Timestamps remain server-owned; display in the project's Lima time zone.
  final lima = date.toUtc().subtract(const Duration(hours: 5));
  return '${lima.day}/${lima.month}/${lima.year} · ${lima.hour.toString().padLeft(2, '0')}:${lima.minute.toString().padLeft(2, '0')}';
}

class Brand extends StatelessWidget {
  const Brand({super.key, this.compact = false});
  final bool compact;
  @override
  Widget build(BuildContext context) => Semantics(
    label: 'Outspark',
    child: Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Image.asset(
          'assets/outspark.png',
          width: 31,
          height: 31,
          excludeFromSemantics: true,
        ),
        if (!compact) ...[
          const SizedBox(width: 10),
          const Text(
            'Outspark',
            style: TextStyle(
              fontSize: 25,
              fontWeight: FontWeight.w800,
              letterSpacing: -.8,
            ),
          ),
        ],
      ],
    ),
  );
}

class PersonAvatar extends StatelessWidget {
  const PersonAvatar(this.id, {super.key, this.size = 42});
  final String id;
  final double size;
  @override
  Widget build(BuildContext context) {
    final color = const [
      Color(0xFFE6DFF2),
      Color(0xFFDDE7F1),
      Color(0xFFF1DFDA),
      Color(0xFFE4E5D9),
      Color(0xFFD9E8DF),
    ][id.codeUnits.fold(0, (a, b) => a + b) % 5];
    final name = personName(id);
    return ExcludeSemantics(
      child: CircleAvatar(
        radius: size / 2,
        backgroundColor: color,
        child: Text(
          name.substring(0, name.length < 2 ? name.length : 2).toUpperCase(),
          style: TextStyle(
            color: ink,
            fontSize: size * .3,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
    );
  }
}

class PaperPanel extends StatelessWidget {
  const PaperPanel({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(24),
    this.color = paper,
  });
  final Widget child;
  final EdgeInsetsGeometry padding;
  final Color color;
  @override
  Widget build(BuildContext context) => DecoratedBox(
    decoration: BoxDecoration(
      color: color,
      borderRadius: BorderRadius.circular(16),
      border: Border.all(color: line),
    ),
    child: Padding(padding: padding, child: child),
  );
}

class PageHeading extends StatelessWidget {
  const PageHeading(this.title, this.description, {super.key, this.action});
  final String title, description;
  final Widget? action;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 28),
    child: Wrap(
      alignment: WrapAlignment.spaceBetween,
      crossAxisAlignment: WrapCrossAlignment.center,
      spacing: 24,
      runSpacing: 16,
      children: [
        ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 690),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Semantics(
                header: true,
                child: Text(
                  title,
                  style: Theme.of(context).textTheme.headlineLarge,
                ),
              ),
              const SizedBox(height: 10),
              Text(
                description,
                style: const TextStyle(color: muted, fontSize: 16, height: 1.5),
              ),
            ],
          ),
        ),
        ?action,
      ],
    ),
  );
}

class Recovery extends StatelessWidget {
  const Recovery({super.key, required this.message, required this.retry});
  final String message;
  final VoidCallback retry;
  @override
  Widget build(BuildContext context) => PaperPanel(
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Icon(Icons.cloud_off_outlined, size: 32),
        const SizedBox(height: 16),
        Text(
          'No pudimos completar la consulta',
          style: Theme.of(context).textTheme.titleLarge,
        ),
        const SizedBox(height: 8),
        ReadableText(message),
        const SizedBox(height: 16),
        OutlinedButton.icon(
          onPressed: retry,
          icon: const Icon(Icons.refresh),
          label: const Text('Volver a intentar'),
        ),
      ],
    ),
  );
}

class LoadingContent extends StatelessWidget {
  const LoadingContent({super.key});
  @override
  Widget build(BuildContext context) => Semantics(
    label: 'Cargando conversaciones',
    liveRegion: true,
    child: Column(
      children: List.generate(
        3,
        (i) => Container(
          height: 150,
          margin: const EdgeInsets.only(bottom: 18),
          decoration: BoxDecoration(
            color: const Color(0xFFE7E9EC),
            borderRadius: BorderRadius.circular(16),
          ),
        ),
      ),
    ),
  );
}

String formatCount(Object? value) => (value ?? 0).toString().replaceAllMapped(
  RegExp(r'(\d)(?=(\d{3})+$)'),
  (m) => '${m[1]} ',
);

/// Expose selectable prose as readable content, rather than an empty disabled
/// browser text field in Flutter web's generated accessibility tree.
class ReadableText extends StatelessWidget {
  const ReadableText(this.text, {super.key, this.style});
  final String text;
  final TextStyle? style;
  @override
  Widget build(BuildContext context) => Semantics(
    container: true,
    label: text,
    child: ExcludeSemantics(child: SelectableText(text, style: style)),
  );
}

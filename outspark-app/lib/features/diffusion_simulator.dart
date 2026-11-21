import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../application/session_controller.dart';
import '../data/api_client.dart';
import '../domain/models.dart';
import '../ui/design_system.dart';

class DiffusionSimulator extends StatefulWidget {
  const DiffusionSimulator({
    super.key,
    required this.session,
    required this.publication,
  });

  final SessionController session;
  final Publication publication;

  @override
  State<DiffusionSimulator> createState() => _DiffusionSimulatorState();
}

class _DiffusionSimulatorState extends State<DiffusionSimulator> {
  final origin = TextEditingController();
  final filter = TextEditingController();
  final selected = <int>{};
  int slots = 3, hops = 2;
  int? lastChange;
  DiffusionComparison? result;
  bool dirty = false, busy = false, calculatingCustom = false;
  String? error;

  @override
  void initState() {
    super.initState();
    final uid = widget.session.profile?.uid ?? '';
    origin.text = RegExp(r'^fb-(\d+)$').firstMatch(uid)?.group(1) ?? '1';
    calculate();
  }

  @override
  void dispose() {
    origin.dispose();
    filter.dispose();
    super.dispose();
  }

  void changeSettings(VoidCallback change) {
    setState(() {
      change();
      dirty = true;
      selected.clear();
      lastChange = null;
      error = null;
      filter.clear();
    });
  }

  Future<void> calculate({bool custom = false}) async {
    if (busy) return;
    final originId = int.tryParse(origin.text);
    if (originId == null || originId < 0 || originId >= 1000000000000) {
      setState(() {
        calculatingCustom = false;
        error = 'Escribe el número de un perfil histórico.';
      });
      return;
    }
    final contacts = custom ? (selected.toList()..sort()) : null;
    final previous = result?.custom?.reachable;
    setState(() {
      busy = true;
      calculatingCustom = custom;
      error = null;
    });
    try {
      final compared = await widget.session.repository.simulateDiffusion(
        widget.publication.publicationId,
        origin: originId,
        hops: hops,
        slots: slots,
        contacts: contacts,
      );
      if (!mounted) return;
      setState(() {
        result = compared;
        dirty = false;
        lastChange = compared.custom == null || previous == null
            ? null
            : compared.custom!.reachable - previous;
      });
    } on ApiException catch (exception) {
      if (mounted) setState(() => error = exception.message);
    } catch (_) {
      if (mounted) {
        setState(
          () => error = 'No pudimos calcular el alcance. Intenta otra vez.',
        );
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Widget settings() => _StudioPanel(
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const _SectionTitle('Escenario'),
        const SizedBox(height: 17),
        LayoutBuilder(
          builder: (context, size) {
            final wide = size.maxWidth >= 700;
            final half = (size.maxWidth - 12) / 2;
            return Wrap(
              spacing: 12,
              runSpacing: 14,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                SizedBox(
                  width: wide ? 238 : size.maxWidth,
                  child: TextField(
                    controller: origin,
                    readOnly: busy,
                    decoration: const InputDecoration(
                      labelText: 'Perfil histórico',
                      prefixIcon: Icon(Icons.person_outline_rounded),
                    ),
                    keyboardType: TextInputType.number,
                    inputFormatters: [
                      FilteringTextInputFormatter.digitsOnly,
                      LengthLimitingTextInputFormatter(12),
                    ],
                    onChanged: (_) => changeSettings(() {}),
                    onSubmitted: (_) => calculate(),
                  ),
                ),
                SizedBox(
                  width: wide ? 132 : half,
                  child: _numberField('Contactos', slots, 10, (value) {
                    slots = value;
                  }),
                ),
                SizedBox(
                  width: wide ? 132 : half,
                  child: _numberField('Saltos', hops, 3, (value) {
                    hops = value;
                  }),
                ),
                SizedBox(
                  width: wide ? null : size.maxWidth,
                  child: OutlinedButton.icon(
                    onPressed: busy || (!dirty && result != null)
                        ? null
                        : () => calculate(),
                    icon: const Icon(Icons.refresh_rounded, size: 18),
                    label: const Text('Calcular planes'),
                  ),
                ),
              ],
            );
          },
        ),
        if (busy && !calculatingCustom) ...[
          const SizedBox(height: 17),
          const LinearProgressIndicator(semanticsLabel: 'Calculando alcance'),
        ],
        if (error != null && !calculatingCustom) _calculationError(),
      ],
    ),
  );

  Widget _calculationError() => Padding(
    padding: const EdgeInsets.only(top: 12),
    child: Semantics(
      liveRegion: true,
      child: Text(
        error!,
        style: TextStyle(color: Theme.of(context).colorScheme.error),
      ),
    ),
  );

  Widget _numberField(
    String label,
    int value,
    int maximum,
    ValueChanged<int> update,
  ) => DropdownButtonFormField<int>(
    initialValue: value,
    isExpanded: true,
    decoration: InputDecoration(labelText: label),
    items: [
      for (var n = 1; n <= maximum; n++)
        DropdownMenuItem(value: n, child: Text('$n')),
    ],
    onChanged: busy ? null : (n) => changeSettings(() => update(n!)),
  );

  Widget plans(DiffusionComparison comparison) {
    final difference =
        comparison.greedy.reachable - comparison.degree.reachable;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const _SectionTitle('Planes automáticos'),
        const SizedBox(height: 6),
        Semantics(
          liveRegion: true,
          child: Text(
            difference == 0
                ? 'Los dos planes estiman el mismo alcance.'
                : '${difference > 0 ? "Mayor alcance" : "Más conexiones"} estima '
                      '${formatCount(difference.abs())} perfiles más.',
            style: const TextStyle(color: muted),
          ),
        ),
        const SizedBox(height: 15),
        _StudioColumns(
          breakpoint: 640,
          first: _PlanCard(
            title: 'Más conexiones',
            description: 'Prioriza contactos con más amistades.',
            icon: Icons.hub_outlined,
            plan: comparison.degree,
            emphasis: difference < 0,
          ),
          second: _PlanCard(
            title: 'Mayor alcance',
            description: 'Prioriza contactos que amplían la cobertura.',
            icon: Icons.arrow_outward_rounded,
            plan: comparison.greedy,
            emphasis: difference > 0,
          ),
        ),
      ],
    );
  }

  Widget customPlan(DiffusionComparison comparison) {
    final query = filter.text.trim();
    final visible = comparison.contacts
        .where((c) => '${c.id}'.contains(query))
        .toList();
    final limit = comparison.contacts.length < slots
        ? comparison.contacts.length
        : slots;
    final custom = comparison.custom;
    final changed = !setEquals(selected, custom?.contacts.toSet());
    final editable = !busy && selected.isNotEmpty && changed;

    return _StudioPanel(
      warm: true,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const _SectionTitle('Mi plan'),
          const SizedBox(height: 6),
          Text(
            'Elige hasta $limit contactos de Usuario ${comparison.origin}.',
            style: const TextStyle(color: muted),
          ),
          const SizedBox(height: 18),
          _StudioColumns(
            breakpoint: 640,
            first: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                TextField(
                  controller: filter,
                  readOnly: busy,
                  decoration: const InputDecoration(
                    labelText: 'Buscar por número',
                    prefixIcon: Icon(Icons.search_rounded),
                  ),
                  keyboardType: TextInputType.number,
                  inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                  onChanged: (_) => setState(() {}),
                ),
                if (selected.isNotEmpty) ...[
                  const SizedBox(height: 10),
                  Wrap(
                    spacing: 6,
                    runSpacing: 6,
                    children: [
                      for (final id in selected)
                        InputChip(
                          label: Text('Usuario $id'),
                          deleteButtonTooltipMessage: 'Quitar usuario $id',
                          onDeleted: busy
                              ? null
                              : () => setState(() => selected.remove(id)),
                        ),
                    ],
                  ),
                ],
                const SizedBox(height: 12),
                if (visible.isEmpty)
                  const Padding(
                    padding: EdgeInsets.symmetric(vertical: 12),
                    child: Text('No hay contactos con ese número.'),
                  )
                else
                  DecoratedBox(
                    decoration: BoxDecoration(
                      color: paper,
                      border: Border.all(color: line),
                      borderRadius: BorderRadius.circular(14),
                    ),
                    child: ConstrainedBox(
                      constraints: const BoxConstraints(maxHeight: 238),
                      child: ListView.separated(
                        shrinkWrap: true,
                        primary: false,
                        padding: const EdgeInsets.symmetric(vertical: 3),
                        itemCount: visible.length,
                        separatorBuilder: (_, _) => const Divider(
                          height: 1,
                          indent: 14,
                          endIndent: 14,
                          color: line,
                        ),
                        itemBuilder: (context, index) {
                          final contact = visible[index];
                          final checked = selected.contains(contact.id);
                          return CheckboxListTile(
                            title: Text('Usuario ${contact.id}'),
                            subtitle: Text(
                              '${formatCount(contact.degree)} amistades',
                            ),
                            value: checked,
                            onChanged:
                                busy || (!checked && selected.length >= limit)
                                ? null
                                : (value) => setState(() {
                                    if (value == true) {
                                      selected.add(contact.id);
                                    } else {
                                      selected.remove(contact.id);
                                    }
                                  }),
                          );
                        },
                      ),
                    ),
                  ),
                const SizedBox(height: 14),
                Wrap(
                  spacing: 16,
                  runSpacing: 10,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    FilledButton(
                      onPressed: editable
                          ? () => calculate(custom: true)
                          : null,
                      child: const Text('Probar mi plan'),
                    ),
                    Semantics(
                      liveRegion: true,
                      child: Text(
                        selected.length == limit
                            ? '$limit de $limit. Quita uno para cambiarlo.'
                            : '${selected.length} de $limit elegidos',
                        style: const TextStyle(color: muted),
                      ),
                    ),
                  ],
                ),
                if (busy && calculatingCustom) ...[
                  const SizedBox(height: 12),
                  const LinearProgressIndicator(
                    semanticsLabel: 'Calculando mi plan',
                  ),
                ],
                if (error != null && calculatingCustom) _calculationError(),
              ],
            ),
            second: custom == null
                ? _StudioPanel(
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Icon(Icons.people_outline_rounded, color: muted),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Text(
                            'Tu alcance aparecerá después de probar tu selección.',
                            style: Theme.of(context).textTheme.bodyLarge,
                          ),
                        ),
                      ],
                    ),
                  )
                : _PlanCard(
                    title: changed
                        ? 'Último cálculo de mi plan'
                        : 'Alcance de mi plan',
                    icon: Icons.people_outline_rounded,
                    plan: custom,
                    announceReach: true,
                    note: lastChange == null ? null : _changeText(lastChange!),
                  ),
          ),
        ],
      ),
    );
  }

  String _changeText(int change) {
    if (change == 0) {
      return 'El alcance se mantuvo respecto a tu plan anterior.';
    }
    final direction = change > 0 ? 'más' : 'menos';
    return '${formatCount(change.abs())} perfiles $direction que en tu plan anterior.';
  }

  Widget _publicationPreview() {
    final publication = widget.publication;
    final community = widget.session.communityName(publication.communityId);
    return _StudioPanel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              PersonAvatar(publication.authorId, size: 42),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Tu publicación',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    Text(
                      '$community · ${moment(publication.createdAt)}',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ],
                ),
              ),
            ],
          ),
          if (publication.body case final body?) ...[
            const SizedBox(height: 13),
            Text(
              body,
              maxLines: 3,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context).textTheme.bodyLarge,
            ),
          ],
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final comparison = result;
    final theme = Theme.of(context);
    final compact = MediaQuery.sizeOf(context).width < 500;
    return Scaffold(
      backgroundColor: ground,
      appBar: AppBar(
        backgroundColor: paper,
        surfaceTintColor: Colors.transparent,
        centerTitle: true,
        title: const Text('Simular difusión'),
        leadingWidth: compact ? 56 : 112,
        leading: compact
            ? IconButton(
                onPressed: () => Navigator.maybePop(context),
                icon: const Icon(Icons.arrow_back_rounded),
                tooltip: 'Volver',
              )
            : Padding(
                padding: const EdgeInsets.only(left: 10),
                child: TextButton.icon(
                  onPressed: () => Navigator.maybePop(context),
                  icon: const Icon(Icons.arrow_back_rounded, size: 19),
                  label: const Text('Volver'),
                ),
              ),
        actions: const [
          Padding(
            padding: EdgeInsets.only(right: 22),
            child: Brand(compact: true),
          ),
        ],
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(18, 18, 18, 40),
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 880),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  _publicationPreview(),
                  const SizedBox(height: 21),
                  Semantics(
                    header: true,
                    child: Text(
                      'Alcance potencial',
                      style: theme.textTheme.headlineMedium,
                    ),
                  ),
                  const SizedBox(height: 5),
                  const Text(
                    'Compara hasta dónde podría llegar tu publicación '
                    'en una red de amistades histórica.',
                    style: TextStyle(color: muted),
                  ),
                  const SizedBox(height: 16),
                  settings(),
                  if (comparison != null && !dirty) ...[
                    const SizedBox(height: 26),
                    if (comparison.contacts.isEmpty)
                      _StudioPanel(
                        child: Text(
                          'Usuario ${comparison.origin} no tiene amistades registradas en el dataset.',
                        ),
                      )
                    else ...[
                      plans(comparison),
                      const SizedBox(height: 26),
                      customPlan(comparison),
                    ],
                  ],
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

const _studioWarm = Color(0xFFFFF9E8);

class _SectionTitle extends StatelessWidget {
  const _SectionTitle(this.title);
  final String title;

  @override
  Widget build(BuildContext context) => Semantics(
    header: true,
    child: Text(title, style: Theme.of(context).textTheme.titleLarge),
  );
}

class _StudioColumns extends StatelessWidget {
  const _StudioColumns({
    required this.breakpoint,
    required this.first,
    required this.second,
  });

  final double breakpoint;
  final Widget first, second;

  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, size) {
      final width = size.maxWidth >= breakpoint
          ? (size.maxWidth - 16) / 2
          : size.maxWidth;
      return Wrap(
        spacing: 16,
        runSpacing: 14,
        children: [
          SizedBox(width: width, child: first),
          SizedBox(width: width, child: second),
        ],
      );
    },
  );
}

class _StudioPanel extends StatelessWidget {
  const _StudioPanel({required this.child, this.warm = false});

  final Widget child;
  final bool warm;

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(18),
    decoration: BoxDecoration(
      color: warm ? _studioWarm : paper,
      borderRadius: BorderRadius.circular(18),
      border: Border.all(color: line),
    ),
    child: child,
  );
}

class _PlanCard extends StatelessWidget {
  const _PlanCard({
    required this.title,
    required this.icon,
    required this.plan,
    this.description,
    this.note,
    this.emphasis = false,
    this.announceReach = false,
  });

  final String title;
  final IconData icon;
  final DiffusionPlan plan;
  final String? description, note;
  final bool emphasis, announceReach;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return _StudioPanel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                padding: const EdgeInsets.all(9),
                decoration: BoxDecoration(
                  color: emphasis ? yellow : ground,
                  borderRadius: BorderRadius.circular(11),
                ),
                child: Icon(icon, size: 21),
              ),
              const SizedBox(width: 11),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title, style: theme.textTheme.titleMedium),
                    if (description != null)
                      Text(description!, style: const TextStyle(color: muted)),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Semantics(
            container: true,
            liveRegion: announceReach,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  formatCount(plan.reachable),
                  style: theme.textTheme.headlineLarge?.copyWith(fontSize: 44),
                ),
                const Text(
                  'perfiles alcanzables',
                  style: TextStyle(color: muted),
                ),
              ],
            ),
          ),
          if (note != null) ...[
            const SizedBox(height: 8),
            Semantics(
              liveRegion: true,
              child: Text(note!, style: theme.textTheme.titleMedium),
            ),
          ],
          const SizedBox(height: 13),
          Wrap(
            spacing: 7,
            runSpacing: 6,
            children: [
              for (final round in plan.rounds)
                DecoratedBox(
                  decoration: BoxDecoration(
                    color: ground,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 8,
                      vertical: 5,
                    ),
                    child: Text(
                      'Salto ${round.hop} · +${formatCount(round.newNodes)}',
                      style: theme.textTheme.bodySmall,
                    ),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 11),
          Text(
            'Contactos iniciales · ${plan.contacts.map((id) => "Usuario $id").join(", ")}',
            style: theme.textTheme.bodySmall,
          ),
        ],
      ),
    );
  }
}

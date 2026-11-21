import 'package:flutter/foundation.dart';
import '../data/outspark_repository.dart';
import '../domain/models.dart';

/// One immutable identity per controller. Old sessions cannot overwrite a new one.
class SessionController extends ChangeNotifier {
  SessionController(this.repository);
  final OutsparkRepository repository;
  Profile? profile;
  List<Community> communities = [];
  List<Topic> topics = [];
  List<String> memberships = [];
  List<String> contacts = [];
  FeedSnapshot? feed;
  FeedComparison? comparison;
  String? error;
  bool loading = true;
  bool _disposed = false;
  int _generation = 0;

  void _emit() {
    if (!_disposed) notifyListeners();
  }

  Future<void> refresh() async {
    final generation = ++_generation;
    loading = true;
    error = null;
    _emit();
    try {
      final results = await Future.wait<Object>([
        repository.loadProfile(),
        repository.listCommunities(),
        repository.listTopics(),
        repository.listMemberships(),
        repository.listContacts(),
        repository.createFeed('chronological'),
      ]);
      if (_disposed || generation != _generation) return;
      profile = results[0] as Profile;
      communities = results[1] as List<Community>;
      topics = results[2] as List<Topic>;
      memberships = results[3] as List<String>;
      contacts = results[4] as List<String>;
      feed = results[5] as FeedSnapshot;
      comparison = null;
    } catch (failure) {
      if (_disposed || generation != _generation) return;
      error = failure.toString();
    } finally {
      if (!_disposed && generation == _generation) {
        loading = false;
        _emit();
      }
    }
  }

  Future<void> compare() async {
    final generation = _generation;
    final result = await repository.compareFeeds();
    if (_disposed || generation != _generation) return;
    comparison = result;
    _emit();
  }

  String communityName(String id) =>
      communities.where((c) => c.id == id).firstOrNull?.name ?? id;
  String topicName(String id) =>
      topics.where((t) => t.id == id).firstOrNull?.name ?? id;

  @override
  void dispose() {
    _disposed = true;
    _generation++;
    super.dispose();
  }
}

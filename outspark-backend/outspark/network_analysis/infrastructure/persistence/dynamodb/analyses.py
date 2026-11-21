from collections import defaultdict
from urllib.parse import urlparse
from uuid import uuid4

from outspark.shared.infrastructure.dynamodb import operations as db
from outspark.shared.infrastructure.dynamodb.bulk import bulk_write
from outspark.shared.infrastructure.dynamodb.mapping import record
from outspark.shared.infrastructure.postgres.records import PostgresRecords


class DynamoStructuralResults:
    """Immutable run partitions; publish the latest pointer only after all buckets exist."""
    def __init__(self, storage):
        self.storage = storage

    def latest(self, dataset_id):
        return record(self.storage.get(f'DATASET#{dataset_id}', 'ANALYSIS#LATEST'))

    def node_group(self, dataset_id, run_id, uid):
        bucket = self.storage.get(f'DATASET#{dataset_id}#ANALYSIS#{run_id}', f'LABELS#{uid // 512:012d}')
        if not bucket:
            return None
        for row in bucket['rows']:
            if int(row[0]) == uid:
                return dict(zip(('node_id', 'group_id', 'group_size', 'degree'), map(int, row)))
        return None

    def save(self, dataset_id, result, summary):
        if not isinstance(self.storage.client, PostgresRecords):
            endpoint = urlparse(self.storage.client.meta.endpoint_url)
            if endpoint.scheme != 'http' or endpoint.hostname not in ('localhost', '127.0.0.1', '::1'):
                raise ValueError('La publicación administrativa requiere almacenamiento local.')
            if not self.storage.table.startswith(('Outspark-local-', 'Outspark-local-test-')):
                raise ValueError('Tabla local de análisis no permitida.')
        if not result['complete']:
            raise ValueError('No se publican resultados incompletos.')
        manifest = self.storage.get(f'DATASET#{dataset_id}', 'MANIFEST')
        if not manifest or manifest['status'] != 'READY' or summary['source_sha256'] != manifest['files']['links']['sha256']:
            raise ValueError('El análisis no corresponde al dataset verificado.')
        if summary['full_graph'] and (result['nodes'] != manifest['counts']['friendship_nodes'] or result['edges'] != manifest['counts']['unique_friendships']):
            raise ValueError('Los recuentos no cubren todo el grafo de amistades.')
        previous = self.latest(dataset_id)
        if previous and previous['full_graph'] and not summary['full_graph']:
            raise ValueError('Un piloto no sustituye al análisis completo publicado.')
        run_id = uuid4().hex
        pk = f'DATASET#{dataset_id}#ANALYSIS#{run_id}'
        sizes = {min(group): len(group) for group in result['groups']}
        buckets = defaultdict(list)
        for row in result['degree_ranking']:
            uid, gid = row['node_id'], row['group_id']
            buckets[uid // 512].append([uid, gid, sizes[gid], row['degree']])
        rows = [dict(PK=pk, SK=f'LABELS#{bucket:012d}', rows=values) for bucket, values in buckets.items()]
        written = bulk_write(self.storage.client, self.storage.table, rows)
        if written != len(rows):
            raise ValueError('Faltan bloques de resultados.')
        published = {**summary, 'run_id': run_id, 'status': 'READY', 'label_buckets': written}
        pointer = db.put(self.storage.table, dict(PK=f'DATASET#{dataset_id}', SK='ANALYSIS#LATEST', **published))
        if previous:
            pointer['Put']['ConditionExpression'] = 'run_id = :previous'
            pointer['Put']['ExpressionAttributeValues'] = db.encode({':previous': previous['run_id']})
        guard = db.check(self.storage.table, {'PK': f'DATASET#{dataset_id}', 'SK': 'MANIFEST'},
                         '#s = :ready AND files.links.sha256 = :hash',
                         {':ready': 'READY', ':hash': summary['source_sha256']}, {'#s': 'status'})
        db.commit(self.storage.client, [db.put(self.storage.table, dict(PK=pk, SK='SUMMARY', **published)), pointer, guard])
        return published

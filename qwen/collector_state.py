"""Versioned checkpoints shared by the two Maps collectors (stdlib only)."""
import json
import errno
import fcntl
from contextlib import contextmanager
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'integrations' / 'browser-use'))
from lead_data import duplicate_of, export, lead_from_detail, normalized, write_json


class CollectionError(RuntimeError):
    pass


class BlockedError(CollectionError):
    pass


class SchemaError(CollectionError):
    pass


@contextmanager
def output_lock(output):
    """Hold one OS lock for the complete collection, including exports.

    Keep the lock file: unlinking it allows another process to lock a new inode.
    The kernel releases the lock even when the process exits unexpectedly.
    """
    directory = Path(output)
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / '.collector.lock').open('a') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            if error.errno in (errno.EACCES, errno.EAGAIN):
                raise CollectionError('Otro colector está usando la carpeta de salida') from None
            raise
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def open_state(args, method, source_options=None):
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    config = dict(queries=list(dict.fromkeys(args.query)), municipality=args.municipality,
                  limit=args.limit, categories=args.category, source_options=source_options or {})
    path = output / 'state.json'
    if path.exists():
        if not args.resume:
            raise CollectionError('Ya existe state.json; usa --resume o una carpeta nueva')
        state = json.loads(path.read_text(encoding='utf-8'))
        if state.get('schema_version') != 1 or state.get('collector') != method:
            raise CollectionError('Estado de otro método o versión sin identificar; usa una carpeta nueva')
        old = state['config']
        if (old['municipality'] != config['municipality'] or old['categories'] != config['categories']
                or args.limit < len(state['accepted'])
                or not set(old['queries']).issubset(config['queries'])):
            raise CollectionError('Resume conserva municipio, categorías y consultas previas; el límite no puede ser menor que los contactos guardados')
        previous = old.get('source_options', {})
        if any(previous.get(key) != config['source_options'].get(key) for key in ('hl', 'gl')):
            raise CollectionError('Resume requiere el mismo idioma y país')
        if any(not isinstance(state.get(key), list) for key in
               ('accepted', 'rejected', 'errors', 'candidates', 'completed', 'completed_queries')):
            raise CollectionError('Checkpoint incompleto o inválido')
        if old != config:
            state['discovery_complete'] = False
            if previous != config['source_options'] or (method == 'maps-ui' and old['limit'] != args.limit):
                state['completed_queries'] = []
            state['config'] = config
    else:
        if args.resume:
            raise CollectionError('No existe state.json para reanudar')
        if any((output / name).exists() for name in ('leads.json', 'leads.csv', 'leads.html')):
            raise CollectionError('Hay exportaciones sin state.json; usa una carpeta nueva')
        state = dict(schema_version=1, collector=method, config=config, accepted=[], rejected=[],
                     errors=[], candidates=[], completed=[], completed_queries=[], discovery_complete=False)
    return state


def save(state, output):
    state['updated_at'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
    state['complete'] = len(state['accepted']) >= state['config']['limit']
    write_json(Path(output) / 'state.json', state)
    export(state, output)


def record_error(state, phase, error, **context):
    # Never persist exception messages: network errors may contain secrets or URLs.
    state['errors'].append(dict(phase=phase, error=type(error).__name__, **context))


def accept_detail(state, detail):
    config = state['config']
    row, reason = lead_from_detail(detail, config['municipality'])
    if row and config['categories'] and not any(normalized(term) in normalized(row['category']) for term in config['categories']):
        row, reason = None, 'category_mismatch'
    duplicate = duplicate_of(row, state['accepted']) if row else None
    if duplicate:
        row, reason = None, 'duplicate: ' + duplicate
    if row:
        row['collector'] = state['collector']
        if detail.get('retrieved_at'):
            row['checked_at'] = detail['retrieved_at']
        row['closure_status'] = 'unverified' if detail.get('permanently_closed') is None else 'not_marked_closed'
        if row['closure_status'] == 'unverified':
            row['notes'] = 'Estado de cierre no comprobado; dato obtenido del feed de búsqueda.'
        state['accepted'].append(row)
    else:
        state['rejected'].append(dict(detail=detail, reason=reason))


def finish(state, args):
    save(state, args.output)
    print(json.dumps(dict(contacts=len(state['accepted']), requested=args.limit,
                          complete=state['complete'], output=str(args.output)), ensure_ascii=False), flush=True)
    if not state['complete']:
        raise SystemExit('Contactos suficientes no encontrados; resultados parciales guardados. Añade consultas y usa --resume')

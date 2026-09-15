"""Normalize, deduplicate and export public business contacts (standard library only)."""
import csv
from datetime import datetime, timezone
import html
import json
from pathlib import Path
import re
import unicodedata
from urllib.parse import urlsplit


def normalized(value):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFKD', value).lower()
                           if not unicodedata.combining(c)).split())


def in_municipality(address, municipality):
    # Match the city component, not a street containing the city's name.
    city = re.escape(normalized(municipality))
    return bool(re.search(r'(?:^|,)\s*(?:\d{4,6}\s*,?\s*)?' + city + r'\s*(?:,|$)', normalized(address)))


def public_url(value):
    return value if urlsplit(value or '').scheme in ('https', 'http') else ''


def maps_url(value):
    match = re.search(r'!1s0x[0-9a-f]+:0x([0-9a-f]+)', value)
    return 'https://www.google.com/maps?cid=' + str(int(match[1], 16)) if match else public_url(value)


def lead_from_detail(detail, municipality):
    fields = detail.get('details', [])
    def field(key):
        return next((f for f in fields if f['id'] == key), {})
    address = field('address').get('text', '').strip()
    address = re.sub(r'^[\s\ue000-\uf8ff]+', '', address).strip()
    if not in_municipality(address, municipality):
        return None, 'municipality_unconfirmed'
    phone = next((f['id'].split('phone:tel:', 1)[1] for f in fields if f['id'].startswith('phone:tel:')), '')
    phone = '+' + re.sub(r'\D', '', phone) if phone else ''
    if not re.fullmatch(r'\+[0-9]{8,15}', phone):
        return None, 'no_public_phone'
    if detail.get('permanently_closed'):
        return None, 'permanently_closed'
    source = maps_url(detail['url'])
    return {
        'name': detail['name'], 'category': detail.get('category', ''),
        'query': detail['query'], 'municipality': municipality, 'address': address,
        'phone': phone, 'website': public_url(field('authority').get('href', '')),
        'maps': source, 'sources': [source], 'email': '', 'whatsapp': '',
        'notes': '', 'checked_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'status': 'Contacto público; sin contactar ni calificar',
    }, ''


def duplicate_of(candidate, accepted):
    for lead in accepted:
        if candidate['maps'] == lead['maps'] or candidate['phone'] == lead['phone']:
            return lead['name']
        if normalized(candidate['address']) == normalized(lead['address']) and normalized(candidate['name']) == normalized(lead['name']):
            return lead['name']
    return None


def write_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def enrich(accepted, additions):
    """Merge manually verified facts; every email/WhatsApp has its own source."""
    by_maps = {row['maps']: row for row in accepted}
    for entry in additions:
        if entry['maps'] not in by_maps:
            raise ValueError('Enrichment does not match an accepted Maps record')
        row = by_maps[entry['maps']]
        for key in ('email', 'whatsapp'):
            fact = entry.get(key)
            if not fact:
                continue
            if not fact.get('source') or not public_url(fact['source']):
                raise ValueError('Every enrichment requires a public source URL')
            if key == 'whatsapp':
                target = urlsplit(fact['value'])
                if target.scheme != 'https' or target.hostname not in ('wa.me', 'api.whatsapp.com', 'www.whatsapp.com'):
                    raise ValueError('WhatsApp must be an explicitly published WhatsApp link')
            elif not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', fact['value']):
                raise ValueError('Invalid email')
            row[key] = fact['value']
            row[key + '_source'] = fact['source']
            if fact['source'] not in row['sources']:
                row['sources'].append(fact['source'])
        if entry.get('notes'):
            row['notes'] = entry['notes']


def excel_safe(value):
    value = str(value)
    return "'" + value if value.lstrip().startswith(('=', '+', '-', '@')) or value.startswith(('\t', '\r')) else value


def export(state, output):
    output = Path(output)
    rows = state['accepted']
    write_json(output / 'leads.json', rows)
    columns = {'name': 'negocio', 'category': 'categoria', 'query': 'busqueda', 'phone': 'telefono',
               'email': 'correo', 'whatsapp': 'whatsapp_publicado', 'address': 'direccion',
               'municipality': 'municipio', 'website': 'sitio_web', 'maps': 'maps',
               'sources': 'fuentes', 'checked_at': 'fecha_consulta', 'status': 'estado', 'notes': 'notas'}
    with (output / 'leads.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(columns.values())
        for row in rows:
            writer.writerow(excel_safe(' | '.join(row[key]) if key == 'sources' else row.get(key, '')) for key in columns)
    escape = html.escape
    def link(url, label):
        return f'<a href="{escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">{escape(label)}</a>' if url else '—'
    table = ''
    for index, row in enumerate(rows, 1):
        contact = link('tel:' + row['phone'], row['phone'])
        if row.get('email'):
            contact += '<br>' + link('mailto:' + row['email'], row['email'])
        if row.get('whatsapp'):
            contact += '<br>' + link(row['whatsapp'], 'WhatsApp publicado')
        sources = ' · '.join(link(url, 'Fuente ' + str(i)) for i, url in enumerate(row['sources'], 1))
        table += f'<tr><td>{index}</td><td><strong>{escape(row["name"])}</strong><br>{escape(row["category"])}<br>{escape(row["address"])}</td><td>{contact}</td><td>{link(row["maps"], "Maps")} · {link(row["website"], "Sitio web")}<br>{sources}<p>{escape(row["notes"])}</p></td></tr>'
    title = f'{len(rows)} contactos · {state["config"]["municipality"]}'
    queries = ' · '.join(state['config']['queries'])
    summary = (f'{len(rows)} contactos de {state["config"]["limit"]} solicitados. '
               f'{sum(bool(r.get("email")) for r in rows)} correos y '
               f'{sum(bool(r.get("whatsapp")) for r in rows)} WhatsApp publicados. '
               'Teléfonos consultados en fichas públicas; no validados por llamada. Prospectos sin contactar ni calificar.')
    document = '''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{font:16px/1.5 system-ui;color:#16304a;background:#f4f7fb;margin:32px}main{max-width:1400px;margin:auto}table{width:100%;border-collapse:collapse;background:white}td,th{padding:16px;text-align:left;vertical-align:top;border-bottom:1px solid #d5e0eb}th{background:#16304a;color:white}a{color:#0065a8}input{padding:12px;font:inherit;min-width:300px;margin:16px 0}td p{font-size:13px}.table{overflow:auto}</style>'''
    document += f'<title>{escape(title)}</title><main><h1>{escape(title)}</h1><p>{escape(queries)}</p><p>{escape(summary)}</p><p>{escape(state["updated_at"])}</p><a href="leads.csv" download>Descargar CSV para Excel</a><br><input id="filter" aria-label="Filtrar contactos" placeholder="Nombre, zona o teléfono…"><div class="table"><table><thead><tr><th>#</th><th>Negocio</th><th>Contacto</th><th>Fuentes</th></tr></thead><tbody>{table}</tbody></table></div><p>Los campos vacíos indican datos no localizados. Las fuentes y las exclusiones se conservan en state.json.</p></main>'
    document += '''<script>document.querySelector('#filter').addEventListener('input',e=>{const q=e.target.value.toLocaleLowerCase();document.querySelectorAll('tbody tr').forEach(r=>r.hidden=!r.innerText.toLocaleLowerCase().includes(q))})</script></html>'''
    (output / 'leads.html').write_text(document, encoding='utf-8')

import csv
import asyncio
from types import SimpleNamespace
import json
from pathlib import Path
import tempfile
import unittest
from lead_data import duplicate_of, enrich, export, in_municipality, lead_from_detail


class ContactTests(unittest.TestCase):
    def detail(self):
        return dict(name='Barbería <Uno>', query='barberías Zapopan', category='Barbería',
                    url='https://www.google.com/maps/place/Uno/data=!1s0x1:0xff',
                    details=[dict(id='address', text='\ue0c8\nCalle Uno 23, Centro, 45100 Zapopan, Jal., México'),
                             dict(id='phone:tel:+523312345678', text='33 1234 5678')])

    def test_completed_resume_preserves_contacts_and_rejects_city_change(self):
        from leads import collect
        row, _ = lead_from_detail(self.detail(), 'Zapopan')
        with tempfile.TemporaryDirectory() as directory:
            config = dict(queries=['barberías Zapopan'], municipality='Zapopan', limit=1, categories=['barber'])
            state = dict(config=config, accepted=[row], completed=[], candidates=[], rejected=[], errors=[], discovery_complete=True)
            path = Path(directory) / 'state.json'
            path.write_text(json.dumps(state))
            args = SimpleNamespace(query=config['queries'], municipality='Zapopan', limit=1, category=['barber'], output=directory, resume=True)
            asyncio.run(collect(None, args))
            saved = path.read_text()
            self.assertEqual(json.loads(saved)['accepted'], [row])
            args.municipality = 'Guadalajara'
            with self.assertRaises(ValueError):
                asyncio.run(collect(None, args))
            self.assertEqual(path.read_text(), saved)

    def test_city_is_not_a_street_name(self):
        self.assertTrue(in_municipality('Calle 1, 45100 Zapopan, Jalisco', 'Zapopan'))
        self.assertFalse(in_municipality('Calle Zapopan 15, Guadalajara, Jalisco', 'Zapopan'))
        self.assertFalse(in_municipality('Av. Uno, Zapopan Norte, Guadalajara', 'Zapopan'))

    def test_extraction_and_duplicate_phone(self):
        row, reason = lead_from_detail(self.detail(), 'Zapopan')
        self.assertEqual(reason, '')
        self.assertEqual(row['phone'], '+523312345678')
        self.assertEqual(row['maps'], 'https://www.google.com/maps?cid=255')
        other = dict(row, name='Otro local', maps='https://www.google.com/maps?cid=256')
        self.assertEqual(duplicate_of(other, [row]), row['name'])
        detail = self.detail(); detail['permanently_closed'] = True
        self.assertEqual(lead_from_detail(detail, 'Zapopan')[1], 'permanently_closed')
        detail = self.detail(); detail['details'].pop()
        self.assertEqual(lead_from_detail(detail, 'Zapopan')[1], 'no_public_phone')

    def test_export_escapes_html_and_spreadsheet_formulas(self):
        row, _ = lead_from_detail(self.detail(), 'Zapopan')
        row['notes'] = '=HYPERLINK("evil")'
        state = dict(accepted=[row], config=dict(municipality='Zapopan', queries=['barberías'], limit=1), updated_at='2026-09-08')
        with tempfile.TemporaryDirectory() as directory:
            export(state, directory)
            path = Path(directory)
            document = (path / 'leads.html').read_text()
            self.assertIn('&lt;Uno&gt;', document)
            with (path / 'leads.csv').open(encoding='utf-8-sig') as stream:
                item = next(csv.DictReader(stream))
            self.assertTrue(item['notas'].startswith("'="))
            self.assertEqual(json.loads((path / 'leads.json').read_text())[0]['phone'], row['phone'])

    def test_enrichment_requires_sources_and_explicit_whatsapp(self):
        row, _ = lead_from_detail(self.detail(), 'Zapopan')
        with self.assertRaises(ValueError):
            enrich([row], [dict(maps=row['maps'], email=dict(value='contacto@example.com'))])
        with self.assertRaises(ValueError):
            enrich([row], [dict(maps=row['maps'], whatsapp=dict(value='https://evil.com/wa.me/123', source='https://example.com'))])
        enrich([row], [dict(maps=row['maps'], email=dict(value='contacto@example.com', source='https://example.com/contacto'))])
        self.assertEqual(row['email_source'], 'https://example.com/contacto')


if __name__ == '__main__':
    unittest.main()

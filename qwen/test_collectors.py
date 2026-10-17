import contextlib
import io
import json
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import qwen_leads_fast as fast
import qwen_leads as ui
from collector_state import BlockedError, CollectionError, SchemaError


def payload(cid=1, name=None, address='Calle Uno, 45100 Zapopan, Jalisco'):
    p = [None] * 179
    p[10], p[11], p[13], p[39] = f'0x1:0x{cid:x}', name or f'Clínica de prueba {cid}', ['Veterinario'], address
    p[178] = [[[f'+52330000{cid:04d}']]]
    return p


def args(output, **updates):
    values = dict(query=['veterinarias Zapopan'], municipality='Zapopan', limit=1,
                  category=['veterin'], output=output, resume=False, hl='es', gl='mx', count=20)
    values.update(updates)
    return SimpleNamespace(**values)


class FakeLupa:
    def __init__(self, count=1, fail_details=False, block=False, interrupt_batch=False):
        self.cards = [dict(name=f'Clínica {n}', url=f'https://www.google.com/maps/place/Fixture{n}/data=!1s0x1:0x{n:x}') for n in range(1,count+1)]
        self.url = ''
        self.visited = []
        self.waits = 0
        self.batches = 0
        self.fail_details = fail_details
        self.block = block
        self.interrupt_batch = interrupt_batch

    def goto(self, url):
        self.url = url
        self.visited.append(url)

    def blocked(self):
        return self.block

    def wait(self, *args, **kwargs):
        self.waits += 1

    def eval(self, script):
        if script == ui.BATCH_JS:
            self.batches += 1
            if self.interrupt_batch and self.batches == 2:
                raise KeyboardInterrupt()
            return json.dumps(self.cards)
        if script == ui.DETAIL_JS:
            if self.fail_details:
                raise RuntimeError('fixture failure')
            n = next(i for i, c in enumerate(self.cards,1) if c['url'] == self.url)
            detail = fast.to_detail(payload(n, f'Clínica {n}'), 'fixture')
            detail['permanently_closed'] = False
            return json.dumps(detail)
        return True


class CollectorTests(unittest.TestCase):
    def test_single_result_is_a_valid_collection(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(fast, 'fetch_results', return_value=[[None, payload()]]), patch.object(fast.time, 'sleep'), contextlib.redirect_stdout(io.StringIO()):
            fast.collect(args(directory), '!1sold!7i20')
            state = json.loads((Path(directory) / 'state.json').read_text())
            self.assertTrue(state['complete'])
            self.assertEqual(len(state['accepted']), 1)

    def test_failed_second_query_preserves_first_query_candidates(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(fast, 'fetch_results', side_effect=[[[None, payload()]], RuntimeError('network failure')]), patch.object(fast.time, 'sleep'), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(RuntimeError):
                fast.collect(args(directory, query=['first', 'second']), '!1sold!7i20')
            state = json.loads((Path(directory) / 'state.json').read_text())
            self.assertEqual(len(state['candidates']), 1)
            self.assertFalse(state['discovery_complete'])

    def test_fast_marks_closure_as_unverified(self):
        detail = fast.to_detail(payload(), 'test')
        self.assertIsNone(detail['permanently_closed'])

    def test_empty_feed_is_not_a_schema_error(self):
        response = [None] * 65
        response[64] = []
        self.assertEqual(fast.parse_response(")]}'\n" + json.dumps(response)), [])
        with tempfile.TemporaryDirectory() as directory, patch.object(fast, 'fetch_results', return_value=[]), patch.object(fast.time, 'sleep'), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit):
                fast.collect(args(directory), '!1sold!7i20')
            state = json.loads((Path(directory) / 'state.json').read_text())
            self.assertFalse(state['complete'])
            self.assertTrue(state['discovery_complete'])
            self.assertEqual(state['errors'], [])

    def test_block_and_changed_json_are_distinct(self):
        with self.assertRaises(BlockedError):
            fast.parse_response('<html>unusual traffic captcha</html>')
        for body in [")]}'\n{}", ")]}'\n[1]", ")]}'\nnot-json"]:
            with self.assertRaises(SchemaError):
                fast.parse_response(body)

    def test_invalid_fields_are_not_guessed(self):
        p = payload();p[10] = '0x1:0xNOTHEX'
        self.assertIsNone(fast.to_detail(p, 'fixture'))
        p = payload();p[39] = ['unexpected address']
        self.assertIsNone(fast.to_detail(p, 'fixture'))
        self.assertIsNone(fast.safe_get([1], -1))
        with tempfile.TemporaryDirectory() as directory, patch.object(fast, 'fetch_results', return_value=[[None, p]]), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SchemaError):
                fast.collect(args(directory), '!1sold!7i20')
            self.assertTrue((Path(directory) / 'state.json').exists())

    def test_completed_resume_never_refetches(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(fast, 'fetch_results', return_value=[[None,payload()]]), patch.object(fast.time, 'sleep'), contextlib.redirect_stdout(io.StringIO()):
            fast.collect(args(directory), '!1sold!7i20')
            accepted = json.loads((Path(directory) / 'leads.json').read_text())
            with patch.object(fast, 'fetch_results', side_effect=AssertionError('unexpected network')):
                fast.collect(args(directory, resume=True), '!1sold!7i20')
            self.assertEqual(json.loads((Path(directory) / 'leads.json').read_text()), accepted)
            self.assertIn('no comprobado', accepted[0]['notes'])

    def test_larger_limit_uses_saved_candidates(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(fast, 'fetch_results', return_value=[[None,payload(1)],[None,payload(2)]]), patch.object(fast.time, 'sleep'), contextlib.redirect_stdout(io.StringIO()):
            fast.collect(args(directory), '!1sold!7i20')
            with patch.object(fast, 'fetch_results', side_effect=AssertionError('unexpected network')):
                fast.collect(args(directory, resume=True, limit=2), '!1sold!7i20')
            self.assertEqual(len(json.loads((Path(directory) / 'leads.json').read_text())), 2)

    def test_resume_after_network_failure_only_fetches_pending_query(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(fast.time, 'sleep'), contextlib.redirect_stdout(io.StringIO()):
            a = args(directory, query=['first','second'], limit=2)
            with patch.object(fast, 'fetch_results', side_effect=[[[None,payload(1)]], OSError('fixture')]):
                with self.assertRaises(OSError):fast.collect(a, '!1sold!7i20')
            a.resume = True
            with patch.object(fast, 'fetch_results', return_value=[[None,payload(2)]]) as fetch:
                fast.collect(a, '!1sold!7i20')
                self.assertEqual(fetch.call_count,1)
                self.assertEqual(fetch.call_args.args[0],'second')
            self.assertEqual(len(json.loads((Path(directory) / 'leads.json').read_text())),2)

    def test_filtering_and_deduplication(self):
        outside = payload(2,address='Calle Zapopan, Guadalajara, Jalisco')
        category = payload(3);category[13] = ['Panadería']
        missing_phone = payload(4);missing_phone[178] = None
        duplicate = payload(5);duplicate[178] = payload(1)[178]
        rows = [[None,p] for p in [payload(1),outside,category,missing_phone,duplicate]]
        with tempfile.TemporaryDirectory() as directory, patch.object(fast, 'fetch_results', return_value=rows), patch.object(fast.time, 'sleep'), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit):fast.collect(args(directory,limit=6),'!1sold!7i20')
            state = json.loads((Path(directory)/'state.json').read_text())
            self.assertEqual(len(state['accepted']),1)
            reasons = [r['reason'] for r in state['rejected']]
            self.assertIn('municipality_unconfirmed',reasons)
            self.assertIn('category_mismatch',reasons)
            self.assertIn('no_public_phone',reasons)
            self.assertTrue(any(x.startswith('duplicate:') for x in reasons))

    def test_resume_rejects_other_method_and_config_without_writing(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(fast, 'fetch_results', return_value=[[None,payload()]]), patch.object(fast.time, 'sleep'), contextlib.redirect_stdout(io.StringIO()):
            fast.collect(args(directory),'!1sold!7i20')
            path = Path(directory)/'state.json';original = path.read_bytes()
            with self.assertRaises(CollectionError):ui.collect(FakeLupa(),args(directory,resume=True))
            for changes in [dict(municipality='Guadalajara'),dict(gl='es'),dict(hl='en'),dict(category=['escuela']),dict(query=['different'])]:
                with self.assertRaises(CollectionError):fast.collect(args(directory,resume=True,**changes),'!1sold!7i20')
            self.assertEqual(path.read_bytes(),original)

    def test_legacy_state_is_rejected_without_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'state.json';path.write_text('{"config":{},"accepted":[]}')
            original = path.read_bytes()
            with self.assertRaises(CollectionError):fast.collect(args(directory,resume=True),'!1sold!7i20')
            self.assertEqual(path.read_bytes(),original)

    def test_ui_interrupt_saves_discovered_batch(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(ui.time,'sleep'), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(KeyboardInterrupt):ui.collect(FakeLupa(interrupt_batch=True),args(directory))
            state=json.loads((Path(directory)/'state.json').read_text())
            self.assertEqual(len(state['candidates']),1)
            self.assertFalse(state['discovery_complete'])
            ui.collect(FakeLupa(),args(directory,resume=True))
            self.assertEqual(len(json.loads((Path(directory)/'leads.json').read_text())),1)

    def test_ui_fifth_detail_error_is_saved_and_retryable(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(ui.time,'sleep'), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(CollectionError):ui.collect(FakeLupa(5,fail_details=True),args(directory,limit=5))
            state=json.loads((Path(directory)/'state.json').read_text())
            self.assertEqual(sum(e['phase']=='detail' for e in state['errors']),5)
            self.assertEqual(state['completed'],[])
            ui.collect(FakeLupa(5),args(directory,resume=True,limit=5))
            self.assertEqual(len(json.loads((Path(directory)/'leads.json').read_text())),5)

    def test_ui_block_stops_before_waiting_for_feed(self):
        fake=FakeLupa(block=True)
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(BlockedError):ui.collect(fake,args(directory))
            self.assertEqual(fake.waits,0)
            self.assertEqual(len(fake.visited),1)
            self.assertEqual(json.loads((Path(directory)/'state.json').read_text())['errors'][-1]['error'],'BlockedError')

    def test_api_redirect_never_forwards_bearer(self):
        hits=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                hits.append(self.path)
                self.send_response(302);self.send_header('Location','/redirect-target');self.end_headers()
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
        try:
            with self.assertRaises(CollectionError):ui.Lupa(f'http://127.0.0.1:{server.server_port}','fixture-token').request('/live')
            self.assertEqual(hits,['/live'])
        finally:
            server.shutdown();server.server_close();worker.join()


    def test_saved_feed_preserves_retrieval_date(self):
        detail = fast.to_detail(payload(), 'fixture')
        detail['retrieved_at'] = '2026-01-01T00:00:00+00:00'
        with tempfile.TemporaryDirectory() as directory, patch.object(fast,'to_detail',return_value=detail), patch.object(fast,'fetch_results',return_value=[[None,payload()]]), patch.object(fast.time,'sleep'), contextlib.redirect_stdout(io.StringIO()):
            fast.collect(args(directory),'!1sold!7i20')
            self.assertEqual(json.loads((Path(directory)/'leads.json').read_text())[0]['checked_at'],detail['retrieved_at'])



if __name__ == '__main__':
    unittest.main()

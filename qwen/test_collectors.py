import contextlib
import io
import json
import tempfile
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import unittest
import urllib.error
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import qwen_leads_fast as fast
import qwen_leads as ui
from collector_state import BlockedError, CollectionError, SchemaError, output_lock


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
    def __init__(self, count=1, fail_details=False, block=False, interrupt_batch=False, empty=False):
        self.cards = [dict(name=f'Clínica {n}', url=f'https://www.google.com/maps/place/Fixture{n}/data=!1s0x1:0x{n:x}') for n in range(1,count+1)]
        self.url = ''
        self.visited = []
        self.waits = 0
        self.batches = 0
        self.fail_details = fail_details
        self.block = block
        self.interrupt_batch = interrupt_batch
        self.empty = empty

    def goto(self, url):
        self.url = url
        self.visited.append(url)

    def blocked(self):
        return self.block

    def wait(self, *args, **kwargs):
        self.waits += 1

    def eval(self, script):
        if script == ui.EMPTY_JS:
            return self.empty
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


@contextlib.contextmanager
def api_fixture(responses):
    queue = list(responses)
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            requests.append((self.path, body))
            status, result = queue.pop(0) if len(queue) > 1 else queue[0]
            data = json.dumps({'result': result} if status == 200 else {'error': 'fixture failure'}).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield ui.Lupa(f'http://127.0.0.1:{server.server_port}', 'fixture-token'), requests
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


class CollectorTests(unittest.TestCase):
    def test_ui_wait_recovers_api_context_failures_during_block_and_ready_checks(self):
        responses = [(500, None), (200, False), (500, None), (200, False), (200, True)]
        with api_fixture(responses) as (lupa, requests):
            lupa.wait('return true', timeout=10, interval=0)
        self.assertEqual(len(requests), 5)
        self.assertEqual(requests[0][1]['script'], ui.BLOCK_JS)

    def test_ui_wait_does_not_retry_auth_rate_limits_or_google_blocks(self):
        for status in (401, 403, 429):
            with self.subTest(status=status), api_fixture([(status, None)]) as (lupa, requests):
                with self.assertRaises(urllib.error.HTTPError):
                    lupa.wait('return true', timeout=10, interval=0)
                self.assertEqual(len(requests), 1)
        with api_fixture([(500, None), (200, True)]) as (lupa, requests):
            with self.assertRaises(BlockedError):
                lupa.wait('return true', timeout=10, interval=0)
            self.assertEqual(len(requests), 2)
            self.assertTrue(all(body['script'] == ui.BLOCK_JS for _, body in requests))

    def test_ui_wait_deadline_stops_persistent_api_failure(self):
        with api_fixture([(500, None)]) as (lupa, requests):
            with self.assertRaises(TimeoutError):
                lupa.wait('return true', timeout=0, interval=0)
            self.assertEqual(len(requests), 1)

    def test_ui_navigation_requests_dom_readiness(self):
        with api_fixture([(200, None), (200, False), (200, True)]) as (lupa, requests):
            lupa.goto('https://www.google.com/maps/search/fixture')
        self.assertEqual(requests[0], ('/live', {'url': 'https://www.google.com/maps/search/fixture', 'waitFor': 'domcontentloaded'}))

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


    def test_output_lock_blocks_other_process_before_state_changes(self):
        code = """
import sys
from types import SimpleNamespace
import qwen_leads_fast as fast
import qwen_leads as ui
from collector_state import CollectionError
args = SimpleNamespace(output=sys.argv[1])
for call in (lambda: fast.collect(args, ''), lambda: ui.collect(None, args)):
    try:
        call()
    except CollectionError as error:
        assert 'Otro colector' in str(error)
    else:
        raise AssertionError('concurrent writer was allowed')
"""
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / 'state.json'
            state.write_text('existing checkpoint')
            with output_lock(directory):
                result = subprocess.run([sys.executable, '-c', code, directory],
                                        cwd=Path(__file__).parent, capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(state.read_text(), 'existing checkpoint')
            self.assertTrue((Path(directory) / '.collector.lock').exists())

    def test_output_lock_releases_after_error_and_process_death(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(RuntimeError):
                with output_lock(directory):
                    raise RuntimeError('fixture')
            with output_lock(directory):
                pass
            code = "from collector_state import output_lock; import sys,time; lock=output_lock(sys.argv[1]); lock.__enter__(); print('ready',flush=True); time.sleep(30)"
            child = subprocess.Popen([sys.executable, '-c', code, directory], cwd=Path(__file__).parent,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                import selectors
                with selectors.DefaultSelector() as selector:
                    selector.register(child.stdout, selectors.EVENT_READ)
                    self.assertTrue(selector.select(10), 'child lock startup timed out')
                self.assertEqual(child.stdout.readline().strip(), 'ready')
                with self.assertRaises(CollectionError):
                    with output_lock(directory):
                        pass
            finally:
                child.kill(); child.communicate(timeout=10)
            with output_lock(directory):
                pass

    def test_real_empty_envelope_requires_explicit_empty_marker(self):
        response = [None] * 72
        header = [None] * 19
        header[8], header[9] = 'fixture', 'fixture'
        header[12], header[18] = ['fixture', '/search?q=fixture'], []
        response[0] = ['fixture', [header]]
        self.assertEqual(fast.parse_response(")]}'\n" + json.dumps(response)), [])
        header[18] = None
        with self.assertRaises(SchemaError):
            fast.parse_response(")]}'\n" + json.dumps(response))
        header[18] = []
        response[0][1].append([None] * 15)
        with self.assertRaises(SchemaError):
            fast.parse_response(")]}'\n" + json.dumps(response))

    def test_ui_empty_panel_completes_discovery_without_errors(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            lupa = FakeLupa(empty=True)
            with self.assertRaises(SystemExit):
                ui.collect(lupa, args(directory))
            state = json.loads((Path(directory) / 'state.json').read_text())
            self.assertTrue(state['discovery_complete'])
            self.assertEqual(state['completed_queries'], state['config']['queries'])
            self.assertEqual(state['errors'], [])
            self.assertEqual(state['accepted'], [])
            self.assertEqual(lupa.batches, 0)


if __name__ == '__main__':
    unittest.main()

"""Opt-in DOM checks against an isolated Lupa instance on this same host/container."""
import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from qwen_leads import BATCH_JS, BLOCK_JS, DETAIL_JS, EMPTY_JS, SEARCH_READY_JS, Lupa, resolve_token
from collector_state import lead_from_detail


@unittest.skipUnless(os.environ.get('LUPA_MAPS_DOM_TESTS') == '1', 'requires isolated Lupa; navigates its live page')
class DomTests(unittest.TestCase):
    def test_collectors_dom_contract(self):
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):pass
            def do_GET(self):
                if self.path == '/feed':
                    body='<div role="feed"><a aria-label="Clínica Uno" href="https://www.google.com/maps/place/Fixture/data=!1s0x1:0x1">Uno</a></div>'
                elif self.path == '/empty':
                    body='<main role="main">Google Maps no encuentra fixture</main>'
                elif self.path == '/blocked':
                    body='Nuestros sistemas han detectado tráfico inusual'
                else:
                    closed='Permanentemente cerrado' if self.path == '/closed' else ''
                    body=f'<main role="main"><h1>Clínica Uno</h1><button jsaction="pane.category">Veterinario</button><div data-item-id="address">Calle Uno, 45100 Zapopan, Jalisco</div><button data-item-id="phone:tel:+523300000001">Teléfono</button><a data-item-id="authority" href="https://example.com">Web</a>{closed}</main>'
                data=body.encode();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.end_headers();self.wfile.write(data)
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
        lupa=Lupa(os.environ['LUPA_URL'],resolve_token())
        try:
            def visit(path):lupa.request('/live',{'url':f'http://127.0.0.1:{server.server_port}{path}'})
            visit('/feed');cards=json.loads(lupa.eval(BATCH_JS));self.assertEqual(len(cards),1);self.assertEqual(cards[0]['name'],'Clínica Uno')
            visit('/open');detail=json.loads(lupa.eval(DETAIL_JS));detail['query']='fixture'
            row,reason=lead_from_detail(detail,'Zapopan');self.assertEqual(reason,'');self.assertEqual(row['phone'],'+523300000001');self.assertFalse(detail['permanently_closed'])
            visit('/closed');detail=json.loads(lupa.eval(DETAIL_JS));detail['query']='fixture';self.assertTrue(detail['permanently_closed']);self.assertEqual(lead_from_detail(detail,'Zapopan')[1],'permanently_closed')
            visit('/blocked');self.assertTrue(lupa.eval(BLOCK_JS));self.assertFalse(lupa.eval(EMPTY_JS))
            visit('/empty');self.assertTrue(lupa.eval(EMPTY_JS));self.assertTrue(lupa.eval(SEARCH_READY_JS))
        finally:
            lupa.request('/live',{'url':'about:blank'})
            server.shutdown();server.server_close();worker.join()


if __name__ == '__main__':unittest.main()

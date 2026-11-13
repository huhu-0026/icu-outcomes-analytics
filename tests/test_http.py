import http.client
import json
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import Handler
from icu_analytics.analytics import ROOT

class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Handler.database=ROOT/'data/demo/mart.sqlite'
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls): cls.server.shutdown();cls.server.server_close();cls.thread.join()
    def request(self,path):
        c=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=20)
        c.request('GET',path);r=c.getresponse();status,headers,data=r.status,dict(r.getheaders()),r.read();c.close();return status,headers,data
    def test_health_and_dashboard(self):
        self.assertEqual(json.loads(self.request('/api/health')[2])['mode'],'demo')
        status,headers,body=self.request('/api/dashboard?hour=24&sex=F')
        self.assertEqual(status,200);self.assertTrue(json.loads(body)['summary']['patients']<1800)
        self.assertIn('Content-Security-Policy',headers)
    def test_no_file_server_escape_or_private_endpoints(self):
        for path in ['/data/private/mart.sqlite','/data/demo/mart.sqlite','/../README.md','/%2e%2e/README.md','/api/patients','/.env']:
            self.assertEqual(self.request(path)[0],404,path)
    def test_invalid_query_rejected(self):
        for query in ['hour=12','hour=abc','sql=SELECT+*+FROM+dim_patient']:
            self.assertEqual(self.request('/api/dashboard?'+query)[0],400)
    def test_static_assets(self):
        for path in ['/','/style.css','/app.js','/favicon.svg']:
            status,_,body=self.request(path);self.assertEqual(status,200);self.assertTrue(body)

if __name__=='__main__': unittest.main()

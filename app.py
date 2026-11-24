"""Offline dashboard launcher. Serves an explicit static allowlist on loopback only."""
import argparse
import json
import mimetypes
import threading
import webbrowser
from contextlib import closing
from functools import partial,lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from icu_analytics.analytics import ROOT, connect, dashboard, metadata
from icu_analytics.research_inputs import research_binding

@lru_cache(maxsize=48)
def cached_dashboard(database,file_version,query,binding=None):
    with closing(connect(database)) as db:
        if binding is not None and metadata(db).get('research_input_sha256') != dict(binding):
            raise ValueError('分析库已更换为不同版本，请重新启动并加载匹配的研究汇总')
        return json.dumps(dashboard(db,dict(query)),ensure_ascii=False,allow_nan=False).encode('utf-8')

class Handler(BaseHTTPRequestHandler):
    database = None
    research = None
    binding = None
    def do_GET(self):
        parsed=urlsplit(self.path)
        if parsed.path == '/api/research':
            if self.research is None:
                self.send_error(404)
            else:
                self.send_content(self.research, 'application/json; charset=utf-8')
            return
        if parsed.path in ('/api/health','/api/dashboard'):
            try:
                if parsed.path=='/api/health':
                    with closing(connect(self.database)) as db: body=json.dumps({'status':'ok','mode':metadata(db)['mode']}).encode()
                else:
                    args={k:v[0] for k,v in parse_qs(parsed.query).items()}
                    if set(args)-{'hour','sex','age','unit'}: raise ValueError('Unsupported filter')
                    stat = self.database.stat()
                    file_version = (stat.st_ino, stat.st_mtime_ns, stat.st_size)
                    body=cached_dashboard(str(self.database),file_version,tuple(sorted(args.items())),self.binding)
                self.send_content(body,'application/json; charset=utf-8')
            except ValueError as e: self.send_content(json.dumps({'error':str(e)}).encode(),'application/json',400)
            except Exception:
                self.send_content(b'{"error":"Database unavailable. Rebuild the selected mode."}','application/json',500)
            return
        names={'/':'index.html','/index.html':'index.html','/style.css':'style.css','/app.js':'app.js','/research-ui.js':'research-ui.js','/preview-data.js':'preview-data.js','/favicon.svg':'favicon.svg'}
        if parsed.path not in names:
            self.send_error(404);return
        p=ROOT/'web'/names[parsed.path]
        if not p.is_file(): self.send_error(404);return
        self.send_content(p.read_bytes(),mimetypes.guess_type(p.name)[0] or 'application/octet-stream')
    def send_content(self,content,mime,status=200):
        self.send_response(status);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(content)))
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
        self.end_headers();self.wfile.write(content)
    def log_message(self,*args): pass

def main():
    p=argparse.ArgumentParser(description='ICU Outcomes Analytics · local portfolio')
    sub=p.add_subparsers(dest='command',required=True)
    for mode in ('build-demo','build-mimic'):
        s=sub.add_parser(mode)
        if mode=='build-mimic': s.add_argument('--project',type=Path,default=ROOT.parent)
    s=sub.add_parser('serve');s.add_argument('--mode',choices=['demo','mimic'],default='demo');s.add_argument('--port',type=int);s.add_argument('--open',action='store_true')
    s.add_argument('--database',type=Path,help='Read an existing mart.sqlite')
    s.add_argument('--research-dir',type=Path,help='Local output from review-research')
    s=sub.add_parser('review-research')
    s.add_argument('--project',required=True,type=Path)
    s.add_argument('--output',required=True,type=Path)
    sub.add_parser('export-public')
    s=sub.add_parser('export-bi');s.add_argument('--mode',choices=['demo','mimic'],default='demo')
    args=p.parse_args()
    if args.command.startswith('build-'):
        from icu_analytics.build import build_demo,build_mimic
        if args.command=='build-demo': build_demo(ROOT/'data/demo/mart.sqlite')
        else: build_mimic(args.project,ROOT/'data/private/mart.sqlite')
    elif args.command=='export-public':
        from icu_analytics.exports import public_bundle
        public_bundle()
    elif args.command=='export-bi':
        from icu_analytics.exports import export_bi
        export_bi(args.mode)
    elif args.command=='review-research':
        from icu_analytics.research import write_review
        print(write_review(args.project,args.output))
    else:
        database=args.database or ROOT/('data/demo' if args.mode=='demo' else 'data/private')/'mart.sqlite'
        if not database.is_file(): p.error('先运行 build-'+('demo' if args.mode=='demo' else 'mimic'))
        with closing(connect(database)) as db:
            source=metadata(db)
            if source['mode']!=args.mode: p.error('数据库和启动模式不匹配')
            if args.mode=='demo':
                from icu_analytics.statistics import synthetic_research
                research=synthetic_research(db)
            else:
                research=None
            binding = None
            if args.research_dir is not None:
                if args.mode!='mimic': p.error('研究结果仅能加载到本地真实模式')
                research=json.loads((args.research_dir/'research_summary.json').read_text(encoding='utf-8'))
                try:
                    binding = research_binding(source, research)
                except ValueError as error:
                    p.error(str(error))
        Handler.research=json.dumps(research,ensure_ascii=False,allow_nan=False).encode('utf-8') if research else None
        Handler.binding = binding
        Handler.database=database
        port=args.port or (8765 if args.mode=='demo' else 8766)
        try: server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
        except OSError: p.error(f'本机端口 {port} 已被使用；关闭旧看板窗口或使用 --port 指定其他端口。')
        print(f'ICU Outcomes Analytics [{args.mode}] http://127.0.0.1:{port} · Ctrl+C to stop',flush=True)
        if args.open: threading.Timer(.5,partial(webbrowser.open,f'http://127.0.0.1:{port}')).start()
        try: server.serve_forever()
        except KeyboardInterrupt: pass
        finally: server.server_close()

if __name__=='__main__': main()

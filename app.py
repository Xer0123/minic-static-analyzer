"""A dependency-free local web interface for the MiniC static analyzer."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import webbrowser
from analyzer import analyze, CompileError

ROOT = Path(__file__).parent

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in ("/", "/index.html"):
            self.send_error(404); return
        page=(ROOT / "index.html").read_bytes()
        self.send_response(200); self.send_header("Content-Type","text/html; charset=utf-8"); self.send_header("Content-Length",str(len(page))); self.end_headers(); self.wfile.write(page)
    def do_POST(self):
        if self.path != "/api/analyze": self.send_error(404); return
        try:
            n=int(self.headers.get("Content-Length","0"))
            if n>200_000: raise ValueError("Source limit is 200 KB.")
            body=json.loads(self.rfile.read(n)); result=analyze(body.get("source",""))
            response={"ok":True,"result":result}
        except CompileError as e:
            response={"ok":False,"error":{"message":e.message,"line":e.line,"column":e.column}}
        except Exception as e:
            response={"ok":False,"error":{"message":str(e),"line":None,"column":None}}
        data=json.dumps(response).encode()
        self.send_response(200); self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Content-Length",str(len(data))); self.send_header("Cache-Control","no-store"); self.end_headers(); self.wfile.write(data)
    def log_message(self,*args): pass

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser(description="Run the MiniC static analyzer in your browser")
    p.add_argument("--host",default="127.0.0.1"); p.add_argument("--port",type=int,default=8000); p.add_argument("--no-browser",action="store_true")
    a=p.parse_args(); server=ThreadingHTTPServer((a.host,a.port),Handler)
    url=f"http://{a.host}:{a.port}"
    print(f"MiniC Analyzer running at {url} (Ctrl+C to stop)")
    if not a.no_browser: webbrowser.open(url)
    try: server.serve_forever()
    except KeyboardInterrupt: print("\nStopped.")
    finally: server.server_close()

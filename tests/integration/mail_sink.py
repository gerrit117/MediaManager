"""Disposable SMTP receiver for integration tests. Never forwards mail."""
import email,html,re,socketserver,threading
from email.policy import default
from urllib.parse import urlsplit,parse_qs
class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        self.wfile.write(b'220 synthetic-test-mail\r\n')
        while True:
            line=self.rfile.readline(16384)
            if not line:return
            verb=line.split(b' ',1)[0].strip().upper()
            if verb in [b'EHLO',b'HELO']:self.wfile.write(b'250 synthetic-test-mail\r\n')
            elif verb==b'DATA':
                self.wfile.write(b'354 End with dot\r\n');data=[];total=0
                while True:
                    part=self.rfile.readline(16384)
                    if not part or part==b'.\r\n':break
                    total+=len(part)
                    if total>1024*1024:return
                    data.append(part)
                self.server.messages.append(b''.join(data));self.wfile.write(b'250 Accepted\r\n')
            elif verb==b'QUIT':self.wfile.write(b'221 Bye\r\n');return
            else:self.wfile.write(b'250 OK\r\n')
class MailSink:
    def __init__(self):
        self.server=socketserver.ThreadingTCPServer(('0.0.0.0',0),Handler);self.server.daemon_threads=True;self.server.messages=[]
        self.port=self.server.server_address[1];self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def token(self,recipient,path='verify'):
        for raw in reversed(self.server.messages):
            message=email.message_from_bytes(raw,policy=default)
            if recipient.lower() not in str(message['To']).lower():continue
            for part in message.walk():
                if part.get_content_type()!='text/html':continue
                for target in re.findall(r'href="([^"]+)"',part.get_content()):
                    link=urlsplit(html.unescape(target))
                    if link.path.endswith(path):return parse_qs(link.fragment or link.query)['token'][0]
        raise AssertionError('Expected synthetic account email was not delivered')
    def close(self):self.server.shutdown();self.server.server_close()

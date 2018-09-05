'''
    Simple socket server using threads
'''
 
from http.server import BaseHTTPRequestHandler

from threading import Thread
from http.server import HTTPServer

PORT_NUMBER = 8888


class HttpServer():
    http_server = True

    def __init__(self):
        super(HttpServer, self).__init__()
        if not self.http_server:
            return
        self.simple_server = HTTPServer(('', 8888), myHandler)
        self.simple_server.message = 'Let\'s go'
        
        self.server_thread = Thread(target = self.simple_server.serve_forever)
        self.server_thread.start()

    def stop(self):
        print('stopping server')
        self.simple_server.shutdown()
        self.simple_server.socket.close()
        print('server stopped')
    

#This class will handles any incoming request from
#the browser 
class myHandler(BaseHTTPRequestHandler):
    #Handler for the GET requests
    def do_GET(self):
        self.send_response(200)
        self.send_header(b'Content-type','text/html')
        self.end_headers()
        # Send the html message
        if (self.path != '/'):
            self.wfile.write(self.server.message.encode())
        else:
            self.wfile.write(b"""<html>
                <body>
                    Inside the mind of the LingLover
                    <div id="a"></div>
                    <script>
                        function a() {
                            var xhttp = new XMLHttpRequest();
                            xhttp.onreadystatechange = function() {
                                if (this.readyState == 4 && this.status == 200) {
                                    document.getElementById("a").innerHTML = "<pre>" + this.responseText + "</pre>";
                                    setTimeout(a, 100);
                                }
                            };
                            xhttp.open("GET", "http://localhost:8888/something", true);
                            xhttp.send();
                        }
                        a();
                    </script>
                </body>
                </html>""")
        return

'''
    Simple socket server using threads
'''
 
from http.server import BaseHTTPRequestHandler

PORT_NUMBER = 8888

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

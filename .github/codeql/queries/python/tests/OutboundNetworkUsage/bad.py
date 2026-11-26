import requests

requests.get("https://example.com")
import socket
socket.create_connection(("example.com", 443))
socket.socket().connect(("example.com", 443))
socket.socket().connect_ex(("example.com", 443))
import urllib.request
urllib.request.urlopen("https://example.com")

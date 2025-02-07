from threading import Thread
from time import sleep
from bsif_webview import WebViewApplication, get_running_application

app = WebViewApplication(debug_enabled=True, title="test")

app.start()

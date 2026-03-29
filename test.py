from threading import Thread
from time import sleep

from webview.webview import WebViewApplication

app = WebViewApplication(debug_enabled=True)

def delay_test():
	sleep(10)
	aa = app.create_window()
	print(aa)

Thread(None, delay_test).start()

app.start(title="test")
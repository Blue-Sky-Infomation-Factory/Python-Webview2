import code
from threading import Thread, current_thread
from time import sleep
from bsif.webview import WebViewApplication, get_running_application

import webview

def test(a):
	print(a)
	app.main_window.navigate_uri = a # type: ignore

def emulator():
	print("sleep for 5s")
	sleep(5)
	print("moving")
	app = get_running_application()
	app.cross_thread_call(test, ("https://bspr0002.github.io/",)) # type: ignore

Thread(target=emulator, daemon=True).start()
# Thread(target=code.interact, daemon=True).start()

app = WebViewApplication(debug_enabled=True, title="test")

app.start(initial_uri="https://github.com/Blue-Sky-Infomation-Factory/Python-Webview2")

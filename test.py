from threading import Thread
from time import sleep
from bsif.webview import WebViewApplication, get_running_application
from bsif.webview.webview import WebViewWindow

def emulator():
	print("sleep for 5s")
	sleep(5)
	print("moving")
	window: WebViewWindow = get_running_application().main_window # type: ignore

Thread(target=emulator, daemon=True).start()
# Thread(target=code.interact, daemon=True).start()

app = WebViewApplication(debug_enabled=True, title="test")

app.start(initial_uri="https://github.com/Blue-Sky-Infomation-Factory/Python-Webview2", max_size=(512, 512))

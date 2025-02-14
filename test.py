from threading import Thread
from time import sleep, time
from bsif.webview import WebViewApplication, get_running_application


def emulator():
	print("sleep for 5s")
	sleep(5)
	print("moving")
	app = get_running_application()
	s = time()
	app.main_window.navigate_uri = "https://bspr0002.github.io/"  # type: ignore
	print(f"done: {time()-s}s")

Thread(target=emulator, daemon=True).start()
# Thread(target=code.interact, daemon=True).start()

app = WebViewApplication(debug_enabled=True, title="test")

app.start(initial_uri="https://github.com/Blue-Sky-Infomation-Factory/Python-Webview2")

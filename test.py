from threading import Thread
from time import sleep
from os.path import dirname

from bsif_webview.webview import WebViewApplication

app = WebViewApplication(debug_enabled=True)

def delay_test():
	for s in range(5, 0, -1):
		print(f"Test mission count down: {s}")
		sleep(1)
	print("Test mission running")
	window = app.main_window
	assert window
	result = window.show_directory_picker(title="Select a file", initial_directory=dirname(__file__), multiple=True, default_directory_name="test")
	if result:
		print(result.directories)
	app.stop()

# def async_agent(method, args = (), kargs = {}):
# 	c: Coroutine = method(*args, **kargs)
# 	result = new_event_loop().run_until_complete(c)
# 	print(result)
# Thread(None, async_agent, args=(delay_test,)).start()
Thread(None, delay_test).start()

app.start(title="test")
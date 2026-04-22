from threading import Thread
from time import sleep, time
from os.path import dirname
from asyncio import new_event_loop, sleep as async_sleep
from typing import Coroutine


from bsif_webview import WebViewApplication

app = WebViewApplication(debug_enabled=True)



async def async_call_test(error: bool = False):
	await async_sleep(5)
	if error:
		raise ValueError("Test error")
	else:
		return "hello world"
def sync_call_test(error: bool = False):
	if error:
		raise ValueError("Test error")
	else:
		return "hello world"
api_test = {
	"asyncCall": async_call_test,
	"syncCall": sync_call_test
}

async def delay_test():
	for s in range(5, 0, -1):
		print(f"Test mission count down: {s}")
		sleep(1)
	print("Test mission running")
	window = app.main_window
	assert window
	window.post_message("hello world")
	window.message_notifier.add_handler(lambda x: print(type(x)))
	window.execute_javascript("0.1 + 0.2", print)
	print(await window.execute_javascript_await("0.1 + 0.2"))
	# app.stop()

def async_agent(method, args = (), kargs = {}):
	c: Coroutine = method(*args, **kargs)
	result = new_event_loop().run_until_complete(c)
	print(result)
Thread(None, async_agent, args=(delay_test,), daemon=True).start()
# Thread(None, delay_test).start()

app.start(title="test", api=api_test, private_mode=False)
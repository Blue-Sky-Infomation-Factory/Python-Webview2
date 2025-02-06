from threading import Thread
from time import sleep
from webview import WebViewApplication, get_running_application

app = WebViewApplication(debug_enabled=True, title="test")

def main():
	sleep(10)
	print(get_running_application())



Thread(target=main).start()



app.start()
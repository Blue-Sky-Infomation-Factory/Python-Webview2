from bsif.webview import WebViewApplication, get_running_application

app = WebViewApplication(debug_enabled=True, title="test")

app.start(initial_uri="https://github.com/Blue-Sky-Infomation-Factory/Python-Webview2")

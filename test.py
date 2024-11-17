from webview import WebViewApplication
from webview.webview import WebViewConfiguration

app = WebViewApplication(WebViewConfiguration(debug_enabled=True), "test")

app.start(borderless=True)
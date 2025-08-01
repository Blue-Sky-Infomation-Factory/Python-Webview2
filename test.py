from webview import WebViewApplication
from webview.webview import WebViewConfiguration

app = WebViewApplication(WebViewConfiguration(debug_enabled=True))

app.start(title="test", window_caption_color="#F00")
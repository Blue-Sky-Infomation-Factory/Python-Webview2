from . import webview
from .webview import WebViewApplication, WebViewConfiguration, WebViewException
from .notifier import Notifier

def running_application(): return webview.running_application
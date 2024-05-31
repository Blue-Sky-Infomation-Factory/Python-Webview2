from . import webview
from .webview import WebViewApplication, WebViewConfiguration, WebViewException
from .handlers import Handlers

def running_application(): return webview.running_application
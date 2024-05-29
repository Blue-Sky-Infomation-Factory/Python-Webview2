from tkinter import Frame, Tk
from traceback import print_exception
from typing import Optional, Tuple
import os
import clr
from win32gui import SetParent, MoveWindow
from json import loads

clr.AddReference('System.Windows.Forms') # type: ignore
clr.AddReference('System.Collections') # type: ignore
clr.AddReference('System.Threading') # type: ignore
clr.AddReference(os.path.dirname(__file__) + '/Microsoft.Web.WebView2.Core.dll') # type: ignore
clr.AddReference(os.path.dirname(__file__) + '/Microsoft.Web.WebView2.WinForms.dll') # type: ignore
clr.AddReference(os.path.dirname(__file__) + '/BSIF.WebView2Bridge.dll') # type: ignore

from System.Drawing import Color # type: ignore
from Microsoft.Web.WebView2.WinForms import WebView2, CoreWebView2CreationProperties # type: ignore
from Microsoft.Web.WebView2.Core import CoreWebView2PermissionState, CoreWebView2HostResourceAccessKind # type: ignore
from System import Uri # type: ignore
from System.Threading import Thread, ThreadStart, ApartmentState # type: ignore
from System.Collections.Generic import List # type: ignore
from BSIF.WebView2Bridge import WebView2Bridge # type: ignore

with open(os.path.dirname(__file__) + "/bridge_js.js") as file: __bridge_script = file.read()

class WebViewException(Exception):
	def __init__(self, exception):
		super(WebViewException, self).__init__(exception.Message)
		self.raw = exception

class WebViewConfiguration:
	def __init__(self,
			data_folder: str = os.getenv('TEMP') + '/Microsoft WebView', # WebView 数据文件夹 # type: ignore
			private_mode = True, # 隐私模式
			debug_enabled = False, # 启用调试特性
			user_agent:Optional[str] = None, # 用户代理标识
			api: object = None, # 向 WebView 暴露的 API 对象
			web_api_permission_bypass: bool = False, # 自动允许 Web API 的权限请求
			vhost_path: Optional[str] = None, # vHost 映射的文件夹路径
			vhost_name: str = "webview", # vHost 的域名
			vhost_cors: bool = True, # 是否允许 vHost 访问外部资源
			min_size: Tuple[int, int] = (384, 256), # 窗口显示区最小尺寸
			max_size: Optional[Tuple[int, int]] = None # 窗口显示区最大尺寸
		):
		self.data_folder = data_folder
		self.private_mode = private_mode
		self.debug_enabled = debug_enabled
		self.user_agent = user_agent
		self.api = api
		self.web_api_permission_bypass = web_api_permission_bypass
		self.vhost_path = vhost_path
		self.vhost_name = vhost_name
		self.vhost_cors = vhost_cors
		self.min_size = min_size
		self.max_size = max_size

class WebViewApplication:
	def __init__(self, configuration: WebViewConfiguration = WebViewConfiguration(), title = 'WebView Application'):
		self.__configuration = configuration
		self.__thread: Optional[Thread] = None
		self.__title = title
		self.__root: Optional[Tk] = None
		self.__frame: Optional[Frame] = None
		self.__webview: Optional[WebView2] = None
		self.__webview_hwnd: Optional[int] = None
		self.__navigate_uri = ""

	def __resize_webview(self, _ = None):
		assert self.__root and self.__frame and self.__webview_hwnd
		frame = self.__frame
		MoveWindow(self.__webview_hwnd, 0,0, frame.winfo_width(), frame.winfo_height(), False)

	def __run(self):
		configuration = self.__configuration
		root = self.__root = Tk()
		root.title(self.__title)
		root.minsize(*configuration.min_size)
		if configuration.max_size: root.maxsize(*configuration.max_size)
		
		frame = self.__frame = Frame(root)
		frame.pack(fill="both",expand=True)
		frame_id = frame.winfo_id()
		webview = self.__webview = WebView2()
		webview_properties = CoreWebView2CreationProperties()
		webview_properties.UserDataFolder = configuration.data_folder
		webview_properties.set_IsInPrivateModeEnabled(configuration.private_mode)
		webview_properties.AdditionalBrowserArguments = '--disable-features=ElasticOverscroll'
		webview.CreationProperties = webview_properties
		webview.DefaultBackgroundColor = Color.White
		webview.CoreWebView2InitializationCompleted += self.__on_webview_ready
		webview.NavigationStarting += self.__on_navigation_start
		webview.NavigationCompleted += self.__on_navigation_completed
		webview.WebMessageReceived += self.__on_javaScript_message
		webview.Source = Uri(self.__navigate_uri)
		webViewHandle = self.__webview_hwnd = webview.Handle.ToInt32()
		SetParent(webViewHandle, frame_id)
		frame.bind('<Configure>', self.__resize_webview)
		root.mainloop()
		self.__root = self.__frame = self.__webview = self.__webview_hwnd = None

	def start(self, uri: Optional[str] = None, width = 384, height = 256):
		if self.__thread: raise Exception("WebView is already started.")
		if uri: self.__navigate_uri = uri
		thread = Thread(ThreadStart(self.__run))
		self.__thread = thread
		thread.ApartmentState = ApartmentState.STA
		thread.Start()
		thread.Join()
		self.__thread = None

	def stop(self):
		if not self.__thread: raise Exception("WebView is not started.")
		self.__thread.Abort()

	@property
	def navigate_uri(self): return self.__navigate_uri
	@navigate_uri.setter
	def navigate_uri(self, value):
		self.__navigate_uri = value
		if self.__webview: self.__webview.Source = Uri(value)

	def __on_new_window_request(self, _, args):
		args.set_Handled(True)

	def __scriptCallHandler(self, method_name: str, argsJson: str):
		print(method_name, loads(argsJson))
		return "ok"

	def __on_webview_ready(self, webview_instance, args):
		if not args.IsSuccess:
			print_exception(WebViewException(args.InitializationException))
			return
		configuration = self.__configuration
		core = webview_instance.CoreWebView2
		core.NewWindowRequested += self.__on_new_window_request
		if configuration.web_api_permission_bypass: core.PermissionRequested += self.__on_permission_requested
		bridge = WebView2Bridge(WebView2Bridge.Caller(self.__scriptCallHandler), ["a"])
		core.AddHostObjectToScript("bridge", bridge)
		core.AddScriptToExecuteOnDocumentCreatedAsync(globals()['__bridge_script'])
		debug_enabled = configuration.debug_enabled
		settings = core.Settings
		settings.AreBrowserAcceleratorKeysEnabled = settings.AreDefaultContextMenusEnabled = settings.AreDevToolsEnabled = debug_enabled
		settings.AreDefaultScriptDialogsEnabled = True
		settings.IsBuiltInErrorPageEnabled = True
		settings.IsScriptEnabled = True
		settings.IsWebMessageEnabled = True
		settings.IsStatusBarEnabled = False
		settings.IsSwipeNavigationEnabled = False
		settings.IsZoomControlEnabled = False

		ua = configuration.user_agent
		if ua: settings.UserAgent = ua

		vhost = configuration.vhost_path
		if vhost: core.SetVirtualHostNameToFolderMapping(configuration.vhost_name, vhost, CoreWebView2HostResourceAccessKind.DenyCors if configuration.vhost_cors else CoreWebView2HostResourceAccessKind.Deny)

		# cookies persist even if UserDataFolder is in memory. We have to delete cookies manually.
		if configuration.private_mode: core.CookieManager.DeleteAllCookies()

		if debug_enabled: core.OpenDevToolsWindow()

	def __on_navigation_start(self, _, args):
		print('Webview navigation started: ' + args.Uri)

	def __on_navigation_completed(self, _, args):
		print('Webview navigation completed, status: ' + str(args.HttpStatusCode))

	def __on_permission_requested(self, _, args):
		args.State = CoreWebView2PermissionState.Allow

	def __on_javaScript_message(self, _, args):
		data = args.WebMessageAsJson
		print(data)
		print(args.AdditionalObjects)

a = WebViewApplication(WebViewConfiguration(debug_enabled= True, api=True))
a.start("https://bsif.netlify.app/page/test")
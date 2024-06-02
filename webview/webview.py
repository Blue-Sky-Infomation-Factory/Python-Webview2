import clr
from inspect import isbuiltin, isfunction, ismethod
from json import dumps, loads
from os import getenv
from os.path import dirname, join
from queue import Queue
from threading import current_thread, main_thread
from tkinter import Frame, Tk
from traceback import print_exception
from typing import Any, Callable, Dict, Optional, Tuple
from win32gui import SetParent, MoveWindow
from .handlers import Handlers

clr.AddReference('System.Windows.Forms') # type: ignore
clr.AddReference('System.Threading') # type: ignore
self_path = dirname(__file__)
clr.AddReference(join(self_path, 'Microsoft.Web.WebView2.Core.dll')) # type: ignore
clr.AddReference(join(self_path,'Microsoft.Web.WebView2.WinForms.dll')) # type: ignore
clr.AddReference(join(self_path, 'BSIF.WebView2Bridge.dll')) # type: ignore
del self_path

from BSIF.WebView2Bridge import WebView2Bridge # type: ignore
from Microsoft.Web.WebView2.Core import CoreWebView2PermissionState, CoreWebView2HostResourceAccessKind # type: ignore
from Microsoft.Web.WebView2.WinForms import WebView2, CoreWebView2CreationProperties # type: ignore
from System import Uri # type: ignore
from System.Drawing import Color # type: ignore
from System.Threading import Thread, ThreadStart, ApartmentState # type: ignore

with open(dirname(__file__) + "/bridge.js") as file: _bridge_script = file.read()

class WebViewException(Exception):
	def __init__(self, exception):
		super().__init__(exception.Message)
		self.raw = exception

def serialize_object(object: object): return object.__dict__

def pick_methods(object: object) -> Dict[str, Callable]:
	methods = {}
	for name in dir(object):
		if name.startswith("_"): continue
		item = getattr(object, name)
		if ismethod(item) or isfunction(item) or isbuiltin(item): methods[name] = item
	return methods

def pick_dictionary_methods(object: Dict[str, Any]) -> Dict[str, Callable]:
	methods = {}
	for key, value in object.items():
		if ismethod(value) or isfunction(value) or isbuiltin(value): methods[key] = value
	return methods

class WebViewConfiguration:
	def __init__(self,
			data_folder: str = getenv('TEMP') + '/Microsoft WebView', # WebView 数据文件夹 # type: ignore
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
		self.__api = (pick_dictionary_methods if type(configuration.api) is dict else pick_methods)(configuration.api) # type: ignore
		self.__message_handlers = Handlers()
		self.__call_queue: Queue[Tuple[Callable, Tuple]] = Queue()

	def __resize_webview(self, _):
		assert self.__root and self.__frame and self.__webview_hwnd
		frame = self.__frame
		MoveWindow(self.__webview_hwnd, 0,0, frame.winfo_width(), frame.winfo_height(), False)

	def __call_handler(self, _):
		queue = self.__call_queue
		task = queue.get(block=False)
		queue.task_done()
		task[0](*task[1])

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
		webview.WebMessageReceived += self.__on_javascript_message
		webview.Source = Uri(self.__navigate_uri)
		webview_handle = self.__webview_hwnd = webview.Handle.ToInt32()
		SetParent(webview_handle, frame_id)
		frame.bind('<Configure>', self.__resize_webview)
		root.bind('<<AppCall>>', self.__call_handler)
		root.mainloop()
		self.__root = self.__frame = self.__webview = self.__webview_hwnd = None

	def start(self, uri: Optional[str] = None, width = 384, height = 256):
		global running_application
		assert (current_thread() is main_thread()), "WebView can start in main thread only."
		assert not self.__thread, "WebView is already started."
		if uri: self.__navigate_uri = uri
		thread = Thread(ThreadStart(self.__run))
		self.__thread = thread
		thread.ApartmentState = ApartmentState.STA
		thread.Start()
		running_application = self
		thread.Join()
		running_application = self.__thread = None

	def stop(self):
		assert self.__root, "WebView is not started."
		self.__root.quit()

	def __on_new_window_request(self, _, args):
		args.set_Handled(True)

	def __script_call_handler(self, method_name: str, args_json: str):
		return dumps(self.__api[method_name](*loads(args_json)), ensure_ascii=False)

	def __on_webview_ready(self, webview_instance, args):
		if not args.IsSuccess:
			print_exception(WebViewException(args.InitializationException))
			return
		configuration = self.__configuration
		core = webview_instance.CoreWebView2
		core.NewWindowRequested += self.__on_new_window_request
		if configuration.web_api_permission_bypass: core.PermissionRequested += self.__on_permission_requested
		bridge = WebView2Bridge(WebView2Bridge.Caller(self.__script_call_handler), self.__api.keys())
		core.AddHostObjectToScript("bridge", bridge)
		core.AddScriptToExecuteOnDocumentCreatedAsync(_bridge_script)
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

	def __on_javascript_message(self, _, args):
		self.__message_handlers.triggle(args.WebMessageAsJson, args.AdditionalObjects)

	def __cross_thread_call(self, function: Callable, *args):
		assert self.__root, "WebView is not started."
		self.__call_queue.put((function, args), block=False)
		self.__root.event_generate("<<AppCall>>")

	def __navigate_to(self, uri: str):
		assert self.__webview, "WebView is not started."
		self.__webview.Source = Uri(uri)
	@property
	def navigate_uri(self): return self.__navigate_uri
	@navigate_uri.setter
	def navigate_uri(self, value):
		self.__navigate_uri = value
		if self.__webview: self.__cross_thread_call(self.__navigate_to, value)

	def __post_message(self, message: str):
		assert self.__webview, "WebView is not started."
		self.__webview.CoreWebView2.PostWebMessageAsJson(message)
	def post_message(self, message: Any):
		self.__cross_thread_call(self.__post_message, dumps(message, ensure_ascii=False, default=serialize_object))
	
	def __execute_javascript(self, script: str):
		assert self.__webview, "WebView is not started."
		self.__webview.CoreWebView2.ExecuteScriptAsync(script)
	def execute_javascript(self, script: str):
		self.__cross_thread_call(self.__execute_javascript, script)

	@property
	def message_handlers(self): return self.__message_handlers

running_application: Optional[WebViewApplication] = None
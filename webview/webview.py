from inspect import isfunction, ismethod
from traceback import print_exception
import clr
from os import getenv
from os.path import dirname, join
from threading import Lock, current_thread, main_thread
from typing import Any, Callable, Iterable, Optional, Self, Tuple, TypedDict, Unpack

from .notifier import Notifier

clr.AddReference("System.Windows.Forms") # type: ignore
clr.AddReference("System.Threading") # type: ignore
self_path = dirname(__file__)
clr.AddReference(join(self_path, "Microsoft.Web.WebView2.Core.dll")) # type: ignore
clr.AddReference(join(self_path, "Microsoft.Web.WebView2.WinForms.dll")) # type: ignore
del self_path

from Microsoft.Web.WebView2.WinForms import WebView2 # type: ignore
from System import Uri
from System.Drawing import Color, Size # type: ignore
from System.Threading import Thread as CSharpThread, ApartmentState, ParameterizedThreadStart # type: ignore
from System.Threading.Tasks import TaskScheduler # type: ignore
from System.Windows.Forms import Application, ApplicationContext, DockStyle, Form # type: ignore

class WebViewException(Exception):
	def __init__(self, exception):
		super().__init__(exception.Message)
		self.raw = exception

class WebViewVirtualHost:
	def __init__(self, src_path: str, host_name = "webview", allow_cross_origin = True):
		self.src_path = src_path,
		self.host_name = host_name,
		self.allow_cross_origin = allow_cross_origin,

class WebViewApplicationParameters(TypedDict, total=False):
	title: str
	data_folder: str
	private_mode: bool
	debug_enabled: bool
	user_agent: str
	virtual_hosts: Iterable[WebViewVirtualHost]
	api: object
	web_api_permission_bypass: bool

class WebViewGlobalConfiguration:
	def __init__(self, data: WebViewApplicationParameters):
		self.title = data.get("title", "WebView Application")
		self.data_folder = data.get("data_folder", getenv("TEMP") + "/Microsoft WebView") # type: ignore
		self.private_mode = data.get("private_mode", True)
		self.debug_enabled = data.get("debug_enabled", False)
		self.user_agent = data.get("user_agent")
		self.virtual_hosts = data.get("virtual_hosts")
		self.api = data.get("api")
		self.web_api_permission_bypass = data.get("web_api_permission_bypass", False)

_start_lock = Lock()

class WebViewWindowParameters(TypedDict, total=False):
	initial_uri: str
	title: str
	size: Tuple[int, int]
	position: Tuple[int, int]
	hide: bool
	borderless: bool
	background_color: Color
	min_size: Tuple[int, int]
	max_size: Tuple[int, int]
	private_mode: bool
	user_agent: str
	virtual_hosts: Iterable[WebViewVirtualHost]
	api: object
	web_api_permission_bypass: bool

class WebViewApplication:
	def __init__(self, **params: Unpack[WebViewApplicationParameters]):
		self.__configuration = WebViewGlobalConfiguration(params)
		self.__task_executor: Optional[TaskScheduler] = None
		self.__running = False
		self.__main_window: Optional[WebViewWindow] = None

	@property
	def main_window(self): return self.__main_window

	def create_window(self, **params: Unpack[WebViewWindowParameters]):
		return WebViewWindow(self.__configuration, params)

	def stop(self):
		Application.Exit()

	def __start(self, params: Tuple[Optional[Callable[[Self], Any]], WebViewWindowParameters]):
		_start_lock.release()
		self.__running = True
		[main, options] = params
		if main:
			try: main(self)
			except Exception as e:
				print_exception(e)
				return
		else:
			self.__main_window = self.create_window(**options)
		Application.Run(ApplicationContext())

	def start(self, main: Optional[Callable[[Self], Any]] = None, **params: Unpack[WebViewWindowParameters]):
		global _running_application
		_start_lock.acquire()
		try:
			assert main is None or isfunction(main) or ismethod(main), "Argument 'main' is not a valid callable object."
			assert (current_thread() is main_thread()), "WebViewApplication can start in main thread only."
			assert not self.__running, "WebViewApplication is already started."
			assert not _running_application, "A WebViewApplication is already running."
		except AssertionError as e:
			_start_lock.release()
			raise e
		_running_application = self
		thread = CSharpThread(ParameterizedThreadStart(self.__start))
		thread.SetApartmentState(ApartmentState.STA)
		thread.Start((main, params))
		thread.Join()
		with _start_lock:
			self.__running = False
			_running_application = None

class WebViewWindow:
	def __init__(self, global_configuration: WebViewGlobalConfiguration, params: WebViewWindowParameters):
		initial_uri = self.__navigate_uri = params.get("initial_uri", "about:blank")
		self.__message_notifier = Notifier()
		window = self.__window = Form()
		window.Text = params.get("title", global_configuration.title)
		window.Size = Size(300, 300)

		self.__webview: WebView2
		webview = self.__webview = WebView2()
		webview.Dock = DockStyle.Fill
		webview.Source = Uri(initial_uri)
		window.Controls.Add(webview)
		
		self.__webview_hwnd: Optional[int] = None
		
		window.Show()
		# private_mode = True,
		# user_agent:Optional[str] = None,
		# virtual_hosts: Optional[Iterable[WebViewVirtualHost]] = None,
		# api: object = None,
		# web_api_permission_bypass: bool = False,
		# min_size: Tuple[int, int] = (384, 256),
		# max_size: Optional[Tuple[int, int]] = None

_running_application: Optional[WebViewApplication] = None
def get_running_application():
	with _start_lock: return _running_application
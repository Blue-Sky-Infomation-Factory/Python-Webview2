from inspect import isfunction, ismethod
from traceback import print_exception
import clr
from os import getenv
from os.path import dirname, join
from threading import Lock, current_thread, main_thread
from typing import Any, Callable, Iterable, Optional, Self, Tuple, TypedDict, Unpack

from .bridge import Bridge, serialize_object
from bsif.utils.notifier import Notifier

clr.AddReference("System.Windows.Forms") # type: ignore
clr.AddReference("System.Threading") # type: ignore
self_path = dirname(__file__)
clr.AddReference(join(self_path, "Microsoft.Web.WebView2.Core.dll")) # type: ignore
clr.AddReference(join(self_path, "Microsoft.Web.WebView2.WinForms.dll")) # type: ignore
del self_path

from Microsoft.Web.WebView2.Core import( # type: ignore
	CoreWebView2HostResourceAccessKind,
	CoreWebView2InitializationCompletedEventArgs,
	CoreWebView2PermissionState
)
from Microsoft.Web.WebView2.WinForms import CoreWebView2CreationProperties, WebView2 # type: ignore
from System import Uri
from System.Drawing import Color, Size # type: ignore
from System.Threading import Thread as CSharpThread, ApartmentState, ParameterizedThreadStart # type: ignore
from System.Threading.Tasks import TaskScheduler # type: ignore
from System.Windows.Forms import Application, ApplicationContext, CloseReason, DockStyle, Form, FormClosedEventArgs # type: ignore

def method_bind(method: Callable, *bind_args, **bind_kargs):
	return lambda *args: method(*bind_args, *args, **bind_kargs)

class WebViewException(Exception):
	def __init__(self, exception):
		super().__init__(exception.Message)
		self.raw = exception

class WebViewVirtualHost:
	def __init__(self, src_path: str, host_name = "webview", allow_cross_origin = True):
		self.src_path = src_path
		self.host_name = host_name
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
	exit_on_close: bool

class WebViewApplication:
	def __init__(self, **params: Unpack[WebViewApplicationParameters]):
		self.__configuration = WebViewGlobalConfiguration(params)
		self.__task_executor: Optional[TaskScheduler] = None
		self.__running = False
		self.__main_window: Optional[WebViewWindow] = None

	@property
	def main_window(self): return self.__main_window

	def create_window(self, **params: Unpack[WebViewWindowParameters]):
		return WebViewWindow(self, self.__configuration, params)

	def stop(self):
		with _start_lock:
			if self.__running: Application.Exit()

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
			if "exit_on_close" not in options: options["exit_on_close"] = True
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

class WebViewWindowInitializeParameters:
	def __init__(self, global_configuration: WebViewGlobalConfiguration, params: WebViewWindowParameters):
		self.debug_enabled = global_configuration.debug_enabled
		self.private_mode = params.get("private_mode", global_configuration.private_mode)
		self.user_agent = params.get("user_agent", global_configuration.user_agent)
		self.virtual_hosts = params.get("virtual_hosts", global_configuration.virtual_hosts)
		self.web_api_permission_bypass = params.get("web_api_permission_bypass", global_configuration.web_api_permission_bypass)

class WebViewWindow:
	@property
	def on_closed(self): return self.__on_closed
	@property
	def exit_on_close(self): return self.__exit_on_close
	@exit_on_close.setter
	def exit_on_close(self, value: bool):
		self.__exit_on_close = bool(value)
	def __on_close_handler(self, *_):
		if self.__exit_on_close: self.__application.stop()

	@property
	def navigate_uri(self): return self.__navigate_uri
	@navigate_uri.setter
	def navigate_uri(self, value: str):
		self.__webview.Source = Uri(value)
		self.__navigate_uri = value

	def __init__(self, application: WebViewApplication, global_configuration: WebViewGlobalConfiguration, params: WebViewWindowParameters):
		self.__application = application
		self.__on_closed: Notifier[Self, CloseReason]
		on_closed = self.__on_closed = Notifier()
		on_closed.add_handler(self.__on_close_handler)
		self.__exit_on_close = params.get("exit_on_close", False)

		initial_uri = self.__navigate_uri = params.get("initial_uri", "about:blank")

		self.__message_notifier = Notifier()
		window = self.__window = Form()
		window.Text = params.get("title", global_configuration.title)
		window.Size = Size(300, 300)
		# window.TransparencyKey = window.BackColor

		init_params = WebViewWindowInitializeParameters(global_configuration, params)
		self.__webview: WebView2
		webview = self.__webview = WebView2()
		webview_properties = CoreWebView2CreationProperties()
		webview_properties.IsInPrivateModeEnabled = init_params.private_mode
		webview_properties.UserDataFolder = global_configuration.data_folder
		webview_properties.AdditionalBrowserArguments = "--disable-features=ElasticOverscroll"
		webview.CreationProperties = webview_properties
		webview.DefaultBackgroundColor = Color.White
		webview.Dock = DockStyle.Fill
		self.__api = params.get("api", global_configuration.api)
		webview.CoreWebView2InitializationCompleted += method_bind(self.__on_webview_ready, init_params)


		webview.Source = Uri(initial_uri)
		window.Controls.Add(webview)
		window.Closed += self.__on_window_closed
		self.__webview_hwnd: Optional[int] = None
		
		window.Show()
		# private_mode = True,
		# user_agent:Optional[str] = None,
		# virtual_hosts: Optional[Iterable[WebViewVirtualHost]] = None,
		# api: object = None,
		# web_api_permission_bypass: bool = False,
		# min_size: Tuple[int, int] = (384, 256),
		# max_size: Optional[Tuple[int, int]] = None

	def __on_window_closed(self, _: Form, args: FormClosedEventArgs):
		self.__on_closed.trigger(self, args.CloseReason)

	def __on_new_window_request(self, _, args):
		args.set_Handled(True)

	def __on_permission_requested(self, _, args):
		args.State = CoreWebView2PermissionState.Allow

	def __on_webview_ready(self, init_params:WebViewWindowInitializeParameters, webview: WebView2, args: CoreWebView2InitializationCompletedEventArgs):
		if not args.IsSuccess:
			print_exception(WebViewException(args.InitializationException))
			return
		core = webview.CoreWebView2
		assert core
		core.NewWindowRequested += self.__on_new_window_request
		if init_params.web_api_permission_bypass: core.PermissionRequested += self.__on_permission_requested
		Bridge(core, self.__api)
		debug_enabled = init_params.debug_enabled
		settings = core.Settings
		settings.AreBrowserAcceleratorKeysEnabled = settings.AreDefaultContextMenusEnabled = settings.AreDevToolsEnabled = debug_enabled
		settings.AreDefaultScriptDialogsEnabled = True
		settings.IsBuiltInErrorPageEnabled = True
		settings.IsScriptEnabled = True
		settings.IsWebMessageEnabled = True
		settings.IsStatusBarEnabled = False
		settings.IsSwipeNavigationEnabled = False
		settings.IsZoomControlEnabled = False

		ua = init_params.user_agent
		if ua: settings.UserAgent = ua

		vhosts = init_params.virtual_hosts
		if vhosts:
			for host in vhosts:
				host.host_name
				core.SetVirtualHostNameToFolderMapping(
					host.host_name, host.src_path,
					CoreWebView2HostResourceAccessKind.DenyCors if host.allow_cross_origin else CoreWebView2HostResourceAccessKind.Deny
				)

		# cookies persist even if UserDataFolder is in memory. We have to delete cookies manually.
		if init_params.private_mode: core.CookieManager.DeleteAllCookies()

		if debug_enabled: core.OpenDevToolsWindow()

_running_application: Optional[WebViewApplication] = None
def get_running_application():
	with _start_lock: return _running_application
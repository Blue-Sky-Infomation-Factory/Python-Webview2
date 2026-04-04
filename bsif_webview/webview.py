from inspect import isfunction, ismethod
from traceback import print_exception
from clr import AddReference
from os import getenv
from os.path import dirname, join
from threading import Lock, current_thread, main_thread
from typing import Any, Callable, Iterable, Optional, Self, Tuple, TypedDict, Unpack
from bsif_utils.notifier import Notifier

from .bridge import Bridge

AddReference("wpf\\PresentationFramework")
self_path = dirname(__file__)
AddReference(join(self_path, "Microsoft.Web.WebView2.Core.dll"))
AddReference(join(self_path, "Microsoft.Web.WebView2.Wpf.dll"))
del self_path

from System import EventArgs, Exception as CSException, Uri, Func, Object as CSObject
from System.Drawing import Color # type: ignore
from System.Threading import ApartmentState, Thread as CSharpThread, ParameterizedThreadStart
from System.Windows import Application, ShutdownMode, Window
from System.Windows.Controls import Grid # type: ignore
from System.Windows.Media import Brushes
from System.Windows.Threading import Dispatcher # type: ignore

from Microsoft.Web.WebView2.Core import( # type: ignore
	CoreWebView2HostResourceAccessKind,
	CoreWebView2NavigationCompletedEventArgs,
	CoreWebView2NavigationStartingEventArgs,
	CoreWebView2NewWindowRequestedEventArgs,
	CoreWebView2InitializationCompletedEventArgs,
	CoreWebView2PermissionRequestedEventArgs,
	CoreWebView2PermissionState,
	CoreWebView2
)
from Microsoft.Web.WebView2.Wpf import CoreWebView2CreationProperties, WebView2CompositionControl # type: ignore

class WebViewException(Exception):
	def __init__(self, exception: CSException):
		super().__init__(exception.Message)
		self.source = exception

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
	stop_at_main_window_closed: bool

class WebViewGlobalConfiguration:
	def __init__(self, data: WebViewApplicationParameters):
		self.title = data.get("title", "WebView Application")
		self.data_folder = data.get("data_folder", getenv("TEMP", ".") + "/Microsoft WebView")
		self.private_mode = data.get("private_mode", True)
		self.debug_enabled = data.get("debug_enabled", False)
		self.user_agent = data.get("user_agent")
		self.virtual_hosts = data.get("virtual_hosts")
		self.api = data.get("api")
		self.web_api_permission_bypass = data.get("web_api_permission_bypass", False)

class WebViewWindowParameters(TypedDict, total=False):
	initial_uri: str
	title: str
	size: Tuple[int, int]
	resizable: bool
	min_size: Tuple[int, int]
	max_size: Tuple[int, int]
	position: Tuple[int, int]
	hide: bool
	frameless: bool
	private_mode: bool
	user_agent: str
	virtual_hosts: Iterable[WebViewVirtualHost]
	api: object
	web_api_permission_bypass: bool

_state_lock = Lock()

def _cross_thread_executor(method: Callable, args: Tuple):
	return method(*args)
_cross_thread_delegate = Func[CSObject, CSObject, CSObject](_cross_thread_executor) # type: ignore
def _cross_thread_call[*AT, RT](dispatcher: Dispatcher, method: Callable[[*AT], RT], args: Tuple[*AT] = ()) -> RT:
	return dispatcher.Invoke(_cross_thread_delegate, (method, args)) # type: ignore

class WebViewApplication:
	@property
	def stop_at_main_window_closed(self): return self.__stop_at_main_window_closed
	@stop_at_main_window_closed.setter
	def stop_at_main_window_closed(self, value: bool):
		self.__stop_at_main_window_closed = bool(value)

	@property
	def main_window(self): return self.__main_window
	@main_window.setter
	def main_window(self, value):
		if value is not None and not isinstance(value, WebViewWindow): raise TypeError("Not a WebViewWindow")
		if value and value.closed: raise ValueError("Cannot set a closed window as main window")
		self.__main_window = value

	def __init__(self, **params: Unpack[WebViewApplicationParameters]):
		self.__configuration = WebViewGlobalConfiguration(params)
		self.__running = False
		self.__application: Optional[Application] = None
		self.__dispatcher: Optional[Dispatcher] = None
		self.__stop_at_main_window_closed = params.get("stop_at_main_window_closed", True)
		self.__main_window: Optional[WebViewWindow] = None

	def create_window(self, **params: Unpack[WebViewWindowParameters]):
		assert self.__dispatcher
		return _cross_thread_call(self.__dispatcher, WebViewWindow, (self, self.__dispatcher, self.__configuration, params))

	def __run(self, params: Tuple[Optional[Callable[[Self], Any]], WebViewWindowParameters]):
		self.__running = True
		app = self.__application = Application()
		self.__dispatcher = app.Dispatcher
		_state_lock.release()
		[main, options] = params
		app.ShutdownMode = ShutdownMode.OnExplicitShutdown
		if main:
			try: main(self)
			except Exception as e:
				print_exception(e)
				return
		else: self.__main_window = self.create_window(**options)
		app.Run()

	def start(self, main: Optional[Callable[[Self], Any]] = None, **params: Unpack[WebViewWindowParameters]):
		global _running_application
		_state_lock.acquire()
		try:
			if main is not None and not isfunction(main) and not ismethod(main): raise TypeError("Argument 'main' is not a valid callable object.")
			if current_thread() is not main_thread(): raise RuntimeError("WebViewApplication can start in main thread only.")
			if self.__running: raise Exception("WebViewApplication is already started.")
			if _running_application: raise Exception("A WebViewApplication is already running.")
		except Exception as e:
			_state_lock.release()
			raise e
		_running_application = self
		thread = CSharpThread(ParameterizedThreadStart(self.__run))
		thread.SetApartmentState(ApartmentState.STA)
		thread.Start((main, params))
		thread.Join()
		with _state_lock:
			self.__running = False
			_running_application = self.__dispatcher = None
	def __stop(self):
		assert self.__application
		self.__application.Shutdown()
	def stop(self):
		with _state_lock:
			if self.__running:
				assert self.__application and self.__dispatcher
				_cross_thread_call(self.__dispatcher, self.__stop)

class WebViewWindowInitializeParameters:
	def __init__(self, global_configuration: WebViewGlobalConfiguration, params: WebViewWindowParameters):
		self.debug_enabled = global_configuration.debug_enabled
		# self.private_mode = params.get("private_mode", global_configuration.private_mode)
		self.user_agent = params.get("user_agent", global_configuration.user_agent)
		self.virtual_hosts = params.get("virtual_hosts", global_configuration.virtual_hosts)
		self.web_api_permission_bypass = params.get("web_api_permission_bypass", global_configuration.web_api_permission_bypass)

class WebViewWindow:
	def __init__(self, app: WebViewApplication, dispatcher: Dispatcher, configuration: WebViewGlobalConfiguration, params: WebViewWindowParameters):
		self.__closed = False
		self.__application = app
		self.__dispatcher = dispatcher
		self.__message_notifier = Notifier()
		self.__on_closed = Notifier[Self]()
		self.__min_size = None
		self.__max_size = None

		window = self.__window = Window()
		window.Title = params.get("title", configuration.title)

		size = params.get("min_size")
		if size: self.min_size = size
		size = params.get("max_size")
		if size: self.max_size = size
		size = params.get("size")
		if size: self.size = size

		init_params = WebViewWindowInitializeParameters(configuration, params)
		layout = Grid()
		layout.Background = Brushes.White
		webview = self.__webview = WebView2CompositionControl()
		webview_properties = CoreWebView2CreationProperties()
		webview_properties.IsInPrivateModeEnabled = params.get("private_mode", configuration.private_mode)
		webview_properties.UserDataFolder = configuration.data_folder
		webview_properties.AdditionalBrowserArguments = "--disable-features=ElasticOverscroll"
		webview.CreationProperties = webview_properties
		webview.DefaultBackgroundColor = Color.Transparent
		self.__api = params.get("api", configuration.api)

		webview.CoreWebView2InitializationCompleted += lambda w, a: self.__on_webview_ready(init_params, w, a)
		if configuration.debug_enabled:
			webview.NavigationStarting += self.__on_navigation_start
			webview.NavigationCompleted += self.__on_navigation_completed
		initial_uri = self.__navigate_uri = params.get("initial_uri", "about:blank")
		webview.Source = Uri(initial_uri)

		layout.Children.Add(webview)
		window.Content = layout

		window.Closed += self.__on_window_closed
		if not params.get("hide"): window.Show()
		# min_size: Tuple[int, int] = (384, 256),
		# max_size: Optional[Tuple[int, int]] = None
	
	@property
	def closed(self): return self.__closed
	@property
	def on_closed(self): return self.__on_closed
	def __close(self):
		self.__window.Close()
	def close(self):
		assert self.__dispatcher
		_cross_thread_call(self.__dispatcher, self.__close)

	@property
	def navigate_uri(self): return self.__navigate_uri
	def __navigate_uri_call(self, value): self.__webview.Source = Uri(value)
	@navigate_uri.setter
	def navigate_uri(self, value: str):
		assert self.__dispatcher
		_cross_thread_call(self.__dispatcher, self.__navigate_uri_call, (value,))
		self.__navigate_uri = value

	def __on_window_closed(self, _, args: EventArgs):
		self.__closed = True
		self.__dispatcher = None
		self.__on_closed.trigger(self)

	def __on_new_window_request(self, _: CoreWebView2, args: CoreWebView2NewWindowRequestedEventArgs):
		args.Handled = True

	def __on_permission_requested(self, _: CoreWebView2, args: CoreWebView2PermissionRequestedEventArgs):
		args.State = CoreWebView2PermissionState.Allow

	def __on_navigation_start(self, _: WebView2CompositionControl, args: CoreWebView2NavigationStartingEventArgs):
		print("Webview navigation started: " + args.Uri)

	def __on_navigation_completed(self, _: WebView2CompositionControl, args: CoreWebView2NavigationCompletedEventArgs):
		print("Webview navigation completed, status: " + str(args.HttpStatusCode))

	def __on_webview_ready(self, init_params:WebViewWindowInitializeParameters, webview: WebView2CompositionControl, args: CoreWebView2InitializationCompletedEventArgs):
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

		if debug_enabled: core.OpenDevToolsWindow()

	def _get_wpf_window(self):
		return self.__window
_get_wpf_window = WebViewWindow._get_wpf_window
del WebViewWindow._get_wpf_window

_running_application: Optional[WebViewApplication] = None
def get_running_application():
	with _state_lock: return _running_application
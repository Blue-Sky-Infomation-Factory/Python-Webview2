from bsif.utils.notifier import Notifier
from inspect import isfunction, ismethod
from traceback import print_exception
import clr
from os import getenv
from os.path import dirname, join
from threading import Lock, current_thread, main_thread
from typing import Any, Callable, Iterable, Optional, Self, Tuple, TypedDict, Unpack

clr.AddReference("System.Threading")
clr.AddReference("System.Windows.Forms")
self_path = dirname(__file__)
clr.AddReference(join(self_path, "Microsoft.Web.WebView2.Core.dll"))
clr.AddReference(join(self_path, "Microsoft.Web.WebView2.WinForms.dll"))
del self_path

from .bridge import Bridge

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
from Microsoft.Web.WebView2.WinForms import CoreWebView2CreationProperties, WebView2 # type: ignore
from System import Exception as CSException, Uri
from System.Drawing import Color, Size # type: ignore
from System.Threading import ApartmentState, SendOrPostCallback, Thread as CSharpThread, ParameterizedThreadStart # type: ignore
from System.Windows.Forms import Application, CloseReason, DockStyle, Form, FormClosedEventArgs, WindowsFormsSynchronizationContext # type: ignore

Application.EnableVisualStyles()
Application.SetCompatibleTextRenderingDefault(True)

class WebViewException(Exception):
	def __init__(self, exception: CSException):
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

_state_lock = Lock()

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

def _cross_thread_executor(params): params[1] = params[0](*params[1])
_cross_thread_caller = SendOrPostCallback(_cross_thread_executor)

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
		self.__sync_context: Optional[WindowsFormsSynchronizationContext] = None
		self.__stop_at_main_window_closed = params.get("stop_at_main_window_closed", True)
		self.__main_window: Optional[WebViewWindow] = None

	def __cross_thread_call(self, method: Callable, args: Tuple):
		with _state_lock:
			if not self.__running: raise RuntimeError("Application is not running.")
			package = [method, args]
			self.__sync_context.Send(_cross_thread_caller, package) # type: ignore
			return package[1]

	def create_window(self, **params: Unpack[WebViewWindowParameters]):
		return self.__cross_thread_call(WebViewWindow, (self, self.__cross_thread_call, self.__configuration, params))

	def stop(self):
		with _state_lock:
			if self.__running: Application.Exit()

	def __start(self, params: Tuple[Optional[Callable[[Self], Any]], WebViewWindowParameters]):
		self.__running = True
		sync_context = self.__sync_context = WindowsFormsSynchronizationContext()
		WindowsFormsSynchronizationContext.SetSynchronizationContext(sync_context)
		_state_lock.release()
		[main, options] = params
		if main:
			try: main(self)
			except Exception as e:
				print_exception(e)
				return
		else: self.__main_window = self.create_window(**options)
		Application.Run()

	def start(self, main: Optional[Callable[[Self], Any]] = None, **params: Unpack[WebViewWindowParameters]):
		global _running_application
		_state_lock.acquire()
		try:
			if main is not None and not isfunction(main) and not ismethod(main): raise TypeError("Argument 'main' is not a valid callable object.")
			if current_thread() is not main_thread(): raise RuntimeError("WebViewApplication can start in main thread only.")
			if self.__running: raise RuntimeError("WebViewApplication is already started.")
			if _running_application: raise RuntimeError("A WebViewApplication is already running.")
		except AssertionError as e:
			_state_lock.release()
			raise e
		_running_application = self
		thread = CSharpThread(ParameterizedThreadStart(self.__start))
		thread.SetApartmentState(ApartmentState.STA)
		thread.Start((main, params))
		thread.Join()
		with _state_lock:
			self.__running = False
			_running_application = self.__sync_context = None

class WebViewWindowInitializeParameters:
	def __init__(self, global_configuration: WebViewGlobalConfiguration, params: WebViewWindowParameters):
		self.debug_enabled = global_configuration.debug_enabled
		# self.private_mode = params.get("private_mode", global_configuration.private_mode)
		self.user_agent = params.get("user_agent", global_configuration.user_agent)
		self.virtual_hosts = params.get("virtual_hosts", global_configuration.virtual_hosts)
		self.web_api_permission_bypass = params.get("web_api_permission_bypass", global_configuration.web_api_permission_bypass)

class WebViewWindow:
	@property
	def closed(self): return self.__closed
	@property
	def on_closed(self): return self.__on_closed

	@property
	def navigate_uri(self): return self.__navigate_uri
	def __navigate_uri_call(self, value): self.__webview.Source = Uri(value)
	@navigate_uri.setter
	def navigate_uri(self, value: str):
		self.__cross_thread_call(self.__navigate_uri_call, (value,))
		self.__navigate_uri = value

	def __init__(self, app: WebViewApplication, cross_thread_caller: Callable[[Callable, Tuple], None], configuration: WebViewGlobalConfiguration, params: WebViewWindowParameters):
		self.__closed = False
		self.__application = app
		self.__cross_thread_caller = cross_thread_caller
		self.__message_notifier = Notifier()
		self.__on_closed = Notifier[Self, CloseReason]()

		window = self.__window = Form()
		window.Text = params.get("title", configuration.title)
		window.Size = Size(300, 300)
		# window.TransparencyKey = window.BackColor
		
		init_params = WebViewWindowInitializeParameters(configuration, params)
		self.__webview: WebView2
		webview = self.__webview = WebView2()
		webview_properties = CoreWebView2CreationProperties()
		webview_properties.IsInPrivateModeEnabled = params.get("private_mode", configuration.private_mode)
		webview_properties.UserDataFolder = configuration.data_folder
		webview_properties.AdditionalBrowserArguments = "--disable-features=ElasticOverscroll"
		webview.CreationProperties = webview_properties
		webview.DefaultBackgroundColor = Color.White
		webview.Dock = DockStyle.Fill
		self.__api = params.get("api", configuration.api)

		webview.CoreWebView2InitializationCompleted += lambda w, a: self.__on_webview_ready(init_params, w, a)
		if configuration.debug_enabled:
			webview.NavigationStarting += self.__on_navigation_start
			webview.NavigationCompleted += self.__on_navigation_completed
		initial_uri = self.__navigate_uri = params.get("initial_uri", "about:blank")
		webview.Source = Uri(initial_uri)

		window.Controls.Add(webview)
		window.Closed += self.__on_window_closed

		if not params.get("hide"): window.Show()
		# min_size: Tuple[int, int] = (384, 256),
		# max_size: Optional[Tuple[int, int]] = None
	
	def __cross_thread_call(self, method: Callable, args: Tuple):
		if self.__closed: raise RuntimeError("Window is closed.")
		return self.__cross_thread_caller(method, args) # type: ignore

	def __on_window_closed(self, _: Form, args: FormClosedEventArgs):
		self.__closed = True
		app = self.__application
		self.__cross_thread_caller = None
		if self is app.main_window:
			app.main_window = None
			if app.stop_at_main_window_closed: app.stop()
		self.__on_closed.trigger(self, args.CloseReason)

	def __on_new_window_request(self, _: CoreWebView2, args: CoreWebView2NewWindowRequestedEventArgs):
		args.Handled = True

	def __on_permission_requested(self, _: CoreWebView2, args: CoreWebView2PermissionRequestedEventArgs):
		args.State = CoreWebView2PermissionState.Allow

	def __on_navigation_start(self, _: WebView2, args: CoreWebView2NavigationStartingEventArgs):
		print("Webview navigation started: " + args.Uri)

	def __on_navigation_completed(self, _: WebView2, args: CoreWebView2NavigationCompletedEventArgs):
		print(f"Webview navigation completed, status: " + str(args.HttpStatusCode))

	def __on_webview_ready(self, init_params:WebViewWindowInitializeParameters, webview: WebView2, args: CoreWebView2InitializationCompletedEventArgs):
		if not args.IsSuccess:
			print_exception(WebViewException(args.InitializationException))
			return
		core = webview.CoreWebView2
		assert core, "Unexpected condition: webview.CoreWebView2 is falsy."
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

_running_application: Optional[WebViewApplication] = None
def get_running_application():
	with _state_lock: return _running_application
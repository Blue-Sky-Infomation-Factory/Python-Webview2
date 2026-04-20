from .helper import ARCHITECTURE, LIBRARIES, PLATFORM_MAP, load_desktop_runtime_dll

if ARCHITECTURE not in PLATFORM_MAP:
	raise RuntimeError("Unsupported platform.")

from asyncio import Future
from enum import Enum
from inspect import isfunction, ismethod
from json import dumps, loads
from traceback import print_exception
from clr import AddReference
from os import getenv
from os.path import join
from threading import Lock, current_thread, main_thread
from typing import Any, Callable, Iterable, Literal, Optional, Self, Tuple, TypedDict, Unpack
from weakref import WeakKeyDictionary
from bsif_utils.notifier import Notifier

AddReference("wpf\\PresentationFramework")
webview2_dlls = join(LIBRARIES, "webview2")
AddReference(join(webview2_dlls, "Microsoft.Web.WebView2.Core.dll"))
AddReference(join(webview2_dlls, "Microsoft.Web.WebView2.Wpf.dll"))
del webview2_dlls

from System import Action, EventArgs, Exception as CSException, Uri, Func, Object as CSObject
from System.Drawing import Color # type: ignore
from System.Threading import ApartmentState, Thread as CSharpThread, ParameterizedThreadStart
from System.Threading.Tasks import Task as CSTask # type: ignore
from System.Windows import Application, ResizeMode, ShutdownMode, Window, WindowState, WindowStyle
from System.Windows.Controls import Grid # type: ignore
from System.Windows.Media import Brushes, ImageSource
from System.Windows.Media.Imaging import BitmapImage # type: ignore
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
from Microsoft.Web.WebView2.Wpf import CoreWebView2CreationProperties, WebView2 # type: ignore

from .bridge import Bridge, serialize_object
from .file_system_dialog import DirectoryPicker, DirectoryPickerOptions, OpenFilePicker, OpenFilePickerOptions, SaveFilePicker, SaveFilePickerOptions

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
	size: Tuple[Optional[int], Optional[int]]
	resizable: bool
	min_size: Tuple[Optional[int], Optional[int]]
	max_size: Tuple[Optional[int], Optional[int]]
	position: Tuple[Optional[int], Optional[int]]
	hide: bool
	frameless: bool
	private_mode: bool
	user_agent: str
	virtual_hosts: Iterable[WebViewVirtualHost]
	api: object
	web_api_permission_bypass: bool

_state_lock = Lock()

def _cross_thread_executor(method: Callable, args: Tuple):
	try: result = method(*args)
	except Exception as e: return (False, e)
	return (True, result)
_cross_thread_delegate = Func[CSObject, CSObject, CSObject](_cross_thread_executor) # type: ignore
def _cross_thread_call[*AT, RT](dispatcher: Optional[Dispatcher], method: Callable[[*AT], RT], args: Tuple[*AT] = ()) -> RT:
	if not dispatcher: raise Exception("UI object is disposed.")
	result: Optional[Tuple[Literal[True], RT] | Tuple[Literal[False], Exception]] = dispatcher.Invoke(_cross_thread_delegate, (method, args))  # type: ignore
	if result is None: raise Exception("UI object is disposed.")
	if result[0] == True: return result[1]
	else: raise result[1]

_window_map: WeakKeyDictionary[Window, "WebViewWindow"] = WeakKeyDictionary()

class WebViewApplication:
	@property
	def stop_at_main_window_closed(self):
		with self.__lock:
			return self.__stop_at_main_window_closed
	@stop_at_main_window_closed.setter
	def stop_at_main_window_closed(self, value: bool):
		with self.__lock:
			self.__stop_at_main_window_closed = bool(value)

	@property
	def main_window(self):
		with self.__lock:
			return self.__main_window
	@main_window.setter
	def main_window(self, value):
		if value is not None and not isinstance(value, WebViewWindow): raise TypeError("Not a WebViewWindow")
		if value and value.closed: raise ValueError("Cannot set a closed window as main window")
		with self.__lock:
			if not self.__running or self.__stopping: raise Exception("WebViewApplication is not running.")
			self.__main_window = value

	def __init__(self, **params: Unpack[WebViewApplicationParameters]):
		self.__configuration = WebViewGlobalConfiguration(params)
		self.__running = False
		self.__application: Optional[Application] = None
		self.__dispatcher: Optional[Dispatcher] = None
		self.__stop_at_main_window_closed = params.get("stop_at_main_window_closed", True)
		self.__main_window: Optional[WebViewWindow] = None
		self.__stopping = False
		self.__lock = Lock()

	def __on_window_closed(self, window: Window, _):
		with self.__lock:
			if _window_map[window] == self.__main_window:
				self.__main_window = None
				if self.__stop_at_main_window_closed:
					self.__stop()
	def create_window(self, **params: Unpack[WebViewWindowParameters]):
		assert self.__dispatcher
		return _cross_thread_call(self.__dispatcher, WebViewWindow, (self.__dispatcher, self.__configuration, params, self.__on_window_closed))

	def __run(self, params: Tuple[Optional[Callable[[Self], Any]], WebViewWindowParameters]):
		self.__running = True
		_state_lock.release()
		app = self.__application = Application()
		self.__dispatcher = app.Dispatcher
		[main, options] = params
		app.ShutdownMode = ShutdownMode.OnExplicitShutdown
		if main:
			self.__lock.release()
			try: main(self)
			except Exception as e:
				print_exception(e)
				return
		else:
			self.__main_window = self.create_window(**options)
			self.__lock.release()
		app.Run()

	def start(self, main: Optional[Callable[[Self], Any]] = None, **params: Unpack[WebViewWindowParameters]):
		global _running_application
		self_lock = self.__lock
		self_lock.acquire()
		_state_lock.acquire()
		try:
			if main is not None and not isfunction(main) and not ismethod(main): raise TypeError("Argument 'main' is not a valid callable object.")
			if current_thread() is not main_thread(): raise RuntimeError("WebViewApplication can start in main thread only.")
			if self.__running: raise Exception("WebViewApplication is already started.")
			if _running_application: raise Exception("A WebViewApplication is already running.")
		except Exception as e:
			_state_lock.release()
			self_lock.release()
			raise e
		_running_application = self
		thread = CSharpThread(ParameterizedThreadStart(self.__run))
		thread.SetApartmentState(ApartmentState.STA)
		thread.Start((main, params))
		thread.Join()
		with _state_lock, self_lock:
			self.__running = self.__stopping = False
			_running_application = self.__dispatcher = None
	def __stop(self):
		if self.__stopping: return
		self.__stopping = True
		assert self.__application
		self.__application.Shutdown()
	def stop(self):
		with self.__lock:
			if self.__running:
				assert self.__dispatcher
				_cross_thread_call(self.__dispatcher, self.__stop)

class WebViewWindowInitializeParameters:
	def __init__(self, global_configuration: WebViewGlobalConfiguration, params: WebViewWindowParameters):
		self.debug_enabled = global_configuration.debug_enabled
		self.user_agent = params.get("user_agent", global_configuration.user_agent)
		self.virtual_hosts = params.get("virtual_hosts", global_configuration.virtual_hosts)
		self.web_api_permission_bypass = params.get("web_api_permission_bypass", global_configuration.web_api_permission_bypass)

class WebViewWindowState(Enum):
	NORMAL = WindowState.Normal
	MINIMIZED = WindowState.Minimized
	MAXIMIZED = WindowState.Maximized

_execute_javascript_delegate = Action[CSTask[str]]

class WebViewWindow:
	def __init__(self, dispatcher: Dispatcher, configuration: WebViewGlobalConfiguration, params: WebViewWindowParameters, on_closed: Callable[[Window, EventArgs], None]):
		self.__closed = False
		self.__dispatcher = dispatcher
		self.__message_notifier = Notifier[Any]()
		self.__on_closed = Notifier[Self]()
		self.__fullscreen: Optional[Tuple[WindowStyle, WindowState]] = None

		window = self.__window = Window()
		_window_map[window] = self
		window.Title = params.get("title", configuration.title)

		size = params.get("min_size")
		if size:
			[min_width, min_height] = size
			if min_width is not None:
				window.MinWidth = min_width
			if min_height is not None:
				window.MinHeight = min_height
		size = params.get("max_size")
		if size:
			[max_width, max_height] = size
			if max_width is not None:
				window.MaxWidth = max_width
			if max_height is not None:
				window.MaxHeight = max_height
		size = params.get("size")
		if size:
			[width, height] = size
			if width is not None:
				window.Width = width
			if height is not None:
				window.Height = height
		window.ResizeMode = ResizeMode.CanResize if params.get("resizable", True) else ResizeMode.NoResize
		position = params.get("position")
		if position:
			[top, left] = position
			if top is not None:
				window.Top = top
			if left is not None:
				window.Left = left

		init_params = WebViewWindowInitializeParameters(configuration, params)
		layout = Grid()
		layout.Background = Brushes.White
		webview = self.__webview = WebView2()
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
		webview.WebMessageReceived += self.__on_javascript_message
		initial_uri = self.__navigate_uri = params.get("initial_uri", "about:blank")
		webview.Source = Uri(initial_uri)

		layout.Background = Brushes.Transparent
		layout.Children.Add(webview)
		window.Content = layout

		closed_event = window.Closed
		closed_event += on_closed
		closed_event += self.__on_window_closed
		if not params.get("hide"): window.Show()
	
	def __show(self):
		self.__window.Show()
	def show(self):
		_cross_thread_call(self.__dispatcher, self.__show)
	def __hide(self):
		self.__window.Hide()
	def hide(self):
		_cross_thread_call(self.__dispatcher, self.__hide)
	@property
	def is_visible(self):
		return self.__window.IsVisible
	
	@property
	def is_fullscreen(self):
		return bool(self.__fullscreen)
	def __enter_fullscreen(self):
		if self.__fullscreen: return
		window = self.__window
		self.__fullscreen = (window.WindowStyle, window.WindowState)
		self.__window.WindowStyle = getattr(WindowStyle, "None")
		self.__window.WindowState = WindowState.Maximized
	def fullscreen(self):
		_cross_thread_call(self.__dispatcher, self.__enter_fullscreen)
	def __exit_fullscreen(self):
		if not self.__fullscreen: return
		window = self.__window
		window.WindowStyle = self.__fullscreen[0]
		window.WindowState = self.__fullscreen[1]
		self.__fullscreen = None
	def exit_fullscreen(self):
		_cross_thread_call(self.__dispatcher, self.__exit_fullscreen)
	def __get_state(self):
		fullscreen = self.__fullscreen
		return WebViewWindowState(fullscreen[1] if fullscreen else self.__window.WindowState)
	@property
	def state(self):
		return _cross_thread_call(self.__dispatcher, self.__get_state)
	def __set_state(self, value: WindowState):
		fullscreen = self.__fullscreen
		if fullscreen:
			self.__fullscreen = (fullscreen[0], value)
		else:
			self.__window.WindowState = value
	@state.setter
	def state(self, value: WebViewWindowState):
		_cross_thread_call(self.__dispatcher, self.__set_state, (value.value,))

	@property
	def closed(self): return self.__closed
	@property
	def on_closed(self): return self.__on_closed
	def __close(self):
		self.__window.Close()
	def close(self):
		_cross_thread_call(self.__dispatcher, self.__close)

	def __get_min_width(self):
		return self.__window.MinWidth
	@property
	def min_width(self):
		return _cross_thread_call(self.__dispatcher, self.__get_min_width)
	def __set_min_width(self, value: float):
		self.__window.MinWidth = value
	@min_width.setter
	def min_width(self, value: float):
		_cross_thread_call(self.__dispatcher, self.__set_min_width, (value,))
	def __get_min_height(self):
		return self.__window.MinHeight
	@property
	def min_height(self):
		return _cross_thread_call(self.__dispatcher, self.__get_min_height)
	def __set_min_height(self, value: float):
		self.__window.MinHeight = value
	@min_height.setter
	def min_height(self, value: float):
		_cross_thread_call(self.__dispatcher, self.__set_min_height, (value,))

	def __get_max_width(self):
		return self.__window.MaxWidth
	@property
	def max_width(self):
		return _cross_thread_call(self.__dispatcher, self.__get_max_width)
	def __set_max_width(self, value: float):
		self.__window.MaxWidth = value
	@max_width.setter
	def max_width(self, value: float):
		_cross_thread_call(self.__dispatcher, self.__set_max_width, (value,))
	def __get_max_height(self):
		return self.__window.MaxHeight
	@property
	def max_height(self):
		return _cross_thread_call(self.__dispatcher, self.__get_max_height)
	def __set_max_height(self, value: float):
		self.__window.MaxHeight = value
	@max_height.setter
	def max_height(self, value: float):
		_cross_thread_call(self.__dispatcher, self.__set_max_height, (value,))

	def __get_width(self):
		return self.__window.Width
	@property
	def width(self):
		return _cross_thread_call(self.__dispatcher, self.__get_width)
	def __set_width(self, value: float):
		self.__window.Width = value
	@width.setter
	def width(self, value: float):
		_cross_thread_call(self.__dispatcher, self.__set_width, (value,))
	def __get_height(self):
		return self.__window.Height
	@property
	def height(self):
		return _cross_thread_call(self.__dispatcher, self.__get_height)
	def __set_height(self, value: float):
		self.__window.Height = value
	@height.setter
	def height(self, value: float):
		_cross_thread_call(self.__dispatcher, self.__set_height, (value,))

	def __get_top(self):
		return self.__window.Top
	@property
	def top(self):
		return _cross_thread_call(self.__dispatcher, self.__get_top)
	def __set_top(self, value: float):
		self.__window.Top = value
	@top.setter
	def top(self, value: float):
		_cross_thread_call(self.__dispatcher, self.__set_top, (value,))
	def __get_left(self):
		return self.__window.Left
	@property
	def left(self):
		return _cross_thread_call(self.__dispatcher, self.__get_left)
	def __set_left(self, value: float):
		self.__window.Left = value
	@left.setter
	def left(self, value: float):
		_cross_thread_call(self.__dispatcher, self.__set_left, (value,))

	@property
	def navigate_uri(self): return self.__navigate_uri
	def __navigate_uri_call(self, value): self.__webview.Source = Uri(value)
	@navigate_uri.setter
	def navigate_uri(self, value: str):
		_cross_thread_call(self.__dispatcher, self.__navigate_uri_call, (value,))
		self.__navigate_uri = value

	def __get_icon(self):
		return self.__window.Icon
	@property
	def icon(self):
		return _cross_thread_call(self.__dispatcher, self.__get_icon)
	def __set_icon(self, value: Optional[ImageSource]):
		self.__window.Icon = value
	@icon.setter
	def icon(self, value: str | ImageSource | None):
		if isinstance(value, str):
			value = BitmapImage(Uri(value))
			value.Freeze()
		elif isinstance(value, ImageSource):
			if not value.IsFrozen:
				raise ValueError("Cannot set icon to non-frozen ImageSource")
		elif value is not None:
			raise ValueError("Value must be str or ImageSource")
		_cross_thread_call(self.__dispatcher, self.__set_icon, (value,))
	
	def __get_resizable(self):
		return self.__window.ResizeMode != ResizeMode.NoResize
	@property
	def resizable(self):
		return _cross_thread_call(self.__dispatcher, self.__get_resizable)
	def __set_resizable(self, value: bool):
		self.__window.ResizeMode = ResizeMode.CanResize if value else ResizeMode.NoResize
	@resizable.setter	
	def resizable(self, value: bool):
		_cross_thread_call(self.__dispatcher, self.__set_resizable, (value,))

	def __on_window_closed(self, _, args: EventArgs):
		self.__closed = True
		self.__dispatcher = None
		self.__on_closed.trigger(self)

	def __on_new_window_request(self, _: CoreWebView2, args: CoreWebView2NewWindowRequestedEventArgs):
		args.Handled = True

	def __on_permission_requested(self, _: CoreWebView2, args: CoreWebView2PermissionRequestedEventArgs):
		args.State = CoreWebView2PermissionState.Allow

	def __on_navigation_start(self, _: WebView2, args: CoreWebView2NavigationStartingEventArgs):
		print("Webview navigation started: " + args.Uri)

	def __on_navigation_completed(self, _: WebView2, args: CoreWebView2NavigationCompletedEventArgs):
		print("Webview navigation completed, status: " + str(args.HttpStatusCode))

	def __on_webview_ready(self, init_params:WebViewWindowInitializeParameters, webview: WebView2, args: CoreWebView2InitializationCompletedEventArgs):
		if not args.IsSuccess:
			print(args.InitializationException)
			raise WebViewException(args.InitializationException)
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
	
	def __post_message(self, message: str):
		assert self.__webview.CoreWebView2
		self.__webview.CoreWebView2.PostWebMessageAsJson(message)
	def post_message(self, message: Any):
		_cross_thread_call(self.__dispatcher, self.__post_message, (dumps(message, ensure_ascii=False, default=serialize_object),))
	
	def __execute_javascript(self, script: str):
		assert self.__webview.CoreWebView2
		return self.__webview.CoreWebView2.ExecuteScriptAsync(script)
	def execute_javascript(self, script: str):
		task = _cross_thread_call(self.__dispatcher, self.__execute_javascript, (script,))
		future = Future()
		task.ContinueWith(_execute_javascript_delegate(lambda task: future.set_result(task.Result)))
		return future
	def __on_javascript_message(self, _, args):
		self.__message_notifier.trigger(loads(args.WebMessageAsJson))
	@property
	def message_notifier(self):
		return self.__message_notifier

	def show_open_file_picker(self, **options: Unpack[OpenFilePickerOptions]):
		picker = _cross_thread_call(self.__dispatcher, OpenFilePicker)
		picker.set_options(options)
		_cross_thread_call(self.__dispatcher, picker.show_dialog, (self.__window,))
		return picker.parse_result()

	def show_save_file_picker(self, **options: Unpack[SaveFilePickerOptions]):
		picker = _cross_thread_call(self.__dispatcher, SaveFilePicker)
		picker.set_options(options)
		_cross_thread_call(self.__dispatcher, picker.show_dialog, (self.__window,))
		return picker.parse_result()
	
	def show_directory_picker(self, **options: Unpack[DirectoryPickerOptions]):
		picker = _cross_thread_call(self.__dispatcher, DirectoryPicker)
		picker.set_options(options)
		_cross_thread_call(self.__dispatcher, picker.show_dialog, (self.__window,))
		return picker.parse_result()

_running_application: Optional[WebViewApplication] = None
def get_running_application():
	with _state_lock: return _running_application
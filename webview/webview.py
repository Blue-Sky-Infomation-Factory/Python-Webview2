from re import match
import clr
from json import dumps
from os import getenv
from os.path import dirname, join
from queue import Queue
from threading import current_thread, main_thread
from tkinter import Frame, Label, Tk
from tkinter.filedialog import askdirectory, askopenfilename, asksaveasfile
from traceback import print_exception
from typing import Any, Callable, Iterable, List, Optional, Tuple, TypedDict, Unpack
from win32gui import SetParent, MoveWindow, GetParent, SetWindowLong, GetWindowLong
from win32con import GWL_STYLE, WS_CAPTION, WS_THICKFRAME
from ctypes import windll, c_uint, byref, sizeof

from .bridge import Bridge, serialize_object
from .handlers import Handlers

clr.AddReference("System.Windows.Forms") # type: ignore
clr.AddReference("System.Threading") # type: ignore
self_path = dirname(__file__)
clr.AddReference(join(self_path, "Microsoft.Web.WebView2.Core.dll")) # type: ignore
clr.AddReference(join(self_path, "Microsoft.Web.WebView2.WinForms.dll")) # type: ignore
del self_path

from Microsoft.Web.WebView2.Core import CoreWebView2PermissionState, CoreWebView2HostResourceAccessKind # type: ignore
from Microsoft.Web.WebView2.WinForms import WebView2, CoreWebView2CreationProperties # type: ignore
from System import Uri # type: ignore
from System.Drawing import Color # type: ignore
from System.Threading import Thread, ApartmentState, ParameterizedThreadStart # type: ignore

# Windows DWM API
DwmSetWindowAttribute = windll.dwmapi.DwmSetWindowAttribute
DWMWA_CAPTION_COLOR = 35

class WebViewStartParameters(TypedDict, total=False):
	size: Optional[Tuple[int, int]]
	position: Optional[Tuple[int, int]]
	hide: bool
	borderless: bool
	background_transparent: bool # not implemented
	icon: str
	title: str
	window_caption_color: str

class WebViewException(Exception):
	def __init__(self, exception):
		super().__init__(exception.Message)
		self.raw = exception

class WebViewConfiguration:
	def __init__(self,
			data_folder: str = getenv("TEMP") + "/Microsoft WebView", # type: ignore
			private_mode = True,
			debug_enabled = False,
			user_agent:Optional[str] = None,
			api: object = None,
			web_api_permission_bypass: bool = False,
			vhost_path: Optional[str] = None,
			vhost_name: str = "webview",
			vhost_cors: bool = True,
			min_size: Tuple[int, int] = (384, 256),
			max_size: Optional[Tuple[int, int]] = None
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

state_dict={
	"zoomed": "maximized",
	"iconic": "minimized",
	"withdrawn": "hidden",
	"normal": "normal"
}

def _parse_color(value: str) -> int:
	value = value.strip()
	match_rs = match(r"^rgb\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)$", value)
	if match_rs:
		return int(match_rs[3]) << 16 | int(match_rs[2]) << 8 | int(match_rs[1])
	match_rs = match(r"^#([\dA-Fa-f]{3,6})$", value)
	if match_rs:
		temp = match_rs[1]
		match len(temp):
			case 6:
				return int(temp[4:6], 16) << 16 | int(temp[2:4], 16) << 8 | int(temp[0:2], 16)
			case 3:
				return int(temp[2] * 2, 16) << 16 | int(temp[1] * 2, 16) << 8 | int(temp[0] * 2, 16)
			case _: pass
	raise Exception("Invalid color string.")

def _event_once(tk: Tk, event: str, func: Callable, args: Iterable = tuple()):
	def wrapped_func(event_obj):
		tk.unbind(event, bound_id)
		func(*args, event_obj)
	bound_id = tk.bind(event, wrapped_func, True)

class WebViewApplication:

	def __init__(self, configuration: WebViewConfiguration = WebViewConfiguration()):
		self.__configuration = configuration
		self.__thread: Optional[Thread] = None
		self.__title = "WebView Application"
		self.__root: Optional[Tk] = None
		self.__frame: Optional[Frame | Label] = None
		self.__webview: Optional[WebView2] = None
		self.__webview_hwnd: Optional[int] = None
		self.__navigate_uri = "about:blank"
		self.__message_handlers = Handlers()
		self.__call_queue: Queue[Tuple[Callable, Tuple]] = Queue()

	def __resize_webview(self, *_):
		assert self.__root and self.__frame and self.__webview_hwnd
		frame = self.__frame
		MoveWindow(self.__webview_hwnd, 0,0, frame.winfo_width(), frame.winfo_height(), False)

	def __call_handler(self, _):
		queue = self.__call_queue
		task = queue.get(block=False)
		queue.task_done()
		task[0](*task[1])

	def __borderlessfy(self, *_):
		root = self.__root
		hwnd = GetParent(root.winfo_id()) # type: ignore
		SetWindowLong(hwnd, GWL_STYLE, GetWindowLong(hwnd, GWL_STYLE) & ~(WS_CAPTION | WS_THICKFRAME)) # type: ignore

	def __run(self, keywords: WebViewStartParameters):
		configuration = self.__configuration
		root = self.__root = Tk()
		caption_color = keywords.get("window_caption_color", None)
		if caption_color is not None: _event_once(root, "<Map>", self.__set_window_caption_color, (_parse_color(caption_color),))
		if keywords.get("borderless", False): _event_once(root, "<Map>", self.__borderlessfy)
		title = keywords.get("title", None)
		if title is not None: self.__title = title
		root.title(self.__title)
		icon = keywords.get("icon")
		if icon: root.iconbitmap(icon)
		root.minsize(*configuration.min_size)
		if configuration.max_size: root.maxsize(*configuration.max_size)
		size=keywords.get("size")
		position=keywords.get("position")
		if size or position: root.geometry((f"{size[0]}x{size[1]}" if size else "") + (f"+{position[0]}+{position[1]}" if position else ""))
		if keywords.get("hide"): root.withdraw()
		frame = self.__frame = Frame(root)
		frame.configure(background="#FFF")
		frame.pack(fill="both", expand=True)
		frame_id = frame.winfo_id()
		webview = self.__webview = WebView2()
		webview_properties = CoreWebView2CreationProperties()
		webview_properties.UserDataFolder = configuration.data_folder
		webview_properties.IsInPrivateModeEnabled = configuration.private_mode
		webview_properties.AdditionalBrowserArguments = "--disable-features=ElasticOverscroll"
		webview.CreationProperties = webview_properties
		webview.DefaultBackgroundColor = Color.Transparent
		webview.CoreWebView2InitializationCompleted += self.__on_webview_ready
		webview.NavigationStarting += self.__on_navigation_start
		webview.NavigationCompleted += self.__on_navigation_completed
		webview.WebMessageReceived += self.__on_javascript_message
		webview.Source = Uri(self.__navigate_uri)
		webview_handle = self.__webview_hwnd = webview.Handle.ToInt32()
		SetParent(webview_handle, frame_id)
		frame.bind("<Configure>", self.__resize_webview)
		root.bind("<<AppCall>>", self.__call_handler)
		root.mainloop()
		self.__root = self.__frame = self.__webview = self.__webview_hwnd = None

	def start(self, uri: Optional[str] = None, **keywords: Unpack[WebViewStartParameters]):
		global running_application
		assert (current_thread() is main_thread()), "WebView can start in main thread only."
		assert not self.__thread, "WebView is already started."
		if uri: self.__navigate_uri = uri
		thread = Thread(ParameterizedThreadStart(self.__run))
		self.__thread = thread
		thread.SetApartmentState(ApartmentState.STA)
		thread.Start(keywords)
		running_application = self
		thread.Join()
		running_application = self.__thread = None

	def stop(self):
		assert self.__root, "WebView is not started."
		self.__root.quit()

	def __on_new_window_request(self, _, args):
		args.set_Handled(True)

	def __on_webview_ready(self, webview_instance, args):
		if not args.IsSuccess:
			print_exception(WebViewException(args.InitializationException))
			return
		configuration = self.__configuration
		core = webview_instance.CoreWebView2
		core.NewWindowRequested += self.__on_new_window_request
		if configuration.web_api_permission_bypass: core.PermissionRequested += self.__on_permission_requested
		Bridge(core, self.__configuration.api)
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
		print("Webview navigation started: " + args.Uri)

	def __on_navigation_completed(self, _, args):
		print("Webview navigation completed, status: " + str(args.HttpStatusCode))

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

	def set_icon(self, file_path: str):
		assert self.__root, "WebView is not started."
		self.__root.iconbitmap(file_path)

	@property
	def size(self):
		root = self.__root
		assert root, "WebView is not started."
		return root.winfo_width(), root.winfo_height()
	def resize(self, width:int, height:int):
		assert self.__root, "WebView is not started."
		self.__root.geometry(f"{width}x{height}")

	@property
	def position(self):
		root = self.__root
		assert root, "WebView is not started."
		return root.winfo_x(), root.winfo_y()
	def move(self, x:int, y:int):
		assert self.__root, "WebView is not started."
		self.__root.geometry(f"+{x}+{y}")

	@property
	def state(self):
		assert self.__root, "WebView is not started."
		return state_dict.get(self.__root.state(), "unknown")
	def show(self):
		assert self.__root, "WebView is not started."
		self.__root.deiconify()
	def hide(self):
		assert self.__root, "WebView is not started."
		self.__root.withdraw()
	def maximize(self):
		assert self.__root, "WebView is not started."
		self.__root.state("zoomed")
	def minimize(self):
		assert self.__root, "WebView is not started."
		self.__root.iconify()
	def normalize(self):
		assert self.__root, "WebView is not started."
		self.__root.state("normal")

	@property
	def is_fullscreen(self):
		assert self.__root, "WebView is not started."
		return bool(self.__root.attributes("-fullscreen"))
	def fullscreen(self):
		assert self.__root, "WebView is not started."
		self.__root.attributes("-fullscreen", True)
	def exit_fullscreen(self):
		assert self.__root, "WebView is not started."
		self.__root.attributes("-fullscreen", False)

	def show_open_file_picker(
		self,
		multiple: bool = True,
		initial_directory: Optional[str] = None,
		initial_file_name: Optional[str] = None,
		title: Optional[str] = None,
		file_types: Iterable[Tuple[str, str | List[str] | Tuple[str, ...]]] = [],
	) -> Tuple[str, ...] | None:
		result=askopenfilename(
			parent=self.__root,
			multiple=multiple, # type: ignore
			initialdir=initial_directory,
			initialfile=initial_file_name,
			title=title,
			filetypes=file_types
		)
		if not result: return None
		return (result,) if not multiple else result
	def show_save_file_picker(
		self,
		overwrite: bool = False,
		binary: bool = False,
		initial_directory: Optional[str] = None,
		initial_file_name: Optional[str] = None,
		title: Optional[str] = None,
		file_types: Iterable[Tuple[str, str | List[str] | Tuple[str, ...]]] = [("all", "*")],
	):
		return asksaveasfile(
			mode=("w+" if overwrite else "a+") + ("b" if binary else ""),
			parent=self.__root,
			initialdir=initial_directory,
			initialfile=initial_file_name,
			title=title,
			filetypes=file_types
		)
	def show_directory_picker(self, initial_directory: Optional[str] = None, title: Optional[str] = None ) -> str | None:
		return askdirectory(parent=self.__root, initialdir=initial_directory, title=title, mustexist=True)
	
	@property
	def title(self): return self.__title
	@title.setter
	def title(self, value: str):
		self.__title = value
		root = self.__root
		if root: root.title(value)

	def __set_window_caption_color(self, value: int, *_):
		assert self.__root, "WebView is not started."
		temp = c_uint(value)
		DwmSetWindowAttribute(GetParent(self.__root.winfo_id()), DWMWA_CAPTION_COLOR, byref(temp), sizeof(temp))

	def set_window_caption_color(self, value: str):
		"""
		value format:
		rgb(255,255,255) |
		#RRGGBB |
		#RGB
		"""
		self.__set_window_caption_color(_parse_color(value))

running_application: Optional[WebViewApplication] = None
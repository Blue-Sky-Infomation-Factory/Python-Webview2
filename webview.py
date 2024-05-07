from time import sleep
from tkinter import Frame, Tk
from traceback import print_exception
from typing import Optional, Tuple
import os
import clr
from win32gui import SetParent, MoveWindow

clr.AddReference('System.Windows.Forms') # type: ignore
clr.AddReference('System.Collections') # type: ignore
clr.AddReference('System.Threading') # type: ignore
clr.AddReference(os.path.dirname(__file__) + '/Microsoft.Web.WebView2.Core.dll') # type: ignore
clr.AddReference(os.path.dirname(__file__) + '/Microsoft.Web.WebView2.WinForms.dll') # type: ignore
clr.AddReference(os.path.dirname(__file__) + '/PythonMicrosoftWebView2Bridge.dll') # type: ignore

from System.Drawing import Color # type: ignore
from Microsoft.Web.WebView2.WinForms import WebView2, CoreWebView2CreationProperties # type: ignore
from Microsoft.Web.WebView2.Core import CoreWebView2PermissionState, CoreWebView2HostResourceAccessKind # type: ignore
from System import Uri # type: ignore
from System.Threading import Thread, ThreadStart, ApartmentState # type: ignore
from PythonMicrosoftWebView2Bridge import Bridge # type: ignore

class WebViewException(Exception):
	def __init__(self, exception):
		super(WebViewException, self).__init__(exception.Message)
		self.raw = exception

class WebViewConfiguration:
	def __init__(self,
			dataFolder: str = os.getenv('TEMP') + '/Microsoft WebView', # WebView 数据文件夹 # type: ignore
			privateMode = True, # 隐私模式
			debugEnabled = False, # 启用调试特性
			userAgent:Optional[str] = None, # 用户代理标识
			api: object = None, # 向 WebView 暴露的 API 对象
			webApiPermissionPypass: bool = False, # 自动允许 Web API 的权限请求
			vHostPath: Optional[str] = None, # vHost 映射的文件夹路径
			vHostName: str = "webview", # vHost 的域名
			vHostCORS: bool = True, # 是否允许 vHost 访问外部资源
			minSize: Tuple[int, int] = (384, 256), # 窗口显示区最小尺寸
			maxSize: Optional[Tuple[int, int]] = None # 窗口显示区最大尺寸
		):
		self.dataFolder = dataFolder
		self.privateMode = privateMode
		self.debugEnabled = debugEnabled
		self.userAgent = userAgent
		self.api = api
		self.webApiPermissionPypass = webApiPermissionPypass
		self.vHostPath = vHostPath
		self.vHostName = vHostName
		self.vHostCORS = vHostCORS
		self.minSize = minSize
		self.maxSize = maxSize

class WebViewApplication:
	def __init__(self, configuration: WebViewConfiguration = WebViewConfiguration(), title = 'WebView Application'):
		self.__configuration = configuration
		self.__thread: Optional[Thread] = None
		self.__title = title
		self.__root: Optional[Tk] = None
		self.__frame: Optional[Frame] = None
		self.__webView: Optional[WebView2] = None
		self.__webViewHwnd: Optional[int] = None
		self.__navigateUri = ""
		self.__startParam = None

	def __resizeWebView(self, _ = None):
		assert self.__root and self.__frame and self.__webViewHwnd
		frame = self.__frame
		MoveWindow(self.__webViewHwnd, 0,0, frame.winfo_width(), frame.winfo_height(), False)

	def __run(self):
		configuration = self.__configuration
		root = self.__root = Tk()
		root.title(self.__title)
		root.minsize(*configuration.minSize)
		if configuration.maxSize: root.maxsize(*configuration.maxSize)
		
		frame = self.__frame = Frame(root)
		frame.pack(fill="both",expand=True)
		frameId = frame.winfo_id()
		webView = self.__webView = WebView2()
		webViewProperties = CoreWebView2CreationProperties()
		webViewProperties.UserDataFolder = configuration.dataFolder
		webViewProperties.set_IsInPrivateModeEnabled(configuration.privateMode)
		webViewProperties.AdditionalBrowserArguments = '--disable-features=ElasticOverscroll'
		webView.CreationProperties = webViewProperties
		webView.DefaultBackgroundColor = Color.White # 默认底色
		webView.CoreWebView2InitializationCompleted += self.__onWebviewReady # WebView 初始化完成回调
		webView.NavigationStarting += self.__onNavigationStart # WebView 导航开始回调
		webView.NavigationCompleted += self.__onNavigationCompleted # WebView 导航完成回调
		webView.WebMessageReceived += self.__onJavaScriptMessage # WebView JS 消息回调
		webView.Source = Uri(self.__navigateUri)
		webViewHandle = self.__webViewHwnd = webView.Handle.ToInt32()
		SetParent(webViewHandle, frameId)
		frame.bind('<Configure>', self.__resizeWebView)
		self.__startParam = None
		root.mainloop()
		self.__root = self.__frame = self.__webView = self.__webViewHwnd = None

	def start(self, uri: Optional[str] = None, width = 384, height = 256):
		if self.__thread: raise Exception("WebView is already started.")
		if uri: self.__navigateUri = uri
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
	def navigateUri(self): return self.__navigateUri
	@navigateUri.setter
	def navigateUri(self, value):
		self.__navigateUri = value
		if self.__webView: self.__webView.Source = Uri(value)

	def __onNewWindowRequest(self, webViewInstance, args):
		args.set_Handled(True)

	def __scriptCallHandler(self, methodName: str, args: list):
		print(methodName, args)

	def __onWebviewReady(self, webViewInstance, args):
		if not args.IsSuccess:
			print_exception(WebViewException(args.InitializationException))
			return
		configuration = self.__configuration
		core = webViewInstance.CoreWebView2
		core.NewWindowRequested += self.__onNewWindowRequest
		if configuration.webApiPermissionPypass: core.PermissionRequested += self.__onPermissionRequested
		global inspect 
		inspect = Bridge(configuration.api)
		if configuration.api:
			core.AddHostObjectToScript("api", inspect)
			Thread(target=doInspect).start()
		debugEnabled = configuration.debugEnabled
		settings = core.Settings
		settings.AreBrowserAcceleratorKeysEnabled = debugEnabled
		settings.AreDefaultContextMenusEnabled = debugEnabled
		settings.AreDefaultScriptDialogsEnabled = True
		settings.AreDevToolsEnabled = debugEnabled
		settings.IsBuiltInErrorPageEnabled = True
		settings.IsScriptEnabled = True
		settings.IsWebMessageEnabled = True
		settings.IsStatusBarEnabled = False
		settings.IsSwipeNavigationEnabled = False
		settings.IsZoomControlEnabled = False

		ua = configuration.userAgent
		if ua: settings.UserAgent = ua

		vHost = configuration.vHostPath
		if vHost: core.SetVirtualHostNameToFolderMapping(configuration.vHostName, vHost, CoreWebView2HostResourceAccessKind.DenyCors if configuration.vHostCORS else CoreWebView2HostResourceAccessKind.Deny)

		# cookies persist even if UserDataFolder is in memory. We have to delete cookies manually.
		if configuration.privateMode: core.CookieManager.DeleteAllCookies()

		if debugEnabled: core.OpenDevToolsWindow()

	def __onNavigationStart(self, webViewInstance, args):
		print('Webview navigation started: ' + args.Uri)

	def __onNavigationCompleted(self, webViewInstance, args):
		print('Webview navigation completed, status: ' + str(args.HttpStatusCode))
		# self.Show()

	def __onPermissionRequested(self, webViewInstance, args):
		args.State = CoreWebView2PermissionState.Allow

	def __onJavaScriptMessage(self, webViewInstance, args):
		data = args.WebMessageAsJson
		print(data)
		print(args.AdditionalObjects)

inspect = None
def doInspect():
	while True:
		if inspect.inspect is not None:
			print(inspect.inspect)
			inspect.inspect = None
		sleep(1)

a = WebViewApplication(WebViewConfiguration(debugEnabled= True))
a.start("https://bsif.netlify.app")
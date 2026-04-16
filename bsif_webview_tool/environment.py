from os import getenv, remove, mkdir
from os.path import join, dirname, exists, abspath
from platform import system
from shutil import copyfile, copytree, rmtree
from subprocess import run
from urllib.request import urlopen
from winreg import OpenKey, QueryValueEx, HKEY_LOCAL_MACHINE

BUNDLED_DOTNET_RUNTIME = join(abspath(join(dirname(__file__), "..", "bsif_webview")), "libs", "dotnet")

class DotNetRuntimeInfo:
	def __init__(self, info_string: str):
		end = info_string.index(" ")
		self.type = info_string[:end]
		index = end + 1
		end = info_string.index(" ", index)
		version_string = info_string[index:end]
		self.version = tuple(map(int, version_string.split(".")))
		self.location = join(info_string[end + 2:-1], version_string)
	@classmethod
	def list(cls):
		try:
			return [cls(info) for info in run("dotnet --list-runtimes", capture_output=True).stdout.decode("utf-8").splitlines() if info]
		except:
			return []

def check_environment():
	os = system() == "Windows"
	result={
		"os": os,
		"dotnet": False,
		"webview": False,
		"webview_version": None
	}
	if not os: return result
	# check dotnet
	for info in DotNetRuntimeInfo.list():
		if info.type == "Microsoft.WindowsDesktop.App" and info.version[0] >= 10:
			result["dotnet"]=True
			break
	# check webview
	try:
		result["webview_version"]=QueryValueEx(
			OpenKey(HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"),
			"pv"
		)[0]
		result["webview"]=True
	except: pass
	return result

def install_webview():
	resource = urlopen("https://go.microsoft.com/fwlink/p/?LinkId=2124703")
	path = join(getenv("TEMP"), "MicrosoftEdgeWebview2Setup.exe") # type: ignore
	with open(path, "wb") as file: file.write(resource.read())
	code = run(path).returncode
	remove(path)
	return code

def install_dotnet_runtime():
	resource = urlopen("https://builds.dotnet.microsoft.com/dotnet/WindowsDesktop/10.0.6/windowsdesktop-runtime-10.0.6-win-x64.exe")
	path = join(getenv("TEMP"), "DotnetWindowsDesktopRuntime10.0.6.exe") # type: ignore
	with open(path, "wb") as file: file.write(resource.read())
	code = run((path, "/quiet", "/norestart")).returncode
	remove(path)
	return code

def bundle_dotnet_runtime(minimal: bool = False):
	from sys import modules
	if "bsif_webview.webview" in modules:
		print(f"bundle_dotnet_runtime() cannot work properly in current environment. Try using 'python -m bsif_webview_tool bundle_dotnet_runtime{' --minimal' if minimal else ''}'.")
		return
	runtime = None
	runtime_list = DotNetRuntimeInfo.list()
	for info in runtime_list:
		if info.type == "Microsoft.WindowsDesktop.App" and info.version[0] >= 10:
			runtime = info.location
			break
	if not runtime:
		raise FileNotFoundError("Cannot find dotnet desktop runtime 10 or higher")
	if exists(BUNDLED_DOTNET_RUNTIME):
		rmtree(BUNDLED_DOTNET_RUNTIME)
	if minimal:
		mkdir(BUNDLED_DOTNET_RUNTIME)
		for file in [
			"D3DCompiler_47_cor3.dll",
			"DirectWriteForwarder.dll",
			"PresentationCore.dll",
			"PresentationFramework.Classic.dll",
			"PresentationFramework.dll",
			"PresentationNative_cor3.dll",
			"ReachFramework.dll",
			"System.Configuration.ConfigurationManager.dll",
			"System.IO.Packaging.dll",
			"System.Printing.dll",
			"System.Private.Windows.Core.dll",
			"System.Windows.Extensions.dll",
			"System.Windows.Primitives.dll",
			"System.Xaml.dll",
			"UIAutomationProvider.dll",
			"UIAutomationTypes.dll",
			"WindowsBase.dll",
			"wpfgfx_cor3.dll"
		]:
			copyfile(join(runtime, file), join(BUNDLED_DOTNET_RUNTIME, file))
	else:
		copytree(runtime, BUNDLED_DOTNET_RUNTIME)

from os import getenv, remove
from os.path import join, dirname, abspath
from platform import system
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
	result["dotnet"]=QueryValueEx(
		OpenKey(HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full"),
		'Release'
	)[0] >= 533320 # .NET 4.8.1
		# 4.6.2: 394802
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
	resource = urlopen("https://go.microsoft.com/fwlink/?linkid=2203305")
	path = join(getenv("TEMP"), "DotneFramework4.8.1.exe") # type: ignore
	with open(path, "wb") as file: file.write(resource.read())
	code = run(path, shell=True).returncode
	remove(path)
	return code

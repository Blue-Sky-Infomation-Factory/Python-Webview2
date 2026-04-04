from os import getenv, remove
from os.path import join
from platform import system
from subprocess import run
from urllib.request import urlopen
from winreg import OpenKey, QueryValueEx, HKEY_LOCAL_MACHINE

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
	try:
		result["dotnet"]=QueryValueEx(
			OpenKey(HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full"),
			'Release'
		)[0] >= 394802 # .NET 4.6.2
	except: pass
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
	resource=urlopen("https://go.microsoft.com/fwlink/p/?LinkId=2124703")
	path=join(getenv("TEMP"), "MicrosoftEdgeWebview2Setup.exe") # type: ignore
	with open(path, "wb") as file: file.write(resource.read())
	code=run(path).returncode
	remove(path)
	return code
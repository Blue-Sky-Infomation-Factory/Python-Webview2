from clr import AddReference
from os.path import isdir, isfile, join, dirname
from os import listdir
from platform import machine, system

PACKAGE = dirname(__file__)
LIBRARIES = join(PACKAGE, "libs")
ARCHITECTURE = machine()
OS = system()
PLATFORM_MAP = {
	"AMD64": "win-x64",
	"ARM64": "win-arm64",
	"x86": "win-x86",
	"x86_64": "win-x64",
}
DOTNET_DESKTOP_RUNTIME = "C:/Program Files/dotnet/shared/Microsoft.WindowsDesktop.App"
def version_sort(version_str: str):
	return tuple(map(int, version_str.split('.')))
def find_desktop_runtime_dll(dll_name: str):
	if isdir(DOTNET_DESKTOP_RUNTIME):
		versions = listdir(DOTNET_DESKTOP_RUNTIME)
		versions.sort(key=version_sort, reverse=True)
		for version in versions:
			path = join(DOTNET_DESKTOP_RUNTIME, version)
			if not isdir(path):
				continue
			dll = join(path, dll_name)
			if isfile(dll):
				return dll
	dll = join(PACKAGE, "libs", dll_name)
	if isfile(dll):
		return dll
	return None

def load_desktop_runtime_dll(dll_name: str):
	dll = find_desktop_runtime_dll(dll_name)
	if not dll:
		raise FileNotFoundError(f"Could not find {dll_name}")
	AddReference(dll)

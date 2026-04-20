from os.path import join, dirname
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

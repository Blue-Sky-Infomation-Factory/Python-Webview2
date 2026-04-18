def print_help():
	print(
"""Usage: python -m bsif_webview <command> [options]

Commands:
    help: Show this help message.
    install_runtimes: Install Webview2 and .Net Desktop Runtime.
    bundle_dotnet_runtime: Bundle .Net Desktop Runtime.
        --minimal: Bundle minimal runtime.
""")
	exit()

if __name__ != "__main__":
	print_help()

from sys import argv

args = argv[1:]
if not args:
	print_help()

def install_runtimes():
	from .environment import check_environment, install_webview, install_dotnet_desktop
	env = check_environment()
	if env['webview']:
		print("Webview2 is already installed.")
	else:
		print("Installing Webview2...")
		install_webview()
	if env['dotnet']:
		print(".Net Desktop Runtime is already installed.")
	else:
		print("Installing .Net Desktop Runtime...")
		install_dotnet_desktop()
	print("Runtimes installation completed.")

def bundle_dotnet_runtime(args):
	from .environment import bundle_dotnet_runtime
	print("Bundling .Net Desktop Runtime...")
	bundle_dotnet_runtime("--minimal" in args)
	print("Bundling completed.")

match args[0]:
	case "help":
		print_help()
	case "install_runtimes":
		install_runtimes()
	case "bundle_dotnet_runtime":
		bundle_dotnet_runtime(args[1:])
	case _:
		print("Unknown command.\n")
		print_help()

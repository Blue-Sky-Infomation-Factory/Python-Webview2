def print_help():
	print(
"""Usage: python -m bsif_webview <command> [options]

Commands:
    help: Show this help message.
    install_runtimes: Install Webview2 and .Net Framework.
""")
	exit()

if __name__ != "__main__":
	print_help()

from sys import argv

args = argv[1:]
if not args:
	print_help()

def install_runtimes():
	from .environment import check_environment, install_webview, install_dotnet_runtime
	env = check_environment()
	if env['webview']:
		print("Webview2 is already installed.")
	else:
		print("Installing Webview2...")
		install_webview()
	if env['dotnet']:
		print(".Net Framework is already installed.")
	else:
		print("Installing .Net Framework...")
		install_dotnet_runtime()
	print("Runtimes installation completed.")

match args[0]:
	case "help":
		print_help()
	case "install_runtimes":
		install_runtimes()
	case _:
		print("Unknown command.\n")
		print_help()

from setuptools import setup
import re

with open("README.md", "r") as file:
    readme = file.read()
lines = readme.split("\n")
lines_end = len(lines)
start_index = None
for i in range(lines_end):
    if lines[i] == "## Third-party licenses":
        start_index = i + 1
        break
if start_index is not None:
    prefix = "https://github.com/Blue-Sky-Infomation-Factory/Python-Webview2/blob/main/"
    for i in range(start_index, lines_end):
        line = lines[i]
        if not line: break
        href_start = re.search(r"^- \[.*?\]\((.*?)\)$", line).regs[1][0] # type: ignore
        lines[i] = f"{line[:href_start]}{prefix}{line[href_start:]}"
readme = "\n".join(lines)

setup(
	name="bsif-webview2",
	version="2.0.2",
	author="Blue Sky Infomation Factory",
	description="Microsoft Webview2 for python.",
	long_description=readme,
	long_description_content_type="text/markdown",
	packages=["bsif_webview", "bsif_webview_tool"],
	package_data={
		"bsif_webview": [
			"bridge.js",
			"libs/*.dll",
			"libs/webview2/*.dll",
			"libs/webview2/runtimes/*/native/WebView2Loader.dll",
			"libs/windows_api_code_pack/*.dll"
		]
	},
	license="BSD 3-Clause License",
	python_requires=">=3.11",
	install_requires=["pythonnet", "bsif-utils"],
	classifiers=[
		"License :: OSI Approved :: BSD License",
		"Operating System :: Microsoft :: Windows :: Windows 10",
		"Operating System :: Microsoft :: Windows :: Windows 11",
		"Programming Language :: Python :: Implementation :: CPython",
		"Programming Language :: Python :: 3"
	],
	url="https://github.com/Blue-Sky-Infomation-Factory/Python-Webview2"
)

# python setup.py bdist_wheel --python-tag cp311 --plat-name win_amd64
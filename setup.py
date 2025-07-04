from setuptools import setup, find_packages

with open('README.md', 'r') as file:
    readme = file.read()

setup(
	name="bsif-webview2",
	version="1.4.0",
	author="Blue Sky Infomation Factory",
	description="Microsoft Webview2 for python.",
	long_description=readme,
	long_description_content_type="text/markdown",
	packages=find_packages(),
	package_data={
		"webview": [
			"bridge.js",
			"*.dll",
			"runtimes/*/native/WebView2Loader.dll"
		]
	},
	license="BSD 3-Clause License",
	python_requires=">=3.11",
	install_requires=["pythonnet", "pywin32"],
	classifiers=[
		"License :: OSI Approved :: BSD License",
		"Operating System :: Microsoft :: Windows :: Windows 10",
		"Operating System :: Microsoft :: Windows :: Windows 11",
		"Programming Language :: Python :: Implementation :: CPython",
		"Programming Language :: Python :: 3.11",
		"Programming Language :: Python :: 3.12"
	],
	url="https://github.com/Blue-Sky-Infomation-Factory/Python-Webview2"
)

# python setup.py bdist_wheel --python-tag cp311 --plat-name win_amd64
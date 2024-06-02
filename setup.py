from setuptools import setup, find_packages

setup(
    name="bsif-webview2",
    version="1.0.0",
    author="Blue Sky Infomation Factory",
    description="Microsoft Webview2 for python.",
    packages=find_packages(),
    package_data={
        "webview": [
			"bridge.js",
			"*.dll",
			"runtimes/*/native/WebView2Loader.dll"
		]
    },
    license="BSD 3-Clause License",
    python_requires=">=3.9",  # Windows 8
    install_requires=["pythonnet", "pywin32"],
    classifiers=[
        "License :: OSI Approved :: BSD License",
        "Operating System :: Microsoft :: Windows",
        "Programming Language :: Python :: 3.9",
    ],
	url="https://github.com/Blue-Sky-Infomation-Factory/Python-Webview2"
)

# python setup.py bdist_wheel
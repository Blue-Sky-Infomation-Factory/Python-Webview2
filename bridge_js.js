"use strict";
{
	const { parse, stringify } = JSON,
		{ Call, methodNames } = chrome.webview.hostObjects.sync.bridge,
		syncApi = Object.create(null),
		webview = {
			postMessage: chrome.webview.postMessage,
			syncApi
		};
	function boundMethod(methodName, ...args) { return parse(Call(methodName, stringify(args))) }
	for (const name of methodNames) syncApi[name] = boundMethod.bind(null, name);
	Object.freeze(webview);
	Object.defineProperty(window, "webview", { value: webview, writable: false, configurable: false, enumerable: false });
}
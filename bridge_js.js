"use strict";
{
	Object.getPrototypeOf(Uint8Array).prototype.toJSON = function toJSON() { return Array.from(this) };
	const { parse, stringify } = JSON,
		webview = chrome.webview,
		{
			sync: {
				bridge: { Call: syncCall, methodNames }
			},
			bridge: { Call: asyncCall }
		} = webview.hostObjects,
		syncApi = Object.create(null),
		asyncApi = Object.create(null);
	function syncMethod(methodName, ...args) { return parse(syncCall(methodName, stringify(args))) }
	async function asyncMethod(methodName, ...args) { return parse(await asyncCall(methodName, stringify(args))) }
	for (const name of methodNames) {
		syncApi[name] = syncMethod.bind(null, name);
		asyncApi[name] = asyncMethod.bind(null, name);
	}
	Object.defineProperty(window, "webview", {
		value: Object.freeze({
			syncApi, asyncApi,
			postMessage: webview.postMessage,
			addMessageListener: webview.addEventListener.bind(undefined, "message"),
			removeMessageListener: webview.removeEventListener.bind(undefined, "message")
		}),
		writable: false,
		configurable: false,
		enumerable: false
	});
}
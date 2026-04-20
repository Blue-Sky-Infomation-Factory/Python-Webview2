"use strict";
{
	Object.getPrototypeOf(Uint8Array).prototype.toJSON = function toJSON() { return Array.from(this) };
	const { parse, stringify } = JSON,
		webview = chrome.webview,
		{
			sync: {
				bridge: { SyncCall: syncCall, methodNames }
			},
			bridge: { AsyncCall: asyncCall }
		} = webview.hostObjects,
		syncApi = Object.create(null),
		asyncApi = Object.create(null);
	function syncMethod(methodName, ...args) {
		try {
			return parse(syncCall(methodName, stringify(args)))
		} catch (error) {
			error = parse(error.message);
			if (error) {
				const newError = new Error(error[1]);
				newError.name = error[0];
				throw newError;
			} else {
				throw new Error("Webview bridge cannot handle the value that remote function returned.");
			}
		}
	}
	async function asyncMethod(methodName, ...args) {
		try {
			return await asyncCall(methodName, stringify(args));
		} catch (error) {
			error = parse(error.message);
			if (error) {
				const newError = new Error(error[1]);
				newError.name = error[0];
				throw newError;
			} else {
				throw new Error("Webview bridge cannot handle the value that remote function returned.");
			}
		}
	}
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
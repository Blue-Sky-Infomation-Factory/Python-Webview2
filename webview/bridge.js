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
	function syncMethod(methodName, ...args) { return parse(syncCall(methodName, stringify(args))) }
	async function asyncMethod(methodName, ...args) {
		const result = await asyncCall(methodName, stringify(args));
		if (!result) throw new TypeError("Failed to serialize result");
		if (result.startsWith("#")) {
			const data = parse(result.substring(1)),
				error = new Error(data[1]);
			error.name = data[0];
			throw error;
		}
		return parse(result)
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
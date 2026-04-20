"use strict";
{
	const COM_GUID = "1B9FCAB5-FB86-4D78-91DE-7BC2B4077E5B",
		GET_OBJECT_PARAM = '{"kind":"request","options":{"operation":"get"}}',
		{ stringify, parse } = JSON;
	const webview = new EmbeddedBrowserWebView,
		postMessage = webview.postMessage.bind(webview),
		postRemoteObjectCall = webview.postRemoteObjectCall.bind(webview),
		{ Error, MessageEvent } = window,
		warn = console.warn.bind(console);
	delete window.EmbeddedBrowserWebView;
	class WebViewInvokeError extends Error {
		name = this.constructor.name;
	}
	class WebViewBridgeError extends Error {
		name = this.constructor.name;
	}
	class WebViewRemoteError extends Error {
		constructor([name, message]) {
			super(message)
			this.name = name;
		}
	}
	function getRemoteObjectProperty(remoteObjectId, key) {
		const result = postRemoteObjectCall(remoteObjectId, key, GET_OBJECT_PARAM, null, true).parameters;
		if ("error" in result) throw new WebViewInvokeError(result.error);
		return result.has_object ?
			result.result[COM_GUID] :
			result.result;
	}
	const syncApi = Object.create(null),
		asyncApi = Object.create(null),
		bridge = getRemoteObjectProperty(0, "bridge").remoteObjectId,
		syncCall = getRemoteObjectProperty(bridge, "SyncCall").remoteObjectId,
		asyncCall = getRemoteObjectProperty(bridge, "AsyncCall").remoteObjectId;
	function syncMethod(methodName, ...args) {
		const result = postRemoteObjectCall(syncCall, "", stringify({
			kind: "request",
			options: { operation: "apply" },
			parameters: [methodName, stringify(args)]
		}), null, true).parameters;
		if ("error" in result) {
			const data = parse(result.error);
			throw data ?
				new WebViewRemoteError(data) :
				new WebViewBridgeError("Webview bridge cannot handle the value that remote function returned.");
		}
		return parse(result.result);
	}
	const asyncRequests = new Map,
		maxAsyncId = Number.MAX_SAFE_INTEGER;
	webview.addEventListener("remoteproxycall", function (event) {
		const { callId: id, parameters: result } = parse(event.data),
			controls = asyncRequests.get(id);
		asyncRequests.delete(id);
		if ("error" in result) {
			const data = parse(result.error);
			controls.reject(data ?
				new WebViewRemoteError(data) :
				new WebViewBridgeError("Webview bridge cannot handle the value that remote function returned."));
		} else {
			controls.resolve(parse(result.result));
		}
	});
	let currentAsyncId = 1;
	function generateAsyncRequestId() {
		if (currentAsyncId == maxAsyncId) currentAsyncId = 1;
		const id = currentAsyncId++;
		if (asyncRequests.has(id)) {
			asyncRequests.delete(id);
			warn(`[Webview] Async request id '${id}' did not get response in loop cycle.`);
		}
		const controls = Promise.withResolvers();
		asyncRequests.set(id, controls);
		return [id, controls.promise];
	}
	function asyncMethod(methodName, ...args) {
		args = stringify(args);
		const [id, promise] = generateAsyncRequestId();
		var result = postRemoteObjectCall(asyncCall, "", stringify({
			kind: "request",
			options: { operation: "apply" },
			parameters: [methodName, args]
		}), id, false);
		return promise;
	}
	for (const name of getRemoteObjectProperty(bridge, "MethodNames")) {
		syncApi[name] = syncMethod.bind(null, name);
		asyncApi[name] = asyncMethod.bind(null, name);
	}
	class WebView extends EventTarget {
		static #flag = false;
		constructor() {
			if (WebView.#flag) throw new TypeError("Illegal invocation");
			WebView.#flag = true;
			super();
			Object.freeze(this);
			const dispatchMessage = this.dispatchEvent.bind(this);
			webview.addEventListener("message", function (event) {
				dispatchMessage(new MessageEvent("message", { data: parse(event.data) }));
			});
		}
		syncApi = syncApi;
		asyncApi = asyncApi;
		static {
			const { prototype } = this;
			prototype.postMessage = postMessage;
			Object.defineProperty(prototype, Symbol.toStringTag, {
				value: this.name,
				configurable: true
			});
		}
	}
	window.webview = new WebView;
	Object.getPrototypeOf(Uint8Array).prototype.toJSON = function toJSON() { return Array.from(this) };
}
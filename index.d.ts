declare class EmbeddedBrowserWebView extends EventTarget {
	getTextureStream(): any;
	postMessage(): any;
	postMessageWithAdditionalObjects(): any;
	postRemoteObjectCall(remoteObjectId: number, targetKey: string, parameters: string, callId: number, sync: boolean): {
		methodName: string,
		remoteObjectId: number,
		parameters: {
			kind: string,
			error?: string,
			has_object?: boolean,
			result?: {
				[key: string]: {
					groupId: string,
					remoteObjectId: number,
					seq_no: number,
					type: string,
					cache_able?: boolean
				}
			} | any
		}
	};
	registerTextureStream(): any;
	releaseBuffer(): any;
	releaseObjectsCallback(): any;
	unregisterTextureStream(): any;
}
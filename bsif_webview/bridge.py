from asyncio import iscoroutine, new_event_loop
from threading import Thread
from traceback import print_exception
from .helper import LIBRARIES, PACKAGE
from clr import AddReference
from inspect import isbuiltin, isfunction, ismethod
from json import dumps, loads
from os.path import join
from typing import Any, Callable, Dict

AddReference(join(LIBRARIES, 'BSIF.WebView2Bridge.dll'))
with open(join(PACKAGE, "bridge.js")) as file: bridge_script = file.read()
from BSIF.WebView2Bridge import WebView2Bridge # type: ignore
from System import Exception as CSException # type: ignore

def serialize_object(object: object): return object.__dict__

def pick_methods(object: object) -> Dict[str, Callable]:
	methods = {}
	for name in dir(object):
		if name.startswith("_"): continue
		item = getattr(object, name)
		if ismethod(item) or isfunction(item) or isbuiltin(item): methods[name] = item
	return methods

def pick_dictionary_methods(object: Dict[str, Any]) -> Dict[str, Callable]:
	methods = {}
	for key, value in object.items():
		if ismethod(value) or isfunction(value) or isbuiltin(value): methods[key] = value
	return methods

def async_call_thread(function: Callable, args_json: str, async_object ):
	try:
		result=function(*loads(args_json))
		if (iscoroutine(result)): result=new_event_loop().run_until_complete(result)
	except Exception as error:
		async_object.SetException(CSException(dumps([error.__class__.__name__, str(error)], ensure_ascii=False)))
		print_exception(error)
		return
	try: async_object.SetResult(dumps(result, ensure_ascii=False, default=serialize_object))
	except BaseException as error:
		async_object.SetException(CSException("null"))
		print_exception(error)

class Bridge:
	def __init__(self, core, api: object):
		api = self.__api = (pick_dictionary_methods if type(api) is dict else pick_methods)(api) # type: ignore
		core.AddScriptToExecuteOnDocumentCreatedAsync(bridge_script)
		core.AddHostObjectToScript("bridge", WebView2Bridge(
			WebView2Bridge.SyncCaller(self.__sync_call_handler),
			WebView2Bridge.AsyncCaller(self.__async_call_handler),
			api.keys()
		))
	
	def __sync_call_handler(self, method_name: str, args_json: str):
		try:
			result = self.__api[method_name](*loads(args_json))
		except Exception as error:
			print_exception(error)
			raise Exception(dumps([error.__class__.__name__, str(error)], ensure_ascii=False))
		try:
			return dumps(result, ensure_ascii=False, default=serialize_object)
		except BaseException as error:
			print_exception(error)
			raise Exception("null")
	def __async_call_handler(self, method_name: str, args_json: str, async_object):
		Thread(None, async_call_thread, method_name, (self.__api[method_name], args_json, async_object), daemon=True).start()

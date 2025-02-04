from traceback import print_exception
from typing import Callable, List

class Notifier:
	def __init__(self):
		self.__handlers: List[Callable] = []

	def add_handler(self, handler: Callable):
		if not callable(handler): raise TypeError("Not callable")
		self.__handlers.append(handler)

	def remove_handler(self, handler: Callable):
		self.__handlers.remove(handler)

	def remove_all_handlers(self):
		self.__handlers = []

	def trigger(self, *args):
		for item in self.__handlers:
			try: item(*args)
			except Exception as e: print_exception(e)
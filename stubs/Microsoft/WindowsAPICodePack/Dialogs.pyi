from abc import ABC
from enum import Enum
from typing import Optional, overload

from System import Object
from System.Collections.Generic import ICollection # type: ignore
from System.Windows import Window # type: ignore

class CommonFileDialogResult(Enum):
	"""
	⚠ Special static key:<br>
	None -> getattr(CommonFileDialogResult, "None")
	"""
	# None = 0
	Ok = 1
	Cancel = 2

class CommonFileDialog(Object, ABC):
	# incomplete
	@property
	def Title(self) -> str: ...
	@Title.setter
	def Title(self, value: str) -> None: ...
	@property
	def InitialDirectory(self) -> Optional[str]: ...
	@InitialDirectory.setter
	def InitialDirectory(self, value: Optional[str]) -> None: ...
	@property
	def DefaultFileName(self) -> Optional[str]: ...
	@DefaultFileName.setter
	def DefaultFileName(self, value: Optional[str]) -> None: ...
	@property
	def FileName(self) -> str: ...
	@property
	def EnsureFileExists(self) -> bool: ...
	@EnsureFileExists.setter
	def EnsureFileExists(self, value: bool) -> None: ...
	@property
	def Filters(self) -> CommonFileDialogFilterCollection: ...
	@property
	def SelectedFileTypeIndex(self) -> int: ...
	@overload
	def ShowDialog(self) -> CommonFileDialogResult: ...
	@overload
	def ShowDialog(self, owner: Window) -> CommonFileDialogResult: ...

class CommonOpenFileDialog(CommonFileDialog):
	# incomplete
	@property
	def IsFolderPicker(self) -> bool: ...
	@IsFolderPicker.setter
	def IsFolderPicker(self, value: bool) -> None: ...
	@property
	def Multiselect(self) -> bool: ...
	@Multiselect.setter
	def Multiselect(self, value: bool) -> None: ...
	@property
	def FileNames(self) -> str: ...
	@FileNames.setter
	def FileNames(self, value: str) -> None: ...


class CommonSaveFileDialog(CommonFileDialog):
	# incomplete
	@property
	def CreatePrompt(self) -> bool: ...
	@CreatePrompt.setter
	def CreatePrompt(self, value: bool) -> None: ...
	@property
	def OverwritePrompt(self) -> bool: ...
	@OverwritePrompt.setter
	def OverwritePrompt(self, value: bool) -> None: ...
	@property
	def AlwaysAppendDefaultExtension(self) -> bool: ...
	@AlwaysAppendDefaultExtension.setter
	def AlwaysAppendDefaultExtension(self, value: bool) -> None: ...

class CommonFileDialogFilter(Object):
	def __init__(self, rawDisplayName: str, extensionList: str):
		self.DisplayName: str
		self.Extensions: str

class CommonFileDialogFilterCollection(Object, ICollection[CommonFileDialogFilter]):
	# incomplete
	pass
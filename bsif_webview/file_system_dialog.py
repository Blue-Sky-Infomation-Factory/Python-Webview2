from typing import Iterable, List, Optional, Tuple, TypedDict
from re import compile
from os.path import dirname, join
from clr import AddReference

AddReference("wpf\\PresentationFramework")
self_path = dirname(__file__)

AddReference(join(self_path, "Microsoft.WindowsAPICodePack.Shell.dll"))

from Microsoft.WindowsAPICodePack.Dialogs import CommonFileDialog, CommonFileDialogFilter, CommonFileDialogFilterCollection, CommonOpenFileDialog, CommonSaveFileDialog, CommonFileDialogResult # type: ignore
from System.Windows import Window # type: ignore

class DialogBase[T: CommonFileDialog]:
	def __init__(self, dialog_class: type[T]):
		self._dialog = dialog_class()
		self._selected = False
	def show_dialog(self, owner: Window):
		self._selected = self._dialog.ShowDialog(owner) == CommonFileDialogResult.Ok

class FilterItem(TypedDict, total = False):
	description: str
	extensions: Iterable[str]

EXTENSION_REGEX = compile("[;'\"\\\\/:<>?]")
description_of_all_files = "All Files"

def parse_filters(collection: CommonFileDialogFilterCollection, filters: Optional[Iterable[FilterItem]], exclude_filter_of_all_files: bool):
	if filters:
		for item in filters:
			description = item.get("description", None)
			if not description: description = ""
			extensions = item.get("extensions", None)
			if not extensions:
				raise ValueError("Extensions cannot be empty.")
			extensions = tuple(extensions)
			for name in extensions:
				if EXTENSION_REGEX.search(name):
					raise ValueError("Extension cannot contain contain special characters.")
			collection.Add(CommonFileDialogFilter(description, ";".join(extensions)))
	if not exclude_filter_of_all_files:
		collection.Add(CommonFileDialogFilter(description_of_all_files, "*.*"))

class OpenFilePickerOptions(TypedDict, total = False):
	title: Optional[str]
	multiple: bool
	initial_directory: Optional[str]
	filters: Optional[Iterable[FilterItem]]
	exclude_filter_of_all_files: bool
	default_file_name: Optional[str]

class OpenFileResult:
	def __init__(self, multiple: bool, file_names: List[str]):
		self.multiple = multiple
		self.files = file_names
		self.file = None if multiple else file_names[0]

class OpenFilePicker(DialogBase[CommonOpenFileDialog]):
	def __init__(self):
		super().__init__(CommonOpenFileDialog)
	def set_options(self, options: OpenFilePickerOptions):
		dialog = self._dialog
		dialog.EnsureFileExists = True
		dialog.Multiselect = options.get("multiple", False)
		title = options.get("title", None)
		if title: dialog.Title = title
		directory = options.get("initial_directory", None)
		if directory: dialog.InitialDirectory = directory
		default_file_name = options.get("default_file_name", None)
		if default_file_name: dialog.DefaultFileName = default_file_name
		parse_filters(dialog.Filters, options.get("filters", None), options.get("exclude_filter_of_all_files", False))
	def parse_result(self):
		if self._selected:
			dialog = self._dialog
			return OpenFileResult(dialog.Multiselect, list(dialog.FileNames))
		return None

class SaveFilePickerOptions(TypedDict, total = False):
	title: Optional[str]
	initial_directory: Optional[str]
	filters: Optional[Iterable[FilterItem]]
	auto_add_extension: bool
	exclude_filter_of_all_files: bool
	default_file_name: Optional[str]

class SaveFileResult:
	def __init__(self, file: str, filter: Optional[FilterItem]):
		self.file = file
		self.filter = filter

class SaveFilePicker(DialogBase[CommonSaveFileDialog]):
	def __init__(self):
		super().__init__(CommonSaveFileDialog)
		self.__filters: Optional[Tuple[FilterItem, ...]] = None
	def set_options(self, options: SaveFilePickerOptions):
		dialog = self._dialog
		title = options.get("title", None)
		if title: dialog.Title = title
		directory = options.get("initial_directory", None)
		if directory: dialog.InitialDirectory = directory
		default_file_name = options.get("default_file_name", None)
		if default_file_name: dialog.DefaultFileName = default_file_name
		filters = options.get("filters", None)
		filters = tuple(filters) if filters else tuple()
		parse_filters(dialog.Filters, filters, options.get("exclude_filter_of_all_files", False))
		self.__filters = filters
		dialog.AlwaysAppendDefaultExtension = options.get("auto_add_extension", True)
	def parse_result(self):
		if self._selected:
			dialog = self._dialog
			filter_index = dialog.SelectedFileTypeIndex - 1
			filters = self.__filters
			assert filters is not None
			filter = filters[filter_index] if filter_index >= 0 and filter_index < len(filters) else None
			return SaveFileResult(dialog.FileName, filter)
		return None

class DirectoryPickerOptions(TypedDict, total = False):
	title: Optional[str]
	multiple: bool
	initial_directory: Optional[str]
	default_directory_name: Optional[str]

class DirectoryResult:
	def __init__(self, multiple: bool, directories: List[str]):
		self.multiple = multiple
		self.directories = directories
		self.directory = None if multiple else directories[0]

class DirectoryPicker(DialogBase[CommonOpenFileDialog]):
	def __init__(self):
		super().__init__(CommonOpenFileDialog)
	def set_options(self, options: DirectoryPickerOptions):
		dialog = self._dialog
		dialog.IsFolderPicker = True
		dialog.Multiselect = options.get("multiple", False)
		title = options.get("title", None)
		if title: dialog.Title = title
		directory = options.get("initial_directory", None)
		if directory: dialog.InitialDirectory = directory
		default_directory_name = options.get("default_directory_name", None)
		if default_directory_name: dialog.DefaultFileName = default_directory_name
	def parse_result(self):
		if self._selected:
			dialog = self._dialog
			return DirectoryResult(dialog.Multiselect, list(dialog.FileNames))
		return None
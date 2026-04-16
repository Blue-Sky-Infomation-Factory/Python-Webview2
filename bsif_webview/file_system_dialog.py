from typing import Iterable, List, Optional, Tuple, TypedDict
from re import compile

from Microsoft.Win32 import CommonDialog, OpenFileDialog, OpenFolderDialog, SaveFileDialog # type: ignore
from System.Windows import Window # type: ignore

class DialogBase[T: CommonDialog]:
	def __init__(self, dialog_class: type[T]):
		self._dialog = dialog_class()
		self._selected = False
	def show_dialog(self, owner: Window):
		self._selected = self._dialog.ShowDialog(owner)

class FilterItem(TypedDict, total = False):
	description: str
	extensions: Iterable[str]

DESCRIPTION_REGEX = compile("\\|")
EXTENSION_REGEX = compile("[\\|;'\"\\\\/:<>?]")
_description_of_all_files = "All Files"
def set_description_of_all_files(text: str):
	global _description_of_all_files
	if type(text) is not str:
		raise TypeError("Argument 'text' must be a string.")
	if DESCRIPTION_REGEX.search(text):
		raise ValueError("Description cannot contain contain '|' character.")
	_description_of_all_files = text

def parse_filters(filters: Optional[Iterable[FilterItem]], exclude_filter_of_all_files: bool):
	temp = []
	if filters:
		for item in filters:
			description = item.get("description", None)
			if description:
				if DESCRIPTION_REGEX.search(description):
					raise ValueError("Description cannot contain contain '|' character.")
			else: description = ""
			extensions = item.get("extensions", None)
			if not extensions:
				raise ValueError("Extensions cannot be empty.")
			extensions = tuple(extensions)
			for name in extensions:
				if EXTENSION_REGEX.search(name):
					raise ValueError("Extension cannot contain contain special characters.")
			temp.append(f"{description}|{';'.join(extensions)}")
	if not exclude_filter_of_all_files:
		temp.append(f"{_description_of_all_files}|*.*")
	return "|".join(temp)

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

class OpenFilePicker(DialogBase[OpenFileDialog]):
	def __init__(self):
		super().__init__(OpenFileDialog)
	def set_options(self, options: OpenFilePickerOptions):
		dialog = self._dialog
		dialog.CheckFileExists = True
		dialog.Multiselect = options.get("multiple", False)
		title = options.get("title", None)
		if title: dialog.Title = title
		directory = options.get("initial_directory", None)
		if directory: dialog.InitialDirectory = directory
		default_file_name = options.get("default_file_name", None)
		if default_file_name: dialog.FileName = default_file_name
		dialog.Filter = parse_filters(options.get("filters", None), options.get("exclude_filter_of_all_files", False))
	def parse_result(self):
		if self._selected:
			dialog = self._dialog
			return OpenFileResult(dialog.Multiselect, list(dialog.FileNames))
		return None

class SaveFilePickerOptions(TypedDict, total = False):
	title: Optional[str]
	initial_directory: Optional[str]
	filters: Optional[Iterable[FilterItem]]
	exclude_filter_of_all_files: bool
	default_file_name: Optional[str]

class SaveFileResult:
	def __init__(self, file: str, filter: Optional[FilterItem]):
		self.file = file
		self.filter = filter

class SaveFilePicker(DialogBase[SaveFileDialog]):
	def __init__(self):
		super().__init__(SaveFileDialog)
		self.__filters: Optional[Tuple[FilterItem, ...]] = None
	def set_options(self, options: SaveFilePickerOptions):
		dialog = self._dialog
		title = options.get("title", None)
		if title: dialog.Title = title
		directory = options.get("initial_directory", None)
		if directory: dialog.InitialDirectory = directory
		filters = options.get("filters", None)
		filters = tuple(filters) if filters else tuple()
		dialog.Filter = parse_filters(filters, options.get("exclude_filter_of_all_files", False))
		self.__filters = filters
		default_file_name = options.get("default_file_name", None)
		if default_file_name: dialog.FileName = default_file_name
	def parse_result(self):
		if self._selected:
			dialog = self._dialog
			filter_index = dialog.FilterIndex - 1
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

class DirectoryPicker(DialogBase[OpenFolderDialog]):
	def __init__(self):
		super().__init__(OpenFolderDialog)
	def set_options(self, options: DirectoryPickerOptions):
		dialog = self._dialog
		dialog.Multiselect = options.get("multiple", False)
		title = options.get("title", None)
		if title: dialog.Title = title
		directory = options.get("initial_directory", None)
		if directory: dialog.InitialDirectory = directory
		default_directory_name = options.get("default_directory_name", None)
		if default_directory_name: dialog.FolderName = default_directory_name
	def parse_result(self):
		if self._selected:
			dialog = self._dialog
			return DirectoryResult(dialog.Multiselect, list(dialog.FolderNames))
		return None
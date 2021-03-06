from mapreduce.commands import base_command


class ClearDataCommand(base_command.BaseCommand):

    def __init__(self):
        self._data = {}
        super().__init__(self._data)

    def set_folder_name(self, folder_name):
        self._data['folder_name'] = folder_name

    def set_remove_all_data(self, remove_all_data):  # = 0 or = 1
        self._data['remove_all_data'] = bool(int(remove_all_data))

    def validate(self):
        if not self._data['folder_name']:
            raise AttributeError('Folder name is not specified!')

    def send(self, **kwargs):
        self.validate()
        return super().send('clear_data')

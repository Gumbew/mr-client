import base64

from mapreduce.commands import base_command


class ReduceCommand(base_command.BaseCommand):

    def __init__(self):
        self._data = {}
        super().__init__(self._data)

    def set_reducer_from_file(self, path):
        with open(path, 'rb') as file:
            file_content = file.read()
            encoded = base64.b64encode(file_content)
            decoded = encoded.decode('utf-8')
            self._data['reducer'] = decoded

    def set_reducer(self, content):
        encoded = base64.b64encode(bytes(content, 'utf-8'))
        decoded = encoded.decode('utf-8')
        self._data['reducer'] = decoded

    def set_field_delimiter(self, field_delimiter):
        encoded = field_delimiter
        self._data['field_delimiter'] = encoded

    def set_server_source_file(self, src_file):
        encoded = src_file
        self._data['server_source_file'] = encoded

    def set_source_file(self, src_file):
        encoded = src_file
        self._data['source_file'] = encoded

    def set_destination_file(self, dest_file):
        encoded = dest_file
        self._data['destination_file'] = encoded

    def validate(self):
        if not self._data['reducer']:
            raise AttributeError('Reducer is empty!')
        if not self._data['destination_file']:
            raise AttributeError('Destination file in not mentioned!')

    def send(self, **kwargs):
        self.validate()
        return super(ReduceCommand, self).send('reduce')

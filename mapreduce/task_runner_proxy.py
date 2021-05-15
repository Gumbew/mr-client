import asyncio
import os
import uuid
from itertools import groupby, count, cycle

from aiohttp import ClientSession
from fastapi import UploadFile

import parsers.sql_parser as sql_parser
from config.config_provider import ConfigProvider
from config.logger import client_logger
from mapreduce import commands

logger = client_logger.get_logger(__name__)

config_provider = ConfigProvider(os.path.join('..', 'config', 'client_config.json'))


def get_file_from_cluster(file_name, dest_file_name):
    return commands.GetFileFromClusterCommand(file_name, dest_file_name).send_command()


async def create_config_and_filesystem(session, file_name):
    return await commands.CreateConfigAndFilesystem(session, file_name).send_command_async()


async def get_data_nodes_list(session):
    return await commands.GetDataNodesListCommand(session).send_command_async()


async def write(session, file_id, file_name, segment, data_node_ip):
    return await commands.WriteCommand(session, file_id, file_name, segment, data_node_ip).send_command_async()


async def refresh_table(session, file_id, ip, segment_name):
    return await commands.RefreshTableCommand(session, file_id, ip, segment_name).send_command_async()


def start_map_phase(is_mapper_in_file, mapper, file_id):
    mc = commands.MapCommand(is_mapper_in_file, mapper, file_id)
    return mc.send_command()


def start_shuffle_phase(file_id):
    return commands.ShuffleCommand(file_id).send_command()


def start_reduce_phase(is_reducer_in_file, reducer, file_id, source_file):
    rc = commands.ReduceCommand(is_reducer_in_file, reducer, file_id, source_file)
    return rc.send_command()


def send_info():
    pass


def get_file(file_name, ip=None):
    return commands.GetFileCommand(file_name).send_command(ip=ip)


def clear_data(file_id: str, clear_all: bool):
    return commands.ClearDataCommand(file_id, clear_all).send_command()


async def push_file_on_cluster(uploaded_file: UploadFile):
    async with ClientSession() as session:
        response = await create_config_and_filesystem(session, uploaded_file.filename)
        data_nodes_list = await get_data_nodes_list(session)
        data_nodes_list = cycle(data_nodes_list)
        row_limit = response.get("distribution")
        file_id = response.get("file_id")

        file_name, file_ext = os.path.splitext(uploaded_file.filename)
        file_obj = uploaded_file.file._file  # noqa
        headers = next(file_obj, None)

        if headers:
            headers = headers.decode("utf-8")

        groups = groupby(file_obj, key=lambda _, line=count(): next(line, None) // row_limit)

        async def push_chunk_on_cluster(chunk, ip):
            ip = f"http://{ip}"  # noqa

            chunk_name = f"{uuid.uuid4()}{file_ext}"
            await write(session,
                        file_id,
                        chunk_name,
                        {"headers": headers, "items": [i.decode("utf-8") for i in chunk]},
                        ip)
            await refresh_table(session, file_id, ip, chunk_name)

        tasks = []
        for group in groups:
            tasks.append(asyncio.ensure_future(push_chunk_on_cluster(group[1], next(data_nodes_list, None))))

        await asyncio.gather(*tasks)

    return file_id


def move_file_to_init_folder(file_name):
    return commands.MoveFileToInitFolderCommand(file_name).send_command()


def check_if_file_is_on_cluster(file_name):
    return commands.CheckIfFileIsOnCLuster(file_name).send_command()


def run_tasks(sql, files_info):
    parsed_sql = sql if type(sql) is dict else sql_parser.SQLParser.sql_parser(sql)
    field_delimiter = config_provider.field_delimiter
    from_file = parsed_sql['from']

    if type(from_file) is dict:
        from_file = run_tasks(from_file, files_info)
    if type(from_file) is tuple:
        reducer = sql_parser.custom_reducer(parsed_sql, field_delimiter)

        for file_name in from_file:
            own_select = sql_parser.SQLParser.split_select_cols(file_name, parsed_sql['select'])
            key_col = sql_parser.SQLParser.get_key_col(parsed_sql, file_name)

            mapper = sql_parser.custom_mapper(key_col, own_select, field_delimiter)
            file_id = files_info[file_name]
            start_map_phase(
                is_mapper_in_file=False,
                mapper=mapper,
                file_id=file_id,
            )
            start_shuffle_phase(file_id=file_id)

        file_name = from_file[0]

        start_reduce_phase(
            is_reducer_in_file=False,
            reducer=reducer,
            file_id=files_info[file_name],
            source_file=list(from_file)
        )
        return file_name

    else:

        key_col = sql_parser.SQLParser.get_key_col(parsed_sql, from_file)
        reducer = sql_parser.custom_reducer(parsed_sql, field_delimiter)
        mapper = sql_parser.custom_mapper(key_col, parsed_sql['select'], field_delimiter)

        if type(from_file) is tuple:
            from_file = from_file[0]

        file_id = files_info[from_file]
        start_map_phase(
            is_mapper_in_file=False,
            mapper=mapper,
            file_id=file_id,
        )
        start_shuffle_phase(file_id=file_id)

        start_reduce_phase(
            is_reducer_in_file=False,
            reducer=reducer,
            file_id=file_id,
            source_file=from_file
        )
        return from_file

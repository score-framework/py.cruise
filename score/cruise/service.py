# Copyright © 2017 STRG.AT GmbH, Vienna, Austria
#
# This file is part of the The SCORE Framework.
#
# The SCORE Framework and all its parts are free software: you can redistribute
# them and/or modify them under the terms of the GNU Lesser General Public
# License version 3 as published by the Free Software Foundation which is in the
# file named COPYING.LESSER.txt.
#
# The SCORE Framework and all its parts are distributed without any WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. For more details see the GNU Lesser General Public
# License.
#
# If you have not received a copy of the GNU Lesser General Public License see
# http://www.gnu.org/licenses/.
#
# The License-Agreement realised between you as Licensee and STRG.AT GmbH as
# Licenser including the issue of its valid conclusion and its pre- and
# post-contractual effects is governed by the laws of Austria. Any disputes
# concerning this License-Agreement including the issue of its valid conclusion
# and its pre- and post-contractual effects are exclusively decided by the
# competent court, in whose district STRG.AT GmbH has its registered seat, at
# the discretion of STRG.AT GmbH also the competent court, in whose district the
# Licensee has his registered seat, an establishment or assets.

import abc
import asyncio
import json


class ServeConnector(metaclass=abc.ABCMeta):

    def __init__(self, name, loop):
        self.name = name
        self.loop = loop
        self.status_change_callbacks = []

    @abc.abstractmethod
    @asyncio.coroutine
    def start(self):
        pass

    @abc.abstractmethod
    @asyncio.coroutine
    def pause(self):
        pass

    @abc.abstractmethod
    @asyncio.coroutine
    def stop(self):
        pass

    @abc.abstractmethod
    @asyncio.coroutine
    def restart(self):
        pass

    @abc.abstractmethod
    @asyncio.coroutine
    def get_status(self):
        pass

    def add_status_change_callback(self, callback):
        self.status_change_callbacks.append(callback)

    def remove_status_change_callback(self, callback):
        self.status_change_callbacks.remove(callback)


class SocketConnector(ServeConnector):

    def __init__(self, name, loop, host, port):
        super().__init__(name, loop)
        self.host = host
        self.port = port
        self.status = None
        self._connection = None
        self._connecting = False

    @asyncio.coroutine
    def start(self):
        yield from self._send_command('start')

    @asyncio.coroutine
    def pause(self):
        yield from self._send_command('pause')

    @asyncio.coroutine
    def stop(self):
        yield from self._send_command('stop')

    @asyncio.coroutine
    def restart(self):
        yield from self._send_command('restart')

    @asyncio.coroutine
    def _send_command(self, command):
        connection = yield from self._get_connection()
        connection.write(command.encode('ASCII') + b'\n')

    @asyncio.coroutine
    def get_status(self):
        if self.status is not None:
            return self.status
        result = None
        condition = asyncio.Condition()

        @asyncio.coroutine
        def callback(status):
            nonlocal result
            result = status
            with (yield from condition):
                condition.notify()
        self.add_status_change_callback(callback)
        try:
            yield from self._get_connection()
            with (yield from condition):
                yield from condition.wait_for(lambda: result is not None)
            return result
        except ConnectionRefusedError:
            return 'offline'
        finally:
            self.remove_status_change_callback(callback)

    @asyncio.coroutine
    def _get_connection(self):
        if self._connection is None:
            self._connection = self.loop.create_task(self._connect())
            try:
                self._connection = (yield from self._connection)[0]
            except ConnectionRefusedError:
                self._status_change('offline')
                raise
            connection = self._connection
        elif asyncio.iscoroutine(self._connection):
            try:
                connection = (yield from self._connection)[0]
            except ConnectionRefusedError:
                self._status_change('offline')
                raise
        else:
            connection = self._connection
        return connection

    @asyncio.coroutine
    def _connect(self):
        def protocol_factory():
            return ServeProtocol(self)
        self._connection = self.loop.create_connection(
            protocol_factory, self.host, self.port)
        self._connection = yield from self._connection
        return self._connection

    def _message_received(self, message):
        self._status_change(json.loads(message))

    def _status_change(self, status):
        if self.status == status:
            return
        self.status = status
        for callback in self.status_change_callbacks:
            result = callback(status)
            if asyncio.iscoroutine(result):
                self.loop.create_task(result)


class ServeProtocol(asyncio.Protocol):

    def __init__(self, connector):
        self.connector = connector
        self.loop = connector.loop
        self.buffer = b''

    def data_received(self, data):
        self.buffer += data
        index = self.buffer.find(b'\n')
        while index >= 0:
            message = self.buffer[:index]
            self.buffer = self.buffer[index + 1:]
            self.connector._message_received(str(message, 'UTF-8'))
            index = self.buffer.find(b'\n')
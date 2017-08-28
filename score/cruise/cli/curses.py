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


import curses
import asyncio


class ServersMenu:

    def __init__(self, main):
        self.main = main
        self.index = 0
        self.window = None
        self.servers = self.main.cruise.servers
        self.max_name_length = max(len(srv.name) for srv in self.servers)

    @asyncio.coroutine
    def redraw(self):
        self.padding = 5
        new_width = self.max_name_length + self.padding * 2 + 1
        new_height, _ = self.main.window.getmaxyx()
        if self.window is None:
            self.window = self.main.window.derwin(new_height, new_width, 0, 0)
        elif self.width != new_width or self.height != new_height:
            self.window.erase()
            self.window.resize(new_height, new_width)
        self.width = new_width
        self.height = new_height
        self.window.vline(0, self.width - 1, '|', new_height)
        for i, server in enumerate(self.servers):
            self.draw_button(i)

    def draw_button(self, idx):
        tpl = '{:%d}' % self.max_name_length
        padding = ' ' * self.padding
        server = self.servers[idx]
        attr = 0
        if idx == self.index:
            attr = curses.A_REVERSE
        text = padding + tpl.format(server.name) + padding
        self.window.addstr(idx + 1, 0, text, attr)

    @asyncio.coroutine
    def handle_keypress(self, char):
        needs_refresh = False
        try:
            if char == curses.KEY_DOWN:
                needs_refresh = yield from self.select_next_server()
            elif char == curses.KEY_UP:
                needs_refresh = yield from self.select_previous_server()
            elif char == ord('r'):
                yield from self.servers[self.index].restart()
            elif char == ord('s'):
                yield from self.servers[self.index].start()
            elif char == ord('p'):
                yield from self.servers[self.index].pause()
            elif char == ord('k'):
                yield from self.servers[self.index].stop()
        except ConnectionError:
            # no need to handle connection errors here, the status of the server
            # connectino will be updated and propagated back to us through our
            # state_change_callback
            pass
        if needs_refresh:
            self.window.refresh()

    @asyncio.coroutine
    def select_next_server(self):
        if self.index >= len(self.servers) - 1:
            return False
        self.index += 1
        self.draw_button(self.index - 1)
        self.draw_button(self.index)
        yield from self.main.details.set_server(self.servers[self.index])
        return True

    @asyncio.coroutine
    def select_previous_server(self):
        if self.index == 0:
            return False
        self.index -= 1
        self.draw_button(self.index + 1)
        self.draw_button(self.index)
        yield from self.main.details.set_server(self.servers[self.index])
        return True

    @asyncio.coroutine
    def cleanup(self):
        pass


class ServerDetails:

    def __init__(self, main):
        self.main = main
        self.window = None
        self.server = None

    @asyncio.coroutine
    def redraw(self):
        self.padding = 5
        new_height, width = self.main.window.getmaxyx()
        new_width = width - self.main.menu.width
        if self.window is None:
            self.window = self.main.window.derwin(
                new_height, new_width, 0, self.main.menu.width)
        elif self.width != new_width:
            self.window.erase()
            self.window.resize(new_height, new_width)
        self.width = new_width
        self.height = new_height
        if self.server is None:
            return
        yield from self.draw_details()

    @asyncio.coroutine
    def draw_details(self, status=None):
        if status is None:
            server = self.server
            status = yield from server.get_status()
            if server != self.server:
                # server was deselected while get_status() was being executed.
                return
        self.window.clear()  # TODO: erase()?
        if isinstance(status, str):
            text = '<%s>' % status
            self.window.addstr(1, self.padding, text)
        else:
            for i, (service, state) in enumerate(status.items()):
                text = '%s: %s' % (service, state)
                self.window.addstr(1 + i, self.padding, text)
        self.window.refresh()

    @asyncio.coroutine
    def set_server(self, server):
        if self.server:
            self.server.remove_status_change_callback(self._status_change)
        self.server = server
        self.server.add_status_change_callback(self._status_change)
        yield from self.draw_details()

    @asyncio.coroutine
    def _status_change(self, status):
        yield from self.draw_details(status)

    @asyncio.coroutine
    def cleanup(self):
        self.server.remove_status_change_callback(self._status_change)


class MainWindow:

    def __init__(self, cruise, window):
        self.cruise = cruise
        self.window = window
        self.menu = ServersMenu(self)
        self.details = ServerDetails(self)

    def run(self):
        loop = self.cruise.loop
        loop.run_until_complete(self._run())
        pending_tasks = [t for t in asyncio.Task.all_tasks(loop)
                         if not t.done()]
        while pending_tasks:
            loop.run_until_complete(pending_tasks[0])
            pending_tasks = [t for t in asyncio.Task.all_tasks(loop)
                             if not t.done()]

    @asyncio.coroutine
    def _run(self):
        yield from self.redraw()
        yield from self.details.set_server(self.cruise.servers[0])
        char = yield from self._getch()
        while char not in (ord('q'), ord('Q')):
            if char in (curses.KEY_RESIZE, curses.KEY_CLEAR):
                yield from self.redraw()
            else:
                yield from self.menu.handle_keypress(char)
            char = yield from self._getch()
        yield from self.menu.cleanup()
        yield from self.details.cleanup()

    @asyncio.coroutine
    def redraw(self):
        yield from self.menu.redraw()
        yield from self.details.redraw()
        self.window.refresh()

    @asyncio.coroutine
    def _getch(self):
        result = yield from self.cruise.loop.run_in_executor(
            None, self.window.getch)
        return result


def launch(cruise):
    def main(window):
        MainWindow(cruise, window).run()
    curses.wrapper(main)

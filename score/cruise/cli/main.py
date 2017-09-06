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


import click
import asyncio
from score.init import parse_config_file, init as score_init


@click.group('cruise', invoke_without_command=True)
@click.pass_context
def main(clickctx):
    if clickctx.invoked_subcommand:
        return
    from .curses import launch
    launch(_init(clickctx))


@main.command('list')
@click.pass_context
def list(clickctx):
    """
    Lists running processes of all servers
    """
    cruise = _init(clickctx)
    coroutines = []
    for server in cruise.servers:
        coroutines.append(server.get_status())
    for server, coroutine in zip(cruise.servers, coroutines):
        status = cruise.loop.run_until_complete(coroutine)
        status_lines = []
        if isinstance(status, str):
            status_lines.append('<%s>' % (status,))
        else:
            for service, state in status.items():
                status_lines.append('%s: %s' % (service, state))
        line_length = max(len(line) for line in status_lines)
        tpl = '{:^%d}' % (line_length + 2)
        print(tpl.format(server.name))
        print('-' * (line_length + 2))
        for line in status_lines:
            print(' ' + line)
        print('')
    _cleanup_loop(cruise.loop)


@main.command('restart')
@click.argument('server')
@click.pass_context
def restart(clickctx, server):
    """
    Restarts a server
    """
    cruise = _init(clickctx)
    server = _get_server(cruise, server)
    try:
        cruise.loop.run_until_complete(server.restart())
    except ConnectionRefusedError:
        raise click.ClickException('Server not running')
    _cleanup_loop(cruise.loop)


@main.command('stop')
@click.argument('server')
@click.pass_context
def stop(clickctx, server):
    """
    Restarts a server
    """
    cruise = _init(clickctx)
    server = _get_server(cruise, server)
    try:
        cruise.loop.run_until_complete(server.stop())
    except ConnectionRefusedError:
        raise click.ClickException('Server not running')
    _cleanup_loop(cruise.loop)


@main.command('status')
@click.argument('server')
@click.pass_context
def status(clickctx, server):
    """
    Restarts a server
    """
    cruise = _init(clickctx)
    server = _get_server(cruise, server)
    status = cruise.loop.run_until_complete(server.get_status())
    if isinstance(status, str):
        print(status)
    else:
        for service, state in status.items():
            print('%s: %s' % (service, state))
    _cleanup_loop(cruise.loop)


def _get_server(cruise, name):
    try:
        return next(server for server in cruise.servers if server.name == name)
    except StopIteration:
        raise click.ClickException(
            'No server called `%s` found in score.cruise configuration' %
            (name,))


def _init(clickctx):
    conf = parse_config_file(clickctx.obj['conf'].path)
    overrides = {
        'score.init': {
            'modules': 'score.cruise',
        }
    }
    try:
        del conf['score.init']['autoimport']
    except KeyError:
        pass
    if 'cruise' not in conf and 'serve' in conf and 'monitor' in conf['serve']:
        conf['cruise'] = {
            'server.local.monitor': conf['serve']['monitor'],
        }
    return score_init(conf, overrides=overrides).cruise


def _cleanup_loop(loop):
    pending_tasks = [t for t in asyncio.Task.all_tasks(loop)
                     if not t.done()]
    while pending_tasks:
        loop.run_until_complete(pending_tasks[0])
        pending_tasks = [t for t in asyncio.Task.all_tasks(loop)
                         if not t.done()]


if __name__ == '__main__':
    main()

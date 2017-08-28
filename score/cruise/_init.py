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

from score.init import ConfiguredModule, extract_conf, parse_host_port
from .service import SocketConnector
import asyncio
from collections import OrderedDict


defaults = OrderedDict()


def init(confdict):
    """
    Initializes this module acoording to the :ref:`SCORE module initialization
    guidelines <module_initialization>` with the following configuration keys:
    """
    conf = defaults.copy()
    conf.update(confdict)
    servers = []
    loop = asyncio.new_event_loop()
    server_names = [c.split('.')[0] for c in extract_conf(conf, 'server.')]
    for name in server_names:
        server_conf = extract_conf(conf, 'server.%s.' % name)
        name = server_conf.get('name', name)
        host, port = parse_host_port(server_conf['monitor'])
        servers.append(
            SocketConnector(name, loop, host, port))
    return ConfiguredCruiseModule(loop, servers)


class ConfiguredCruiseModule(ConfiguredModule):

    def __init__(self, loop, servers):
        import score.cruise
        super().__init__(score.cruise)
        self.loop = loop
        self.servers = servers

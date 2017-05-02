#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import os
import sys
import argparse

from zope import component

from zope.interface.adapter import _lookupAll as zopeLookupAll  # private API

from zope.intid.interfaces import IIntIds

from nti.contenttypes.courses.interfaces import ALL_COURSE_OUTLINE_INTERFACES

from nti.contenttypes.courses.interfaces import iface_of_node

from nti.dataserver.utils import run_with_dataserver
from nti.dataserver.utils.base_script import create_context

from nti.site.hostpolicy import get_all_host_sites

from nti.site.utils import unregisterUtility


def _lookupAll(main):
    result = {}
    required = ()
    order = len(required)
    for registry in main.utilities.ro:  # must keep order
        byorder = registry._adapters
        if order >= len(byorder):
            continue
        components = byorder[order]
        extendors = ALL_COURSE_OUTLINE_INTERFACES
        zopeLookupAll(components, required, extendors, result, 0, order)
        break  # break on first
    return result


def _process_site(current, intids, seen):
    site_name = current.__name__
    registry = current.getSiteManager()
    site_components = _lookupAll(registry)
    logger.info("%s outline node(s) found in %s",
                len(site_components), site_name)

    for ntiid, item in site_components.items():
        provided = iface_of_node(item)
        doc_id = intids.queryId(item)

        # registration for a removed outline
        if doc_id is None:
            logger.warn("Removing invalid registration %s from site %s",
                        ntiid, site_name)
            unregisterUtility(registry, item, provided=provided, name=ntiid)
            continue

        seen.add(ntiid)


def _process_args(verbose=False):
    seen = set()
    intids = component.getUtility(IIntIds)
    for current in get_all_host_sites():
        _process_site(current, intids, seen)


def main():
    arg_parser = argparse.ArgumentParser(description="Unregister invalid outline nodes")
    arg_parser.add_argument('-v', '--verbose', help="Be verbose", action='store_true',
                            dest='verbose')
    args = arg_parser.parse_args()

    env_dir = os.getenv('DATASERVER_DIR')
    if not env_dir or not os.path.exists(env_dir) and not os.path.isdir(env_dir):
        raise IOError("Invalid dataserver environment root directory")

    context = create_context(env_dir, with_library=True)
    conf_packages = ('nti.appserver',)

    run_with_dataserver(environment_dir=env_dir,
                        xmlconfig_packages=conf_packages,
                        verbose=args.verbose,
                        context=context,
                        function=lambda: _process_args(verbose=args.verbose))
    sys.exit(0)


if __name__ == '__main__':
    main()

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

from zope.component.hooks import site as current_site

from zope.intid import IIntIds

from nti.contenttypes.courses.interfaces import iface_of_node
from nti.contenttypes.courses.interfaces import ICourseOutlineNode

from nti.dataserver.utils import run_with_dataserver
from nti.dataserver.utils.base_script import create_context

from nti.site.utils import unregisterUtility
from nti.site.hostpolicy import get_all_host_sites

def unregister(registry, name, provided):
	return unregisterUtility(registry=registry,
					  		 provided=provided,
					  		 name=name)

def clean(verbose=False):
	result = 0
	intids = component.getUtility(IIntIds)
	for site in get_all_host_sites():
		with current_site(site):
			count = 0
			name = site.__name__
			registry = component.getSiteManager()
			for ntiid, obj in list(registry.getUtilitiesFor(ICourseOutlineNode)):
				if 	intids.queryId(obj) is None and \
					unregister(registry, ntiid, iface_of_node(obj)):
					count += 1
					if verbose:
						logger.warn("Removed %s from %s", ntiid, name)

			if verbose:
				logger.warn("Removed %s node(s) from %s", count, name)
			result += count
	if verbose:
		logger.info("Remove %s node(s)", result)
	return result

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
						function=lambda: clean(verbose=args.verbose))
	sys.exit(0)

if __name__ == '__main__':
	main()

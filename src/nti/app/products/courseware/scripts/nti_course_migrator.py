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

from nti.app.products.courseware.utils import course_migrator

from nti.contenttypes.courses.interfaces import ES_PUBLIC

from nti.dataserver.utils import run_with_dataserver
from nti.dataserver.utils.base_script import set_site
from nti.dataserver.utils.base_script import create_context

def _migrate(ntiid, scope=ES_PUBLIC, max_seat_count=25, sections=(),
			 site=None, dry_run=False, verbose=False):

	set_site(site)
	result = course_migrator(ntiid=ntiid,
							 scope=scope,
							 dry_run=dry_run,
							 verbose=verbose,
							 sections=sections,
							 max_seat_count=max_seat_count)
	return result

def main():
	arg_parser = argparse.ArgumentParser(description="Migrate enrollments from main course to sub-instances")
	arg_parser.add_argument('ntiid', help="Course entry identifier/ntiid")
	arg_parser.add_argument('-v', '--verbose', help="Be verbose", action='store_true',
							dest='verbose')
	arg_parser.add_argument('-c', '--count',
							dest='max_seat_count',
							default=25,
							type=int,
							help="Max seat count")
	arg_parser.add_argument('--sections',
							 dest='sections',
							 nargs="+",
							 default=(),
							 help="The names of sections to enroll")
	arg_parser.add_argument('--dry',
							 dest='dry_run',
							 action='store_true',
							 help="Dry run")
	arg_parser.add_argument('-s', '--scope',
							 dest='scope',
							 default=ES_PUBLIC,
							 help="Scope to migrate")
	arg_parser.add_argument('--site',
							dest='site',
							help="Application SITE.")
	args = arg_parser.parse_args()

	env_dir = os.getenv('DATASERVER_DIR')
	if not env_dir or not os.path.exists(env_dir) and not os.path.isdir(env_dir):
		raise IOError("Invalid dataserver environment root directory")

	site = args.site
	ntiid = args.ntiid
	scope = args.scope
	dry_run = args.dry_run
	sections = args.sections
	max_seat_count = args.max_seat_count

	if max_seat_count <= 0:
		raise ValueError("Invalid max seat count")

	context = create_context(env_dir, with_library=True)
	conf_packages = ('nti.appserver',)

	run_with_dataserver(environment_dir=env_dir,
						xmlconfig_packages=conf_packages,
						verbose=args.verbose,
						context=context,
						function=lambda: _migrate(site=site,
												  ntiid=ntiid,
												  scope=scope,
												  dry_run=dry_run,
												  sections=sections,
												  verbose=args.verbose,
												  max_seat_count=max_seat_count))
	sys.exit(0)

if __name__ == '__main__':
	main()

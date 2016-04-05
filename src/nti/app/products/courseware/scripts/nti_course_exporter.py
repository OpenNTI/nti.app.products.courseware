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

from nti.contenttypes.courses.interfaces import ICourseExporter
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseExportFiler

from nti.dataserver.utils import run_with_dataserver

from nti.dataserver.utils.base_script import set_site
from nti.dataserver.utils.base_script import create_context

from nti.ntiids.ntiids import find_object_with_ntiid

def _export(ntiid, path=None, site=None):
	set_site(site)
	course = find_object_with_ntiid(ntiid)
	course = ICourseInstance(course, None)
	if course is None:
		raise ValueError("Invalid course")

	path = path or os.getcwd()
	path = os.path.expanduser(path)
	if not os.path.exists(path):
		os.makedirs(path)
	elif not os.path.isdir(path):
		raise ValueError("Invalid output path")

	# prepare source filer
	filer = ICourseExportFiler(course)
	filer.prepare()

	# export course
	exporter = component.getUtility(ICourseExporter)
	exporter.export(course, filer)

	# zip contents
	zip_file = filer.asZip(path=path)

	# remove all content
	filer.reset()

	logger.info("Course exported to %s", zip_file)
	return zip_file

def main():
	arg_parser = argparse.ArgumentParser(description="Export a course")
	arg_parser.add_argument('-v', '--verbose', help="Be verbose", action='store_true',
							dest='verbose')
	arg_parser.add_argument('-p', '--path',
							dest='path',
							help="Output path")
	arg_parser.add_argument('-n', '--ntiid',
							dest='ntiid',
							help="Course NTIID")
	arg_parser.add_argument('-s', '--site',
							dest='site',
							help="Application SITE.")
	args = arg_parser.parse_args()

	env_dir = os.getenv('DATASERVER_DIR')
	if not env_dir or not os.path.exists(env_dir) and not os.path.isdir(env_dir):
		raise IOError("Invalid dataserver environment root directory")

	site = args.site
	ntiid = args.ntiid
	path = args.path or os.getcwd()

	if not ntiid:
		raise ValueError("No course specified")

	if not site:
		raise ValueError("No site specified")

	context = create_context(env_dir, with_library=True)
	conf_packages = ('nti.appserver',)

	run_with_dataserver(environment_dir=env_dir,
						xmlconfig_packages=conf_packages,
						verbose=args.verbose,
						context=context,
						function=lambda: _export(site=site,
												 path=path,
												 ntiid=ntiid))
	sys.exit(0)

if __name__ == '__main__':
	main()

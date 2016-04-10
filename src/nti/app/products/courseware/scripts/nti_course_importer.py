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
import shutil
import zipfile
import argparse
import tempfile

import transaction

from zope import component

from nti.cabinet.filer import DirectoryFiler

from nti.contenttypes.courses.interfaces import ICourseImporter
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.utils import run_with_dataserver

from nti.dataserver.utils.base_script import set_site
from nti.dataserver.utils.base_script import create_context

from nti.ntiids.ntiids import find_object_with_ntiid

def _import(ntiid, path=None, site=None, dry_run=False):
	set_site(site)
	course = find_object_with_ntiid(ntiid)
	course = ICourseInstance(course, None)
	if course is None:
		raise ValueError("Invalid course")

	try:
		if not os.path.isdir(path):
			if not zipfile.is_zipfile(path):
				raise IOError("Invalid archive")
			archive = zipfile.ZipFile(path)
			path = tmp_path = tempfile.mkdtemp()
			archive.extractall(tmp_path)
		else:
			tmp_path = None
	
		filer = DirectoryFiler(path)
		importer = component.getUtility(ICourseImporter)
		importer.process(course, filer)
	finally:
		if tmp_path:
			shutil.rmtree(tmp_path, True)
		if dry_run:
			transaction.doom()

	logger.info("Course imported from %s", path)

def main():
	arg_parser = argparse.ArgumentParser(description="Import a course")
	arg_parser.add_argument('-v', '--verbose', help="Be verbose", action='store_true',
							dest='verbose')
	arg_parser.add_argument('-p', '--path',
							dest='path',
							help="Archive path")
	arg_parser.add_argument('-n', '--ntiid',
							dest='ntiid',
							help="Course NTIID")
	arg_parser.add_argument('-s', '--site',
							dest='site',
							help="Application SITE.")
	arg_parser.add_argument('--dry',
							dest='dry_run',
							help="Dry run.")
	args = arg_parser.parse_args()

	env_dir = os.getenv('DATASERVER_DIR')
	if not env_dir or not os.path.exists(env_dir) and not os.path.isdir(env_dir):
		raise IOError("Invalid dataserver environment root directory")

	site = args.site
	ntiid = args.ntiid
	dry_run = args.dry_run
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
						function=lambda: _import(path=path,
												 site=site,
												 ntiid=ntiid,
												 dry_run=dry_run))
	sys.exit(0)

if __name__ == '__main__':
	main()

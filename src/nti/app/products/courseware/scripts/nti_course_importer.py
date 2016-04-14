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

from nti.contentlibrary.interfaces import IFilesystemBucket

from nti.contenttypes.courses.courses import ContentCourseInstance

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseImporter
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.utils import run_with_dataserver

from nti.dataserver.utils.base_script import set_site
from nti.dataserver.utils.base_script import create_context

from nti.ntiids.ntiids import find_object_with_ntiid

def _execute(course, path, dry_run=False):
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

def _import(ntiid, path, dry_run=False):
	course = find_object_with_ntiid(ntiid or u'')
	return _execute(course, path, dry_run=dry_run)

def _create(adm, key, path):
	catalog = component.getUtility(ICourseCatalog)
	if adm not in catalog:
		raise KeyError("Invalid Administrative level")
	adm_level = catalog[adm]
	root = adm_level.root
	if not IFilesystemBucket.providedBy(root):
		raise IOError("Administrative level does not have a root bucket")
	if key in adm_level:
		raise KeyError("Course key already created")

	course_path = os.path.join(root.absolute_path, key)
	if not os.path.exists(course_path):
		os.mkdir(course_path)
	course_root = root.getChildNamed(key)
	if course_root is None:
		raise IOError("Could not access course bucket %s", course_path)
	# create course and execute import
	course = ContentCourseInstance()
	course.root = course_root
	adm_level[key] = course
	return _execute(course, path)

def _process(args):
	set_site(args.site)
	path = os.path.expanduser(args.path or os.getcwd())
	if hasattr(args, 'ntiid'):
		_import(args.ntiid, path)
	else:
		_create(args.adm, args.key, path)

def main():
	arg_parser = argparse.ArgumentParser(description="Import a course")
	arg_parser.add_argument('-v', '--verbose', help="Be verbose", action='store_true',
							dest='verbose')

	parent_parser = argparse.ArgumentParser(add_help=False)
	parent_parser.add_argument('-p', '--path',
							   dest='path',
							   help="Archive path",
							   required=False)
	parent_parser.add_argument('-s', '--site',
							   dest='site',
							   help="Application SITE.",
							   required=True)

	subparsers = arg_parser.add_subparsers(help='sub-command help')

	# create
	parser_create = subparsers.add_parser('create', help='Create command',
										  parents=[parent_parser])
	parser_create.add_argument('-a', '--adm',
								dest='adm',
								help="Administrative level", required=True)
	parser_create.add_argument('-k', '--key',
								dest='key',
								help="Course key", required=True)

	# import
	parser_import = subparsers.add_parser('import', help='Import command',
										  parents=[parent_parser])
	parser_import.add_argument('-n', '--ntiid',
							   dest='ntiid',
							   help="Course NTIID", required=True)

	parsed = arg_parser.parse_args()
	if not parsed.site:
		raise ValueError("No site specified")
	env_dir = os.getenv('DATASERVER_DIR')
	if not env_dir or not os.path.exists(env_dir) and not os.path.isdir(env_dir):
		raise IOError("Invalid dataserver environment root directory")

	context = create_context(env_dir, with_library=True)
	conf_packages = ('nti.appserver',)

	run_with_dataserver(environment_dir=env_dir,
						xmlconfig_packages=conf_packages,
						verbose=parsed.verbose,
						context=context,
						function=lambda: _process(parsed))
	sys.exit(0)

if __name__ == '__main__':
	main()

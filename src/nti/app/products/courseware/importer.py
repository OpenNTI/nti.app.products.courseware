#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import os
import time
import shutil
import zipfile
import tempfile

from zope import component

from nti.cabinet.filer import DirectoryFiler

from nti.contentlibrary.interfaces import IFilesystemBucket

from nti.contenttypes.courses.courses import ContentCourseInstance
from nti.contenttypes.courses.courses import ContentCourseSubInstance

from nti.contenttypes.courses.interfaces import SECTIONS

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseImporter
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.ntiids.ntiids import find_object_with_ntiid

def check_archive(path):
	if not os.path.isdir(path):
		if not zipfile.is_zipfile(path):
			raise IOError("Invalid archive")
		archive = zipfile.ZipFile(path)
		tmp_path = tempfile.mkdtemp()
		archive.extractall(tmp_path)
	else:
		tmp_path = None
	return tmp_path

def create_dir(path):
	if not os.path.exists(path):
		os.mkdir(path)

def delete_dir(path):
	if path and os.path.exists(path):
		shutil.rmtree(path, True)

def _execute(course, archive_path):
	course = ICourseInstance(course, None)
	if course is None:
		raise ValueError("Invalid course")

	now = time.time()
	try:
		tmp_path = check_archive(archive_path)
		filer = DirectoryFiler(tmp_path or archive_path)
		importer = component.getUtility(ICourseImporter)
		importer.process(course, filer)
	finally:
		delete_dir(tmp_path)

	logger.info("Course imported from %s in %s", 
				archive_path, time.time() - now)

def import_course(ntiid, archive_path):
	"""
	Import a course from a file archive
	
	:param ntiid Course NTIID
	:param archive_path archive path
	"""
	course = find_object_with_ntiid(ntiid or u'')
	return _execute(course, archive_path)

def create_course(admin, key, archive_path, catalog=None):
	"""
	Creates a course from a file archive
	
	:param admin Administrative level key
	:param key Course name
	:param archive_path archive path
	"""
	catalog = component.getUtility(ICourseCatalog) if catalog is None else catalog
	if admin not in catalog:
		raise KeyError("Invalid Administrative level")

	administrative_level = catalog[admin]
	root = administrative_level.root
	if not IFilesystemBucket.providedBy(root):
		raise IOError("Administrative level does not have a root bucket")

	try:
		tmp_path = check_archive(archive_path)
		course_path = os.path.join(root.absolute_path, key)
		create_dir(course_path)

		course_root = root.getChildNamed(key)
		if course_root is None:
			raise IOError("Could not access course bucket %s", course_path)
		if key in administrative_level:
			course = administrative_level[key]
			logger.info("Course '%s' already created", key)
		else:
			course = ContentCourseInstance()
			course.root = course_root
			administrative_level[key] = course # gain intid

			# let's check for subinstances
			archive_sec_path = os.path.expanduser(tmp_path or archive_path)
			archive_sec_path = os.path.join(archive_sec_path, SECTIONS)
			if os.path.isdir(archive_sec_path):  # if found in archive
				sections_path = os.path.join(course_path, SECTIONS)
				create_dir(sections_path)
				sections_root = course_root.getChildNamed(SECTIONS)
				for name in os.listdir(archive_sec_path):
					ipath = os.path.join(archive_sec_path, name)
					if not os.path.isdir(ipath):
						continue

					# create subinstance
					subinstance_section_path = os.path.join(sections_path, name)
					create_dir(subinstance_section_path)

					# get chained root
					section_root = sections_root.getChildNamed(name)
					subinstance = ContentCourseSubInstance()
					subinstance.root = section_root
					course.SubInstances[name] = subinstance
		# process
		_execute(course, tmp_path or archive_path)
	finally:
		delete_dir(tmp_path)
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

from nti.contentlibrary.filesystem import FilesystemBucket

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
		# check for extract dir
		files = os.listdir(tmp_path)
		if len(files) == 1 and os.path.isdir(os.path.join(tmp_path, files[0])):
			tmp_path = os.path.join(tmp_path, files[0])
	else:
		tmp_path = None
	return tmp_path

def create_dir(path):
	if not os.path.exists(path):
		os.mkdir(path)

def delete_dir(path):
	if path and os.path.exists(path):
		shutil.rmtree(path, True)

def _execute(course, archive_path, writeout=True):
	course = ICourseInstance(course, None)
	if course is None:
		raise ValueError("Invalid course")

	now = time.time()
	try:
		tmp_path = check_archive(archive_path)
		filer = DirectoryFiler(tmp_path or archive_path)
		importer = component.getUtility(ICourseImporter)
		importer.process(course, filer, writeout)
	finally:
		delete_dir(tmp_path)

	logger.info("Course imported from %s in %s", 
				archive_path, time.time() - now)

def import_course(ntiid, archive_path, writeout=True):
	"""
	Import a course from a file archive
	
	:param ntiid Course NTIID
	:param archive_path archive path
	"""
	course = find_object_with_ntiid(ntiid or u'')
	return _execute(course, archive_path, writeout)

def create_course(admin, key, archive_path, catalog=None, writeout=True):
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
		if writeout:
			create_dir(course_path)

		course_root = root.getChildNamed(key)
		if course_root is None:
			if not writeout:
				course_root = FilesystemBucket()
				course_root.key = key
				course_root.bucket = root
				course_root.absolute_path = course_path
			else:
				raise IOError("Could not access course bucket %s", course_path)

		if key in administrative_level:
			course = administrative_level[key]
			logger.debug("Course '%s' already created", key)
		else:
			course = ContentCourseInstance()
			course.root = course_root
			administrative_level[key] = course # gain intid

			# let's check for subinstances
			archive_sec_path = os.path.expanduser(tmp_path or archive_path)
			archive_sec_path = os.path.join(archive_sec_path, SECTIONS)
			if os.path.isdir(archive_sec_path):  # if found in archive
				sections_path = os.path.join(course_path, SECTIONS)
				if writeout:
					create_dir(sections_path)
				sections_root = course_root.getChildNamed(SECTIONS)
				if sections_root is None:
					sections_root = FilesystemBucket()
					sections_root.key = SECTIONS
					sections_root.bucket = course_root
					sections_root.absolute_path = sections_path
				for name in os.listdir(archive_sec_path):
					ipath = os.path.join(archive_sec_path, name)
					if not os.path.isdir(ipath):
						continue

					# create subinstance
					subinstance_section_path = os.path.join(sections_path, name)
					if writeout:
						create_dir(subinstance_section_path)

					# get chained root
					sub_section_root = sections_root.getChildNamed(name)
					if sub_section_root is None:
						sub_section_root = FilesystemBucket()
						sub_section_root.key = name
						sub_section_root.bucket = sections_root
						sub_section_root.absolute_path = subinstance_section_path
					subinstance = ContentCourseSubInstance()
					subinstance.root = sub_section_root
					course.SubInstances[name] = subinstance # register
		# process
		_execute(course, tmp_path or archive_path, writeout)
	finally:
		delete_dir(tmp_path)

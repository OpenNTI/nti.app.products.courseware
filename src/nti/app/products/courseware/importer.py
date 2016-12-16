#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import os
import shutil
import zipfile
import tempfile

from zope import component
from zope import lifecycleevent

from zope.component.hooks import getSite

from nti.cabinet.filer import DirectoryFiler

from nti.common.string import to_unicode

from nti.contentfolder.interfaces import IRootFolder

from nti.contentlibrary.filesystem import FilesystemBucket

from nti.contentlibrary.interfaces import IFilesystemBucket
from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.interfaces import IDelimitedHierarchyContentPackageEnumeration

from nti.contenttypes.courses.courses import ContentCourseInstance
from nti.contenttypes.courses.courses import ContentCourseSubInstance
from nti.contenttypes.courses.courses import CourseAdministrativeLevel

from nti.contenttypes.courses.interfaces import SECTIONS

from nti.contenttypes.courses.interfaces import ICourseOutline
from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseImporter
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.presentation.interfaces import INTIMedia
from nti.contenttypes.presentation.interfaces import IConcreteAsset
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import IItemAssetContainer

from nti.coremetadata.interfaces import IRecordable

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
	if path and not os.path.exists(path):
		os.mkdir(path)

def mkdirs(path):
	if path and not os.path.exists(path):
		os.makedirs(path)

def delete_dir(path):
	if path and os.path.exists(path):
		shutil.rmtree(path, True)

def _lockout(course):
	logger.info("Locking course")
	def _do_lock(obj):
		if 		obj is not None \
			and IRecordable.providedBy(obj) \
			and not INTIMedia.providedBy(obj):
			obj.lock()
			lifecycleevent.modified(obj)

	def _lock_assets(asset):
		_do_lock(asset)
		_do_lock(IConcreteAsset(asset, None))
		if IItemAssetContainer.providedBy(asset):
			for item in asset.Items or ():
				_lock_assets(item)

	def _recur(node):
		if not ICourseOutline.providedBy(node):
			_do_lock(node)
		_lock_assets(INTILessonOverview(node, None))
		for child in node.values():
			_recur(child)
	_recur(course.Outline)

def _execute(course, archive_path, writeout=True, lockout=False, clear=False):
	course = ICourseInstance(course, None)
	if course is None:
		raise ValueError("Invalid course")
	if clear:
		root = IRootFolder(course)
		root.clear()

	tmp_path = None
	try:
		tmp_path = check_archive(archive_path)
		filer = DirectoryFiler(tmp_path or archive_path)
		importer = component.getUtility(ICourseImporter)
		result = importer.process(course, filer, writeout)
		if lockout:
			_lockout(course)
		return result
	finally:
		if tmp_path:
			delete_dir(tmp_path)

def import_course(ntiid, archive_path, writeout=True, lockout=False, clear=False):
	"""
	Import a course from a file archive

	:param ntiid Course NTIID
	:param archive_path archive path
	"""
	course = find_object_with_ntiid(ntiid or u'')
	_execute(course, archive_path, writeout, lockout, clear)
	return course

def install_admin_level(admin_name, catalog, site=None, writeout=True):
	site = getSite() if site is None else site
	library = component.getUtility(IContentPackageLibrary)
	enumeration = IDelimitedHierarchyContentPackageEnumeration(library)
	enumeration_root = enumeration.root
	courses_bucket = enumeration_root.getChildNamed(catalog.__name__)
	logger.info('[%s] Creating admin level %s', site.__name__, admin_name)
	admin_root = courses_bucket.getChildNamed(admin_name)
	if admin_root is None:
		path = os.path.join(courses_bucket.absolute_path, admin_name)
		if writeout:
			mkdirs(path)
			admin_root = courses_bucket.getChildNamed(admin_name)
		else:
			admin_root = FilesystemBucket()
			admin_root.key = admin_name
			admin_root.bucket = courses_bucket
			admin_root.absolute_path = path
	new_level = CourseAdministrativeLevel()
	new_level.root = admin_root
	catalog[admin_name] = new_level
	return new_level

def create_course(admin, key, archive_path, catalog=None, writeout=True,
				  lockout=False, clear=False):
	"""
	Creates a course from a file archive

	:param admin Administrative level key
	:param key Course name
	:param archive_path archive path
	"""
	catalog = component.getUtility(ICourseCatalog) if catalog is None else catalog
	if admin not in catalog:
		install_admin_level(admin, catalog)

	administrative_level = catalog[admin]
	root = administrative_level.root
	if not IFilesystemBucket.providedBy(root):
		raise IOError("Administrative level does not have a root bucket")

	tmp_path = None
	try:
		key = to_unicode(key)
		admin = to_unicode(admin)
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
			administrative_level[key] = course  # gain intid

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
					course.SubInstances[name] = subinstance  # register

		# process
		_execute(course, tmp_path or archive_path, writeout, lockout, clear)
		return course
	finally:
		delete_dir(tmp_path)

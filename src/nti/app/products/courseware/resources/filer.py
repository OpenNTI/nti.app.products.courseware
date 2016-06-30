#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import os

from zope import interface

from plone.namedfile.file import getImageInfo

from slugify import slugify_filename

from nti.app.contentfile import transfer_data

from nti.app.products.courseware import ASSETS_FOLDER

from nti.app.products.courseware.resources.interfaces import ICourseRootFolder
from nti.app.products.courseware.resources.interfaces import ICourseSourceFiler
from nti.app.products.courseware.resources.interfaces import ICourseContentFolder

from nti.app.products.courseware.resources.model import CourseContentFile
from nti.app.products.courseware.resources.model import CourseContentImage
from nti.app.products.courseware.resources.model import CourseContentFolder

from nti.app.products.courseware.resources.utils import get_assets_folder
from nti.app.products.courseware.resources.utils import get_images_folder
from nti.app.products.courseware.resources.utils import get_documents_folder
from nti.app.products.courseware.resources.utils import is_internal_file_link
from nti.app.products.courseware.resources.utils import to_external_file_link
from nti.app.products.courseware.resources.utils import get_file_from_external_link

from nti.contentfolder.utils import mkdirs
from nti.contentfolder.utils import traverse
from nti.contentfolder.utils import TraversalException

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.common.file import safe_filename

from nti.common.random import generate_random_hex_string

from nti.coremetadata.interfaces import SYSTEM_USER_ID

from nti.common.mimetypes import guess_type

from nti.traversal.traversal import find_interface

def get_unique_file_name(text, container):
	separator = '_'
	newtext = text
	slugified = slugify_filename(text)
	text_noe, ext = os.path.splitext(slugified)
	while True:
		if newtext not in container:
			break
		s = generate_random_hex_string(6)
		newtext = "%s%s%s%s" % (text_noe, separator, s, ext)
	return newtext

def get_namedfile_factory(source):
	contentType = getattr(source, 'contentType', None)
	if contentType:
		factory = CourseContentFile
	else:
		contentType, _, _ = getImageInfo(source)
		source.seek(0)  # reset
		factory = CourseContentFile if contentType else CourseContentImage
	contentType = contentType or u'application/octet-stream'
	return factory, contentType

def get_namedfile_from_source(source, name):
	factory, contentType = get_namedfile_factory(source)
	result = factory()
	result.name = name
	transfer_data(source, result)
	result.contentType = result.contentType or contentType
	# for filename we want to use the filename as originally provided on the source, not
	# the sluggified internal name. This allows us to give it back in the
	# Content-Disposition header on download
	result.filename = result.filename or getattr(source, 'name', name)
	return result

@interface.implementer(ICourseSourceFiler)
class CourseSourceFiler(object):

	def __init__(self, context=None, user=None, oid=True):
		self.oid = oid
		self.user = user
		self.course = ICourseInstance(context)

	@property
	def username(self):
		result = getattr(self.user, 'username', None)
		return result

	@property
	def root(self):
		result = ICourseRootFolder(self.course)
		return result

	@property
	def assets(self):
		result = get_assets_folder(self.course)
		return result

	@property
	def images(self):
		result = get_images_folder(self.course)
		return result

	@property
	def documents(self):
		result = get_documents_folder(self.course)
		return result
	
	def get_create_folders(self, parent, name):
		def builder():
			result = CourseContentFolder()
			result.creator = self.username or SYSTEM_USER_ID
			return result
		result = mkdirs(parent, name, factory=builder)
		return result
	get_create_folder = get_create_folders

	@classmethod
	def is_image(cls, key, contentType=None):
		result = 	(guess_type(key.lower())[0] or u'').startswith('image/') \
				 or (contentType or u'').startswith('image/')
		return result

	def save(self, key, source, contentType=None, bucket=None, 
			 overwrite=False, structure=False, **kwargs):
		username = self.username
		context = kwargs.get('context')
		if structure:
			bucket = self.images if self.is_image(key, contentType) else self.documents
		elif bucket == ASSETS_FOLDER: # legacy
			bucket = self.assets
		elif bucket:
			bucket = self.get_create_folders(self.root, bucket)
		else:
			bucket = self.root

		key = safe_filename(key)
		if overwrite:
			if key in bucket:
				bucket.remove(key)
		else:
			key = get_unique_file_name(key, bucket)

		namedfile = get_namedfile_from_source(source, key)
		namedfile.creator = username or SYSTEM_USER_ID  # set creator
		namedfile.contentType = contentType if contentType else namedfile.contentType
		bucket.add(namedfile)

		if context is not None:
			namedfile.add_association(context)
		
		# return external link
		result = self.get_external_link(namedfile)
		return result

	def get(self, key, bucket=None):
		result = None
		if is_internal_file_link(key):
			result = get_file_from_external_link(key)
			if result is not None:
				course = find_interface(result, ICourseInstance, strict=False)
				if course is not self.course:  # not the same course
					result = None
		elif bucket:
			context = traverse(self.root, bucket)
			if context is not None and key in context:
				result = context[key]
		else:
			path, key = os.path.split(key)
			context = traverse(self.root, path)
			if context is not None and key in context:
				result = context[key]
		return result

	def remove(self, key, bucket=None):
		try:
			result = self.get(key, bucket=bucket)
			if result is not None:
				parent = result.__parent__
				parent.remove(result)
				return True
		except TraversalException:
			pass
		return False

	def contains(self, key, bucket=None):
		if is_internal_file_link(key):
			result = self.get(key) is not None
		else:
			try:
				context = traverse(self.root, bucket) if bucket else self.root
				result = key in context
			except TraversalException:
				result = False
		return result
	
	def list(self, bucket=None):
		context = traverse(self.root, bucket) if bucket else self.root
		path = context.path or u'/'
		result = tuple(os.path.join(path, name) for name in context.keys())
		return result

	def is_bucket(self, bucket):
		try:
			context = traverse(self.root, bucket) if bucket else self.root
			result =	ICourseContentFolder.providedBy(context) \
					or	ICourseRootFolder.providedBy(context)
		except TraversalException:
			result = False
		return result
	isBucket = is_bucket

	def key_name(self, identifier):
		if is_internal_file_link(identifier):
			result = self.get(identifier)
			result = result.__name__ if result is not None else None
		else:
			result = os.path.split(identifier)[1]
		return result
	keyName = key_name
	
	def get_external_link(self, item):
		result = to_external_file_link(item, self.oid)
		return result
	to_external_link = get_external_link

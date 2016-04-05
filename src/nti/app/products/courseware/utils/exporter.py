#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import os
import six
from urlparse import urlparse

from nti.app.products.courseware import ASSETS_FOLDER

from nti.app.products.courseware.resources.interfaces import ICourseContentResource

from nti.app.products.courseware.resources.utils import is_internal_file_link
from nti.app.products.courseware.resources.utils import get_file_from_external_link

from nti.common import mimetypes

from nti.contenttypes.courses.interfaces import NTI_COURSE_FILE_SCHEME

def save_resources_to_filer(provided, obj, filer, ext_obj=None):
	"""
	parse the provided interface field and look for internal resources to
	be saved in the specified filer
	"""
	result = {}
	for name in provided:
		if name.startswith('_'):
			continue
		value = getattr(obj, name, None)
		if 	value is not None \
			and isinstance(value, six.string_types) \
			and is_internal_file_link(value):
			# get resource
			resource = get_file_from_external_link(value)
			contentType = resource.contentType
			if ICourseContentResource.providedBy(resource) and hasattr(resource, 'path'):
				path = resource.path
				path = os.path.split(path)[0]  # remove resource name
				path = path[1:] if path.startswith('/') else path
			else:
				path = ASSETS_FOLDER
			# save resource
			filer.save(resource.name, resource, bucket=path,
					   contentType=contentType, overwrite=True)
			# get course file scheme
			internal = NTI_COURSE_FILE_SCHEME + path + "/" + resource.name
			result[name] = internal
			if ext_obj is not None:
				ext_obj[name] = internal
	return result

def transfer_resources_from_filer(provided, obj, source_filer, target_filer):
	"""
	parse the provided interface field and look for internal resources to
	be gotten from the specified source filer and saved to the target filer
	"""
	result = {}
	for name in provided:
		if name.startswith('_'):
			continue
		value = getattr(obj, name, None)
		if 	value is not None \
			and isinstance(value, six.string_types) \
			and value.startswith(NTI_COURSE_FILE_SCHEME):

			path = urlparse(value).path
			bucket, name = os.path.split(path)
			bucket = None if not bucket else bucket
			
			source  = source_filer.get(path)
			contentType = getattr(source, 'contentType', None) or mimetypes.guess_type(name)
			if source is not None:
				href = target_filer.save(name, source, bucket=bucket, 
										 contentType=contentType,
								  		 overwrite=True)
				setattr(obj, name, href)
				result[name] = href
	return result

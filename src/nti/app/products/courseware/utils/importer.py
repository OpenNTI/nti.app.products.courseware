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

from zope.interface.interfaces import IMethod

from nti.common import mimetypes

from nti.contentfile.interfaces import IContentBaseFile

from nti.contenttypes.courses.interfaces import NTI_COURSE_FILE_SCHEME

def associate(obj, filer, key, bucket=None):
	source = filer.get(key=key, bucket=bucket)
	if IContentBaseFile.providedBy(source):
		source.add_association(obj)
		return filer.get_external_link(source)
	return None

def transfer_resources_from_filer(provided, obj, source_filer, target_filer):
	"""
	parse the provided interface field and look for internal resources to
	be gotten from the specified source filer and saved to the target filer
	"""
	result = {}
	if source_filer is target_filer:
		return result
	for field_name in provided:
		if field_name.startswith('_'):
			continue
		value = getattr(obj, field_name, None)
		if 		value is not None \
			and not IMethod.providedBy(value) \
			and isinstance(value, six.string_types) \
			and value.startswith(NTI_COURSE_FILE_SCHEME):

			path = urlparse(value).path
			bucket, name = os.path.split(path)
			bucket = None if not bucket else bucket
			
			# don't save if already in target filer.
			if target_filer.contains(key=name, bucket=bucket):
				href = associate(obj, target_filer, name, bucket)
				setattr(obj, field_name, href)
				continue
			
			source = source_filer.get(path)
			if source is not None:	
				contentType = getattr(source, 'contentType', None)
				contentType = contentType or mimetypes.guess_type(name)
				href = target_filer.save(name, source,
										 context=obj,
										 bucket=bucket, 
										 overwrite=True,
										 contentType=contentType)
				logger.debug("%s was saved as %s", value, href)
				setattr(obj, field_name, href)
				result[field_name] = href
	return result

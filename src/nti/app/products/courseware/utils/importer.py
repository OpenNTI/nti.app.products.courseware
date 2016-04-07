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

from nti.common import mimetypes

from nti.contenttypes.courses.interfaces import NTI_COURSE_FILE_SCHEME

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
		if 		value is not None \
			and isinstance(value, six.string_types) \
			and value.startswith(NTI_COURSE_FILE_SCHEME):

			path = urlparse(value).path
			bucket, name = os.path.split(path)
			bucket = None if not bucket else bucket
			
			source  = source_filer.get(path)
			if source is not None:
				contentType = getattr(source, 'contentType', None)
				contentType = contentType or mimetypes.guess_type(name)
				href = target_filer.save(name, source, bucket=bucket, 
										 contentType=contentType,
								  		 overwrite=True)
				setattr(obj, name, href)
				result[name] = href
	return result

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
import tempfile

from zope import component

from zope.component.hooks import site as current_site

from zope.security.management import endInteraction
from zope.security.management import restoreInteraction

from pyramid import httpexceptions as hexc

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.base.abstract_views import get_all_sources
from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.products.courseware import MessageFactory as _

from nti.app.products.courseware.importer import delete_dir
from nti.app.products.courseware.importer import create_course
from nti.app.products.courseware.importer import import_course

from nti.app.products.courseware.views import VIEW_IMPORT_COURSE
from nti.app.products.courseware.views import CourseAdminPathAdapter

from nti.cabinet.filer import transfer_to_native_file

from nti.common.file import safe_filename

from nti.common.maps import CaseInsensitiveDict

from nti.common.string import is_true

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.dataserver import authorization as nauth

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.site.hostpolicy import get_host_site

from nti.site.site import get_component_hierarchy_names

NTIID = StandardExternalFields.NTIID

class CourseImportMixin(ModeledContentUploadRequestUtilsMixin):

	def readInput(self, value=None):
		if self.request.body:
			result = ModeledContentUploadRequestUtilsMixin.readInput(self, value=value)
			return CaseInsensitiveDict(result)
		return CaseInsensitiveDict()

	def _get_source_paths(self, values):
		tmp_path = None
		path = values.get('path')
		if path and not os.path.exists(path):
			raise hexc.HTTPUnprocessableEntity(_('Invalid path.'))
		elif self.request.POST:
			source = None
			filename = None
			for name, source in get_all_sources(self.request, None).items():
				filename = getattr(source, 'filename', name)
				filename = safe_filename(os.path.split(filename)[1])
				break
			if not filename:
				raise hexc.HTTPUnprocessableEntity(_('No archive source uploaded.'))
			tmp_path = tempfile.mkdtemp()
			path = os.path.join(tmp_path, filename)
			transfer_to_native_file(source, path)
		elif not path:
			raise hexc.HTTPUnprocessableEntity(_('No archive source specified.'))
		return path, tmp_path

	def _do_call(self):
		pass

	def __call__(self):
		endInteraction()
		try:
			return self._do_call()
		finally:
			restoreInteraction()

@view_config(context=ICourseInstance)
@view_config(context=ICourseCatalogEntry)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   name=VIEW_IMPORT_COURSE,
			   permission=nauth.ACT_CONTENT_EDIT)
class CourseImportView(AbstractAuthenticatedView, CourseImportMixin):

	def _do_call(self):
		now = time.time()
		values = self.readInput()
		result = LocatedExternalDict()
		try:
			entry = ICourseCatalogEntry(self.context)
			path, tmp_path = self._get_source_paths(values)
			writeout = is_true(values.get('writeout') or values.get('save'))
			import_course(entry.ntiid, os.path.abspath(path), writeout)
			result['Elapsed'] = time.time() - now
			result['Course'] = ICourseInstance(self.context)
		finally:
			delete_dir(tmp_path)
		return result

@view_config(route_name='objects.generic.traversal',
			 renderer='rest',
			 name='ImportCourse',
			 request_method='POST',
			 context=CourseAdminPathAdapter,
			 permission=nauth.ACT_CONTENT_EDIT)
class ImportCourseView(AbstractAuthenticatedView, CourseImportMixin):

	def _import_course(self, ntiid, path, writeout=True):
		context = find_object_with_ntiid(ntiid)
		course = ICourseInstance(context, None)
		if course is None:
			raise hexc.HTTPUnprocessableEntity(_('Invalid course.'))
		return import_course(ntiid, path, writeout)

	def _create_course(self, admin, key, path, writeout=True):
		if not admin:
			msg = _('No administrative level specified.')
			raise hexc.HTTPUnprocessableEntity(msg)
		if not key:
			raise hexc.HTTPUnprocessableEntity(_('No course key specified.'))

		catalog = None
		for name in get_component_hierarchy_names(reverse=True):
			site = get_host_site(name)
			with current_site(site):
				adm_levels = component.queryUtility(ICourseCatalog)
				if adm_levels is not None and admin in adm_levels:
					catalog = adm_levels
					break
		if catalog is None:
			raise hexc.HTTPUnprocessableEntity(_('Invalid administrative level.'))
		return create_course(admin, key, path, catalog=catalog, writeout=writeout)

	def _do_call(self):
		now = time.time()
		values = self.readInput()
		result = LocatedExternalDict()
		params = result['Params'] = {}
		try:
			path, tmp_path = self._get_source_paths(values)
			path = os.path.abspath(path)
			ntiid = values.get('ntiid')
			writeout = is_true(values.get('writeout') or values.get('save'))
			if ntiid:
				params[NTIID] = ntiid
				course = self._import_course(ntiid, path, writeout)
			else:
				params['Key'] = key = values.get('key')
				params['Admin'] = admin = values.get('admin')
				course = self._create_course(admin, key, path, writeout)
			result['Course'] = course
			result['Elapsed'] = time.time() - now
		finally:
			delete_dir(tmp_path)
		return result

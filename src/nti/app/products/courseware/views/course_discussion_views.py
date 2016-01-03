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

from zope import interface
from zope import lifecycleevent

from pyramid.view import view_config
from pyramid.view import view_defaults
from pyramid import httpexceptions as hexc

from nti.app.base.abstract_views import get_all_sources
from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.contentfile import validate_sources

from nti.app.externalization.internalization import read_body_as_external_object

from nti.appserver.ugd_edit_views import UGDPutView
from nti.appserver.ugd_edit_views import UGDPostView
from nti.appserver.dataserver_pyramid_views import GenericGetView

from nti.common.property import Lazy
from nti.common.maps import CaseInsensitiveDict

from nti.contentfolder.interfaces import IContentFolder

from nti.contenttypes.courses.interfaces import DISCUSSIONS
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseInstancePublicScopedForum
from nti.contenttypes.courses.interfaces import ICourseInstanceForCreditScopedForum

from nti.contenttypes.courses.discussions.parser import path_to_course
from nti.contenttypes.courses.discussions.interfaces import NTI_COURSE_BUNDLE
from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussion
from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussions

from nti.dataserver import authorization as nauth

from nti.dataserver_core.interfaces import ILinkExternalHrefOnly

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.externalization import to_external_object

from nti.links.links import Link
from nti.links.externalization import render_link

from nti.namedfile.file import name_finder
from nti.namedfile.file import safe_filename

from nti.ntiids.ntiids import find_object_with_ntiid

from ..discussions import get_topic_key

from ..utils import get_assets_folder

from ._utils import _get_namedfile
from ._utils import _get_download_href
from ._utils import _get_file_from_link
from ._utils import _slugify_in_container

from . import CourseAdminPathAdapter

CLASS = StandardExternalFields.CLASS
ITEMS = StandardExternalFields.ITEMS
MIMETYPE = StandardExternalFields.MIMETYPE

def _get_unique_filename(folder, context, name):
	name = getattr(context, 'filename', None) or getattr(context, 'name', None) or name
	name = safe_filename(name_finder(name))
	result = _slugify_in_container(name, folder)
	return result

def _remove_file(href):
	if href and isinstance(href, six.string_types):
		named = _get_file_from_link(href)
		container = getattr(named, '__parent__', None)
		if IContentFolder.providedBy(container):
			return container.remove(named)
	return False

def to_external_href(resource):
	link = Link(target=resource)
	interface.alsoProvides(link, ILinkExternalHrefOnly)
	return render_link(link)

def _handle_multipart(context, discussion, sources):
	provided = ICourseDiscussion
	assets = get_assets_folder(context)
	for name, source in sources.items():
		if name in provided:
			# remove existing
			_remove_file(getattr(discussion, name, None))
			# save a new file
			file_key = _get_unique_filename(assets, source, name)
			namedfile = _get_namedfile(source, file_key)
			assets[file_key] = namedfile  # add to container
			location = _get_download_href(namedfile)
			setattr(discussion, name, location)

@view_config(context=ICourseDiscussions)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='GET',
			   permission=nauth.ACT_CONTENT_EDIT)
class CourseDiscussionsGetView(GenericGetView):

	def _do_call(self, discussions):
		result = LocatedExternalDict()
		result[MIMETYPE] = discussions.mimeType
		result[CLASS] = getattr(discussions, '__external_class_name__',
								discussions.__class__.__name__)
		items = result[ITEMS] = {}
		for name, discussion in discussions.items():
			ext_obj = to_external_object(discussion)
			ext_obj['href'] = to_external_href(discussion)
			items[name] = ext_obj
		result['ItemCount'] = len(items)
		result.__parent__ = self.context
		result.__name__ = self.request.view_name
		result.lastModified = discussions.lastModified
		return result

	def __call__(self):
		return self._do_call(self.context)

@view_config(context=ICourseCatalogEntry)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='GET',
			   name='CourseDiscussions',
			   permission=nauth.ACT_CONTENT_EDIT)
class CatalogEntryCourseDiscussionView(CourseDiscussionsGetView):

	@Lazy
	def _course(self):
		return ICourseInstance(self.context)

	def __call__(self):
		discussions = ICourseDiscussions(self._course)
		return self._do_call(discussions)

@view_config(context=ICourseDiscussions)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='POST',
			   permission=nauth.ACT_CONTENT_EDIT)
class CourseDiscussionsPostView(UGDPostView):

	content_predicate = ICourseDiscussion.providedBy

	def readCreateUpdateContentObject(self, creator, search_owner=False, externalValue=None):
		contentObject = self.doReadCreateUpdateContentObject(creator=creator,
															 search_owner=search_owner,
															 externalValue=externalValue)
		sources = get_all_sources(self.request)
		if sources:  # multi-part data
			validate_sources(contentObject, sources)
			_handle_multipart(self.context, contentObject, sources)
		return contentObject

	def _do_call(self):
		creator = self.remoteUser
		discussion = self.readCreateUpdateContentObject(creator, search_owner=False)
		discussion.creator = creator.username
		discussion.updateLastMod()

		# get a unique file nane
		name = _slugify_in_container("discussion.json", self.context)

		# set a proper NTI course bundle id
		course = ICourseInstance(self.context)
		path = os.path.join(path_to_course(course.root), DISCUSSIONS)
		iden = "%s://%s" % (NTI_COURSE_BUNDLE, os.path.join(path, name))
		discussion.id = iden

		# add discussion
		lifecycleevent.created(discussion)
		self.context[name] = discussion
		self.request.response.status_int = 201
		return discussion

@view_config(context=ICourseDiscussion)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='PUT',
			   permission=nauth.ACT_CONTENT_EDIT)
class CourseDiscussionPutView(UGDPutView):

	def updateContentObject(self, contentObject, externalValue, set_id=False, notify=True):
		result = UGDPutView.updateContentObject(self,
												contentObject,
												externalValue,
												set_id=set_id,
												notify=notify)

		sources = get_all_sources(self.request)
		if sources:
			validate_sources(result, sources)
			_handle_multipart(self.context, self.context, sources)
		return result

# admin

def _parse_courses(values):
	# get validate course entry
	ntiids = values.get('ntiid') or values.get('ntiids') or \
			 values.get('entry') or values.get('entries') or \
			 values.get('course') or values.get('courses')
	if not ntiids:
		raise hexc.HTTPUnprocessableEntity(detail='No course entry identifier')

	if isinstance(ntiids, six.string_types):
		ntiids = ntiids.split()

	result = []
	for ntiid in ntiids:
		context = find_object_with_ntiid(ntiid)
		context = ICourseCatalogEntry(context, None)
		if context is not None:
			result.append(context)
	return result

def _parse_course(values):
	result = _parse_courses(values)
	if not result:
		raise hexc.HTTPUnprocessableEntity(detail='Course not found')
	return result[0]

@view_config(name='DropCourseDiscussions')
@view_config(name='drop_course_discussions')
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   context=CourseAdminPathAdapter,
			   permission=nauth.ACT_NTI_ADMIN)
class DropCourseDiscussionsView(AbstractAuthenticatedView):

	def readInput(self):
		if self.request.body:
			values = read_body_as_external_object(self.request)
		else:
			values = self.request.params
		result = CaseInsensitiveDict(values)
		return result

	def __call__(self):
		values = self.readInput()
		courses = _parse_courses(values)
		if not courses:
			raise hexc.HTTPUnprocessableEntity(detail='Please specify a valid course')

		result = LocatedExternalDict()
		items = result[ITEMS] = {}
		for course in courses:
			course = ICourseInstance(course, None)
			entry = ICourseCatalogEntry(course, None)
			if course is None or entry is None:
				continue

			data = items[entry.ntiid] = {}
			course_discs = ICourseDiscussions(course, None) or {}
			course_discs = {get_topic_key(d) for d in course_discs.values()}
			if not course_discs:
				continue

			discussions = course.Discussions
			for forum in discussions.values():
				if 		not ICourseInstancePublicScopedForum.providedBy(forum) \
					and not ICourseInstanceForCreditScopedForum.providedBy(forum):
					continue

				for key in course_discs:
					if key in forum:
						del forum[key]
						data.setdefault(forum.__name__, [])
						data[forum.__name__].append(key)
		return result

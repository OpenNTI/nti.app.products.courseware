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

from pyramid import httpexceptions as hexc

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.base.abstract_views import get_all_sources
from nti.app.base.abstract_views import get_safe_source_filename
from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.contentfile import validate_sources

from nti.app.externalization.internalization import read_body_as_external_object

from nti.app.products.courseware import ASSETS_FOLDER

from nti.app.products.courseware.discussions import get_topic_key
from nti.app.products.courseware.discussions import create_topics
from nti.app.products.courseware.discussions import auto_create_forums

from nti.app.products.courseware.resources.filer import get_unique_file_name

from nti.app.products.courseware.resources.utils import get_course_filer
from nti.app.products.courseware.resources.utils import is_internal_file_link	

from nti.app.products.courseware.views._utils import is_true

from nti.app.products.courseware.views import VIEW_COURSE_DISCUSSIONS

from nti.app.products.courseware.views import CourseAdminPathAdapter

from nti.appserver.dataserver_pyramid_views import GenericGetView

from nti.appserver.ugd_edit_views import UGDPutView
from nti.appserver.ugd_edit_views import UGDPostView

from nti.common.maps import CaseInsensitiveDict

from nti.common.property import Lazy

from nti.contenttypes.courses.discussions.interfaces import NTI_COURSE_BUNDLE
from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussion
from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussions

from nti.contenttypes.courses.discussions.parser import parse_discussions
from nti.contenttypes.courses.discussions.parser import path_to_discussions

from nti.contenttypes.courses.interfaces import DISCUSSIONS

from nti.contenttypes.courses.interfaces import ICourseInstance 
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseInstancePublicScopedForum
from nti.contenttypes.courses.interfaces import ICourseInstanceForCreditScopedForum

from nti.dataserver import authorization as nauth

from nti.dataserver_core.interfaces import ILinkExternalHrefOnly

from nti.externalization.externalization import to_external_object

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

from nti.links.externalization import render_link

from nti.links.links import Link

from nti.ntiids.ntiids import find_object_with_ntiid

CLASS = StandardExternalFields.CLASS
ITEMS = StandardExternalFields.ITEMS
MIMETYPE = StandardExternalFields.MIMETYPE

def render_to_external_ref(resource):
	link = Link(target=resource)
	interface.alsoProvides(link, ILinkExternalHrefOnly)
	return render_link(link)

def _handle_multipart(context, user, discussion, sources):
	provided = ICourseDiscussion
	filer = get_course_filer(context, user)
	for name, source in sources.items():
		if name in provided:
			# remove existing
			location = getattr(discussion, name, None)
			if location and is_internal_file_link(location):
				filer.remove(location)
			# save a in a new file
			key = get_safe_source_filename(source, name)
			location = filer.save(key, source, overwrite=False,
								  bucket=ASSETS_FOLDER, context=discussion)
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
		items = result[ITEMS] = []
		for discussion in sorted(discussions.values()):
			ext_obj = to_external_object(discussion)
			ext_obj['href'] = render_to_external_ref(discussion)
			items.append(ext_obj)
		result['Total'] = result['ItemCount'] = len(items)
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
			   name=VIEW_COURSE_DISCUSSIONS,
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
		return contentObject, sources

	def _do_call(self):
		creator = self.remoteUser
		discussion, sources = self.readCreateUpdateContentObject(creator, search_owner=False)
		discussion.creator = creator.username
		discussion.updateLastMod()

		# get a unique file nane
		name = get_unique_file_name("discussion.json", self.context)

		# set a proper NTI course bundle id
		course = ICourseInstance(self.context)
		path = path_to_discussions(course)
		path = os.path.join(path, name)
		iden = "%s://%s" % (NTI_COURSE_BUNDLE, path)
		discussion.id = iden

		# add discussion
		lifecycleevent.created(discussion)
		self.context[name] = discussion
		
		# handle multi-part data
		if sources:  
			validate_sources(self.remoteUser, discussion, sources)
			_handle_multipart(self.context, self.remoteUser, discussion, sources)

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
			validate_sources(self.remoteUser, result, sources)
			_handle_multipart(self.context, self.remoteUser, self.context, sources)
		return result

# admin

def _parse_courses(values):
	# get validate course entry
	ntiids = values.get('ntiid') or values.get('ntiids')
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

@view_config(name='CreateCourseDiscussionTopics')
@view_config(name='create_course_discussion_topics')
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   context=CourseAdminPathAdapter,
			   permission=nauth.ACT_NTI_ADMIN)
class CreateCourseDiscussionTopicsView(AbstractAuthenticatedView):

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
			raise hexc.HTTPUnprocessableEntity('Please specify a valid course')

		result = LocatedExternalDict()
		items = result[ITEMS] = {}
		for course in courses:
			course = ICourseInstance(course)
			entry = ICourseCatalogEntry(course)
			data = items[entry.ntiid] = []
			auto_create_forums(course) # always
			discussions = ICourseDiscussions(course)
			for discussion in discussions.values():
				data.extend(create_topics(discussion))
		return result

@view_config(name='SyncCourseDiscussions')
@view_config(name='sync_course_discussions')
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   context=CourseAdminPathAdapter,
			   permission=nauth.ACT_NTI_ADMIN)
class SyncCourseDiscussionsView(AbstractAuthenticatedView):

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
			raise hexc.HTTPUnprocessableEntity('Please specify a valid course')

		force = is_true(values.get('force'))
		for course in courses:
			course = ICourseInstance(course)
			root = course.root
			if root is None:
				continue
			ds_bucket = root.getChildNamed(DISCUSSIONS)
			if ds_bucket is None:
				continue
			parse_discussions(course, ds_bucket, force=force)

		return hexc.HTTPNoContent()

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
			raise hexc.HTTPUnprocessableEntity('Please specify a valid course')

		result = LocatedExternalDict()
		items = result[ITEMS] = {}
		for course in courses:
			course = ICourseInstance(course)
			entry = ICourseCatalogEntry(course)
			data = items[entry.ntiid] = {}

			discussions = ICourseDiscussions(course)
			discussions = {get_topic_key(d) for d in discussions.values()}
			for forum in course.Discussions.values():
				if (	not ICourseInstancePublicScopedForum.providedBy(forum)
					and not ICourseInstanceForCreditScopedForum.providedBy(forum)):
					continue

				for key in discussions:
					if key in forum:
						del forum[key]
						data.setdefault(forum.__name__, [])
						data[forum.__name__].append(key)
		return result

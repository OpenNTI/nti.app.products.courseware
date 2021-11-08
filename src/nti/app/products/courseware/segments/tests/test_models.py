#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import sys

from contextlib import contextmanager
from unittest import TestCase

import fudge

from hamcrest import is_
from hamcrest import all_of
from hamcrest import contains
from hamcrest import assert_that
from hamcrest import has_entries
from hamcrest import has_length
from hamcrest import has_properties
from hamcrest import not_none
from nti.contenttypes.courses.sharing import CourseInstanceSharingScopes

from zope import component

from zope.component.hooks import getSite

from zope.lifecycleevent import modified

from zope.schema.vocabulary import SimpleVocabulary

from nti.app.products.courseware.segments.interfaces import ENROLLED_IN
from nti.app.products.courseware.segments.interfaces import ICourseMembershipFilterSet
from nti.app.products.courseware.segments.interfaces import NOT_ENROLLED_IN

from nti.app.products.courseware.segments.tests import SharedConfiguringTestLayer

from nti.app.products.courseware.segments.model import CourseProgressFilterSet
from nti.app.products.courseware.segments.model import CourseMembershipFilterSet

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.segments.tests.test_views import SegmentManagementTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.app.users.utils import set_user_creation_site

from nti.contenttypes.completion.progress import CompletionContextProgress

from nti.contenttypes.courses.interfaces import ENROLLMENT_SCOPE_VOCABULARY

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseEnrollmentManager

from nti.dataserver.tests import mock_dataserver

from nti.dataserver.users import User

from nti.externalization import to_external_object
from nti.externalization import update_from_external_object

from nti.externalization.internalization import find_factory_for

from nti.externalization.tests import externalizes

from nti.testing.matchers import verifiably_provides


class TestCourseMembershipFilterSet(TestCase):

    layer = SharedConfiguringTestLayer

    def test_valid_interface(self):
        course_ntiid = u'tag:nextthought.com,2021-10-11:filterset-one'
        assert_that(CourseMembershipFilterSet(course_ntiid=course_ntiid,
                                              operator=ENROLLED_IN),
                    verifiably_provides(ICourseMembershipFilterSet))

    def _internalize(self, external):
        factory = find_factory_for(external)
        assert_that(factory, is_(not_none()))
        new_io = factory()
        if new_io is not None:
            update_from_external_object(new_io, external)
        return new_io

    def test_internalize(self):
        course_ntiid = u'tag:nextthought.com,2021-10-11:filterset-one'
        ext_obj = {
            "MimeType": CourseMembershipFilterSet.mime_type,
            "course_ntiid": course_ntiid,
            "operator": NOT_ENROLLED_IN
        }
        filter_set = self._internalize(ext_obj)
        assert_that(filter_set, has_properties(
            course_ntiid=course_ntiid,
            operator=NOT_ENROLLED_IN
        ))

    def test_externalize(self):
        course_ntiid = u'tag:nextthought.com,2021-10-11:filterset-one'
        filter_set = CourseMembershipFilterSet(course_ntiid=course_ntiid,
                                               operator=ENROLLED_IN)
        assert_that(filter_set,
                    externalizes(all_of(has_entries({
                        'MimeType': CourseMembershipFilterSet.mime_type,
                        "course_ntiid": course_ntiid,
                        "operator": ENROLLED_IN,
                    }))))


class TestApplyCourseMembershipFilterSet(SegmentManagementTest):

    layer = PersistentInstructedCourseApplicationTestLayer

    default_origin = 'http://platform.ou.edu'

    def _create_and_enroll(self, username, section=None, scope=None):
        with mock_dataserver.mock_db_trans():
            if not User.get_user(username):
                self._create_user(username)

        with mock_dataserver.mock_db_trans(site_name='platform.ou.edu'):
            user = User.get_user(username)
            set_user_creation_site(user, getSite())
            modified(user)

            cat = component.getUtility(ICourseCatalog)
            course = cat['Fall2015']['CS 1323']
            if section:
                course = course.SubInstances[section]
            manager = ICourseEnrollmentManager(course)
            scope = scope or 'ForCreditDegree'
            manager.enroll(user, scope=scope)

    def get_entry_ntiid(self, section=None):
        with mock_dataserver.mock_db_trans(site_name='platform.ou.edu'):
            cat = component.getUtility(ICourseCatalog)
            course = cat['Fall2015']['CS 1323']
            if section:
                course = course.SubInstances[section]

            return ICourseCatalogEntry(course).ntiid

    @WithSharedApplicationMockDS(users=('parent_user',
                                        'section_user1',
                                        'section_user2',
                                        'non_enrolled_user'),
                                 testapp=True,
                                 default_authenticate=True)
    def test_any_course(self):
        parent_user = u'parent_user'
        section_user1 = u'section_user1'
        section_user2 = u'section_user2'
        non_enrolled_user = 'non_enrolled_user'

        self.init_users(non_enrolled_user, parent_user, section_user1, section_user2)

        enrolled_members_url, not_enrolled_members_url = self._create_initial_course_membership_segments()

        res = self.testapp.get(not_enrolled_members_url).json_body
        assert_that(res['Items'], has_length(4))

        # Enroll some of the users
        self._create_and_enroll(parent_user)
        self._create_and_enroll(section_user1, section='010', scope='Public')
        self._create_and_enroll(section_user2, section='995', scope='Purchased')

        res = self.testapp.get(enrolled_members_url).json_body
        assert_that(res['Items'], has_length(3))

        res = self.testapp.get(not_enrolled_members_url).json_body
        assert_that(res['Items'], has_length(1))

    @WithSharedApplicationMockDS(users=('parent_user',
                                        'section_user1',
                                        'section_user2',
                                        'non_enrolled_user'),
                                 testapp=True,
                                 default_authenticate=True)
    def test_single_course(self):
        parent_user = u'parent_user'
        section_user1 = u'section_user1'
        section_user2 = u'section_user2'
        non_enrolled_user = 'non_enrolled_user'

        self.init_users(non_enrolled_user, parent_user, section_user1, section_user2)

        entry_ntiid = self.get_entry_ntiid(section='010')
        enrolled_members_url, not_enrolled_members_url = \
            self._create_initial_course_membership_segments(entry_ntiid=entry_ntiid)

        res = self.testapp.get(not_enrolled_members_url).json_body
        assert_that(res['Items'], has_length(4))

        # Enroll some of the users
        self._create_and_enroll(parent_user)
        self._create_and_enroll(section_user1, section='010', scope='Public')
        self._create_and_enroll(section_user2, section='995', scope='Purchased')

        res = self.testapp.get(enrolled_members_url).json_body
        assert_that(res['Items'], has_length(1))

        res = self.testapp.get(not_enrolled_members_url).json_body
        assert_that(res['Items'], has_length(3))

        # Ensure proper handling of courses no longer available
        with patched('nti.app.products.courseware.segments.model.find_object_with_ntiid') \
                as find_object_with_ntiid:

            find_object_with_ntiid.is_callable().returns(None)

            res = self.testapp.get(enrolled_members_url).json_body
            assert_that(res['Items'], has_length(0))

            res = self.testapp.get(not_enrolled_members_url).json_body
            assert_that(res['Items'], has_length(4))

    @WithSharedApplicationMockDS(users=('enrolled_user',
                                        'unenrolled_user'),
                                 testapp=True,
                                 default_authenticate=True)
    def test_course_scopes(self):
        enrolled_user = u'enrolled_user'
        unenrolled_learner = u'unenrolled_user'
        self.init_users(enrolled_user, unenrolled_learner)

        enrolled_members_url, not_enrolled_members_url = \
            self._create_initial_course_membership_segments(self.get_entry_ntiid())

        all_enrolled_members_url, all_not_enrolled_members_url = \
            self._create_initial_course_membership_segments()

        res = self.testapp.get(not_enrolled_members_url).json_body
        assert_that(res['Items'], has_length(2))

        self._create_and_enroll(enrolled_user, scope='Public')

        res = self.testapp.get(enrolled_members_url).json_body
        assert_that(res['Items'], has_length(1))

        res = self.testapp.get(not_enrolled_members_url).json_body
        assert_that(res['Items'], has_length(1))

        # Remove test scope from the course
        with mock_dataserver.mock_db_trans(site_name='platform.ou.edu'):
            cat = component.getUtility(ICourseCatalog)
            course = cat['Fall2015']['CS 1323']
            del course.SharingScopes['Public']

        # Have to get creative here, b/c CourseInstanceSharingScopes
        # requires any new items to be in ENROLLMENT_SCOPE_VOCABULARY,
        # restricting additions. Further, removals are restricted by our
        # need to call initScopes() prior to filter set evaluation, to
        # ensure they've been initialized at all, and this repopulates any
        # missing from that vocab.
        def vocab_without_public(_self):
            return SimpleVocabulary(
                [term for term in ENROLLMENT_SCOPE_VOCABULARY
                 if term.token != 'Public'])

        with fudge.patched_context(CourseInstanceSharingScopes,
                                   '_vocabulary',
                                   vocab_without_public):

            res = self.testapp.get(enrolled_members_url).json_body
            assert_that(res['Items'], has_length(0))

            res = self.testapp.get(not_enrolled_members_url).json_body
            assert_that(res['Items'], has_length(2))

            res = self.testapp.get(all_enrolled_members_url).json_body
            assert_that(res['Items'], has_length(1))

            res = self.testapp.get(all_not_enrolled_members_url).json_body
            assert_that(res['Items'], has_length(1))

    def _create_initial_course_membership_segments(self, entry_ntiid=None):
        enrolled_members_url = self._create_course_membership_segment(
            'Enrolled in Any Course',
            entry_ntiid=entry_ntiid
        )

        not_enrolled_members_url = self._create_course_membership_segment(
            'Not Enrolled in Any Course',
            operator='not enrolled in',
            entry_ntiid=entry_ntiid
        )

        # No one enrolled yet
        res = self.testapp.get(enrolled_members_url).json_body
        assert_that(res['Items'], has_length(0))

        return enrolled_members_url, not_enrolled_members_url

    def _create_course_membership_segment(self,
                                          title,
                                          operator='enrolled in',
                                          entry_ntiid=None):
        simple_filter_set = CourseMembershipFilterSet(course_ntiid=entry_ntiid,
                                                      operator=operator)
        simple_filter_set = to_external_object(simple_filter_set)
        segment = self._create_segment(title,
                                       simple_filter_set=simple_filter_set).json_body

        return self.require_link_href_with_rel(segment, 'members')

    def init_users(self, *users):
        with mock_dataserver.mock_db_trans(site_name='platform.ou.edu'):
            for username in users:
                user = self._get_user(username)
                set_user_creation_site(user, getSite())
                modified(user)


class TestCourseProgressFilterSet(SegmentManagementTest):

    layer = PersistentInstructedCourseApplicationTestLayer

    default_origin = 'http://platform.ou.edu'

    def _create_and_enroll(self, username, section=None, scope=None):
        with mock_dataserver.mock_db_trans():
            if not User.get_user(username):
                self._create_user(username)

        with mock_dataserver.mock_db_trans(site_name='platform.ou.edu'):
            user = User.get_user(username)
            set_user_creation_site(user, getSite())
            modified(user)

            cat = component.getUtility(ICourseCatalog)
            course = cat['Fall2015']['CS 1323']
            if section:
                course = course.SubInstances[section]
            manager = ICourseEnrollmentManager(course)
            scope = scope or 'ForCreditDegree'
            manager.enroll(user, scope=scope)

    def get_entry_ntiid(self, section=None):
        with mock_dataserver.mock_db_trans(site_name='platform.ou.edu'):
            cat = component.getUtility(ICourseCatalog)
            course = cat['Fall2015']['CS 1323']
            if section:
                course = course.SubInstances[section]

            return ICourseCatalogEntry(course).ntiid

    def init_users(self, *users):
        with mock_dataserver.mock_db_trans(site_name='platform.ou.edu'):
            for username in users:
                user = self._get_user(username)
                set_user_creation_site(user, getSite())
                modified(user)
                
    def _create_progress_segment(self,
                                 title,
                                 percentage,
                                 operator,
                                 entry_ntiid):
        filter_set = CourseProgressFilterSet(course_ntiid=entry_ntiid,
                                             operator=operator,
                                             percentage=percentage)
        filter_set = to_external_object(filter_set)
        segment = self._create_segment(title,
                                       simple_filter_set=filter_set).json_body
        return self.require_link_href_with_rel(segment, 'members')

    @WithSharedApplicationMockDS(users=('user_progress1',
                                        'user_progress2',
                                        'user_progress3'),
                                 testapp=True,
                                 default_authenticate=True)
    @fudge.patch('nti.app.contenttypes.completion.adapters.CompletionContextProgressFactory.__call__')
    def test_progress_filter(self, mock_progress):
        # Need a non-zero required item set here
        empty_progress = CompletionContextProgress(AbsoluteProgress=0,
                                                   MaxPossibleProgress=10,
                                                   HasProgress=False)
        fifty_progress = CompletionContextProgress(AbsoluteProgress=5,
                                                   MaxPossibleProgress=10,
                                                   HasProgress=True)
        hundred_progress = CompletionContextProgress(AbsoluteProgress=10,
                                                     MaxPossibleProgress=10,
                                                     HasProgress=False)
        fake_progress = mock_progress.is_callable()
        fake_progress.returns(empty_progress)
        
        def with_progress():
            fake_progress.next_call().returns(fifty_progress)
            fake_progress.next_call().returns(hundred_progress)
            fake_progress.next_call().returns(empty_progress)
        
        user_progress1 = u'user_progress1'
        user_progress2 = u'user_progress2'
        user_progress3 = u'user_progress3'
        
        def _get_usernames(url):
            res = self.testapp.get(url).json_body
            result = []
            for item_ext in res['Items']:
                result.append(item_ext['Username'])
            return result
        
        # Empty
        entry_ntiid = self.get_entry_ntiid()
        zero_ge_url = self._create_progress_segment('zero_ge_progress', 0, 
                                                    'ge', entry_ntiid)
        
        zero_eq_url = self._create_progress_segment('zero_eq_progress', 0, 
                                                    'eq', entry_ntiid)
        
        fifty_gt_url = self._create_progress_segment('fifty_lt_progress', .5, 
                                                     'gt', entry_ntiid)
        
        one_lt_url = self._create_progress_segment('one_lt_progress', 1, 
                                                   'lt', entry_ntiid)

        for url in (zero_ge_url, zero_eq_url, fifty_gt_url, one_lt_url):
            usernames = _get_usernames(url)
            assert_that(usernames, has_length(0))
        
        # Enroll
        self.init_users(user_progress1, user_progress2, user_progress3)
        
        # Enroll some of the users
        self._create_and_enroll(user_progress1)
        self._create_and_enroll(user_progress2)
        self._create_and_enroll(user_progress3)
        
        for url in (fifty_gt_url,):
            usernames = _get_usernames(url)
            assert_that(usernames, has_length(0))
            
        for url in (zero_ge_url, zero_eq_url, one_lt_url):
            usernames = _get_usernames(url)
            assert_that(usernames, has_length(3))
            assert_that(usernames, contains('user_progress1', 'user_progress2', 'user_progress3'))
        
        # With progress
        with_progress()
        usernames = _get_usernames(zero_eq_url)
        assert_that(usernames, contains('user_progress1'))
        
        with_progress()
        usernames = _get_usernames(zero_ge_url)
        assert_that(usernames, contains('user_progress1', 'user_progress2', 'user_progress3'))
        
        with_progress()
        usernames = _get_usernames(fifty_gt_url)
        assert_that(usernames, contains('user_progress3'))
        
        with_progress()
        usernames = _get_usernames(one_lt_url)
        assert_that(usernames, contains('user_progress1', 'user_progress2'))
        
        # Ensure proper handling of courses no longer available
        with patched('nti.app.products.courseware.segments.model.find_object_with_ntiid') \
                as find_object_with_ntiid:

            find_object_with_ntiid.is_callable().returns(None)
            res = self.testapp.get(zero_ge_url).json_body
            assert_that(res['Items'], has_length(0))


@contextmanager
def patched(path):
    obj, attr = path.rsplit('.', 1)
    fake = fudge.Fake(attr)
    inner_context_manager = fudge.patched_context(obj, attr, fake)
    inner_context_manager.__enter__()
    try:
        yield fake
    except Exception as e:
        etype, val, tb = sys.exc_info()
        inner_context_manager.__exit__(etype, val, tb)
        raise e
    else:
        inner_context_manager.__exit__(None, None, None)

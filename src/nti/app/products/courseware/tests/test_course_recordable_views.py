#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import is_not
from hamcrest import has_length
from hamcrest import assert_that
does_not = is_not

from nti.testing.time import time_monotonically_increases

import fudge

from random import shuffle

from nti.app.products.courseware import VIEW_RECURSIVE_AUDIT_LOG

from nti.app.products.courseware.views.view_mixins import AbstractRecursiveTransactionHistoryView

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollmentManager

from nti.dataserver.users.users import User

from nti.externalization.interfaces import StandardExternalFields

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.ntiids.oids import to_external_ntiid_oid

from nti.recorder.record import TransactionRecord

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.dataserver.tests import mock_dataserver

ITEMS = StandardExternalFields.ITEMS
LAST_MODIFIED = StandardExternalFields.LAST_MODIFIED

BATCH_SIZE = AbstractRecursiveTransactionHistoryView._DEFAULT_BATCH_SIZE
TX_POOL_SIZE = BATCH_SIZE * 1.5
TX_POOL_SIZE = int(TX_POOL_SIZE)


class TestCourseRecursiveTransactionHistory(ApplicationLayerTest):

    layer = PersistentInstructedCourseApplicationTestLayer
    testapp = None

    default_origin = 'http://janux.ou.edu'
    catalog_ntiid = u'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2013_CLC3403_LawAndJustice'

    def _do_enroll(self):
        with mock_dataserver.mock_db_trans(self.ds):
            # The janux policy enforces first/last names.
            self._create_user(u'student_user')

        with mock_dataserver.mock_db_trans(self.ds, site_name='janux.ou.edu'):
            open_user = User.get_user('student_user')
            course = find_object_with_ntiid(self.catalog_ntiid)
            course = ICourseInstance(course)
            self.course_oid = to_external_ntiid_oid(course)
            manager = ICourseEnrollmentManager(course)
            manager.enroll(open_user)

    tx_pool = None
    next_tx_idx = 0

    def _get_txs(self, _):
        """
        Returns transactions from a shuffled pool. The pool is initialized
        with default-batch-size * 1.5 items, with an ordered tid per record.
        """
        if not self.tx_pool:
            txs = []
            for i in range(TX_POOL_SIZE):
                record = TransactionRecord(principal=u'martin_chatwin',
                                           tid=u'%s' % i,
                                           attributes=tuple())
                txs.append(record)
            shuffle(txs)
            self.tx_pool = txs
        try:
            result = self.tx_pool[self.next_tx_idx]
        except IndexError:
            return ()
        self.next_tx_idx += 1
        # Return iterable
        return (result,)

    @time_monotonically_increases
    @WithSharedApplicationMockDS(users=True,
                                 testapp=True,
                                 default_authenticate=True)
    @fudge.patch('nti.app.products.courseware.views.view_mixins.AbstractRecursiveTransactionHistoryView._get_transactions')
    def test_audit_log(self, mock_get_txs):
        # Student does not have access
        self._do_enroll()
        student_environ = self._make_extra_environ('student_user')
        res = self.fetch_by_ntiid(self.catalog_ntiid, self.testapp,
                                  extra_environ=student_environ)
        self.forbid_link_with_rel(res.json_body, VIEW_RECURSIVE_AUDIT_LOG)

        # Admin user
        res = self.fetch_by_ntiid(self.course_oid)
        log_link = self.require_link_href_with_rel(
            res.json_body, VIEW_RECURSIVE_AUDIT_LOG)

        # Student fails
        self.testapp.get(log_link, extra_environ=student_environ, status=403)

        # Test empty
        mock_get_txs.is_callable().returns(())
        res = self.testapp.get(log_link)
        res = res.json_body
        assert_that(res.get(ITEMS), has_length(0))
        assert_that(res.get('ItemCount'), is_(0))
        assert_that(res.get('TotalItemCount'), is_(0))

        # Test base results
        mock_get_txs.is_callable().calls(self._get_txs)
        res = self.testapp.get(log_link)
        res = res.json_body
        records = res.get(ITEMS)
        assert_that(records, has_length(BATCH_SIZE))
        # By default, first 20 items are returned.
        item_tids = [x.get('tid') for x in records]
        assert_that(item_tids, is_(['%s' % y for y in range(BATCH_SIZE)]))
        assert_that(res.get('ItemCount'), is_(BATCH_SIZE))
        assert_that(res.get('TotalItemCount'), is_(TX_POOL_SIZE))

        max_created_time = max((x.createdTime for x in self.tx_pool))
        assert_that(res.get(LAST_MODIFIED), is_(max_created_time))

        # Test reverse sort, max batch size.
        self.next_tx_idx = 0
        href = log_link + '?sortOrder=%s&batchSize=%s'
        res = self.testapp.get(href % ('descending', 50))
        res = res.json_body
        records = res.get(ITEMS)
        assert_that(records, has_length(TX_POOL_SIZE))

        # Most recent items are returned first.
        item_tids = [x.get('tid') for x in records]
        item_tids.reverse()
        assert_that(item_tids, is_(['%s' % y for y in range(TX_POOL_SIZE)]))
        assert_that(res.get('ItemCount'), is_(TX_POOL_SIZE))
        assert_that(res.get('TotalItemCount'), is_(TX_POOL_SIZE))
        assert_that(res.get(LAST_MODIFIED), is_(max_created_time))

#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from zope.schema import vocabulary

from nti.ntiids.schema import ValidNTIID

from nti.schema.field import ValidChoice

from nti.segments.interfaces import IUserFilterSet

ENROLLED_IN = u"enrolled in"
NOT_ENROLLED_IN = u"not enrolled in"

ENROLLMENT_OPS = (ENROLLED_IN,
                  NOT_ENROLLED_IN)

ENROLLMENT_OP_VOCABULARY = vocabulary.SimpleVocabulary(
    tuple(vocabulary.SimpleTerm(x) for x in ENROLLMENT_OPS)
)


class ICourseMembershipFilterSet(IUserFilterSet):
    """
    A filter set describing users enrolled, or not enrolled, in the given
    course.
    """

    course_ntiid = ValidNTIID(title=u'Course NTIID',
                              description=u'NTIID of the course in which to check membership.',
                              required=True)

    operator = ValidChoice(title=u'Operator',
                           description=u'Whether to check for enrolled or not enrolled users.',
                           vocabulary=ENROLLMENT_OP_VOCABULARY,
                           required=True)
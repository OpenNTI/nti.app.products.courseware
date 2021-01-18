from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from pyramid.view import view_config

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.products.acclaim.interfaces import IAcclaimBadge

from nti.app.products.courseware.acclaim.interfaces import ICourseAcclaimBadgeContainer

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.dataserver.authorization import ACT_CONTENT_EDIT

from nti.externalization.interfaces import StandardExternalFields

ITEMS = StandardExternalFields.ITEMS
TOTAL = StandardExternalFields.TOTAL
ITEM_COUNT = StandardExternalFields.ITEM_COUNT

logger = __import__('logging').getLogger(__name__)


@view_config(route_name='objects.generic.traversal',
             context=ICourseAcclaimBadgeContainer,
             request_method='POST',
             permission=ACT_CONTENT_EDIT,
             renderer='rest')
class CourseAcclaimBadgesInsertView(AbstractAuthenticatedView,
                                    ModeledContentUploadRequestUtilsMixin):
    """
    Allow creating a new badge tied to this course.
    """

    content_predicate = IAcclaimBadge.providedBy

    def _do_call(self):
        acclaim_badge = self.readCreateUpdateContentObject(self.remoteUser)
        result = self.context.get_or_create_badge(acclaim_badge)
        return result

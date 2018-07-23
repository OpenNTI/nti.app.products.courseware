#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods

from hamcrest import none
from hamcrest import not_none
from hamcrest import has_entries
from hamcrest import assert_that

from nti.testing.matchers import verifiably_provides

from nti.externalization.externalization import to_external_object

from nti.app.products.courseware.webinars.assets import WebinarAsset

from nti.app.products.courseware.webinars.interfaces import IWebinarAsset

from nti.app.products.webinar.client_models import Webinar
from nti.app.products.webinar.client_models import WebinarSession

from nti.app.products.courseware.tests import CourseLayerTest

from nti.externalization.internalization import find_factory_for
from nti.externalization.internalization import update_from_external_object

webinar_asset_json = {
        "MimeType": WebinarAsset.mime_type,
        "webinar": {
              "numberOfRegistrants": 0,
              "MimeType": Webinar.mime_type,
              "times": [
                {
                  "MimeType": WebinarSession.mime_type,
                  "startTime": u"2018-07-09T17:00:00Z",
                  "endTime": u"2018-07-09T18:00:00Z"
                }],
              "description": u"desc",
              "subject": u"subject",
              "inSession": True,
              "organizerKey": "13431343",
              "webinarKey": "11111111",
              "webinarID": u"web_id",
              "timeZone": u"tz",
              "registrationUrl": u"http://reg_url",}
}


class TestWebinarInternalization(CourseLayerTest):

    def test_webinar_asset(self):
        factory = find_factory_for(webinar_asset_json)
        assert_that(factory, not_none())
        webinar_asset = factory()
        update_from_external_object(webinar_asset, webinar_asset_json, require_updater=True)

        assert_that(webinar_asset, verifiably_provides(IWebinarAsset))
        assert_that(webinar_asset.title, none())
        assert_that(webinar_asset.description, none())
        assert_that(webinar_asset.webinar, not_none())
        webinar = webinar_asset.webinar
        assert_that(webinar.__parent__, not_none())

        asset_ext = to_external_object(webinar_asset)
        assert_that(asset_ext, has_entries('webinar', not_none(),
                                           'title', none(),
                                           'description', none()))

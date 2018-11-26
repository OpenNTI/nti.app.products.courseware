#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

import os
import shutil
import tempfile

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.products.courseware.cartridge.renderer import execute
from nti.app.products.courseware.cartridge.renderer import get_renderer

from nti.app.products.courseware.qti.interfaces import ICanvasMeta
from nti.app.products.courseware.qti.interfaces import IQTIAssessment

from nti.assessment import IQAssignment
from nti.assessment import IQuestionSet

from nti.contenttypes.presentation.interfaces import INTIAssignmentRef
from nti.contenttypes.presentation.interfaces import INTIQuestionSetRef

from nti.dataserver import authorization as nauth

from nti.ntiids.ntiids import find_object_with_ntiid

__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)


@view_defaults(route_name='objects.generic.traversal',
               request_method='GET',
               permission=nauth.ACT_CREATE,
               renderer='rest',
               name='qti')
class QTIAssessmentView(AbstractAuthenticatedView):
    """
    For convenience, this view also accepts refs
    """

    @view_config(context=IQuestionSet)
    @view_config(context=IQAssignment)
    def _export(self, assignment=None):
        assignment = assignment if assignment else self.context
        qti = IQTIAssessment(assignment)
        export = qti.export()
        meta_obj = ICanvasMeta(qti)
        m_exp = meta_obj.meta()
        archive = tempfile.mkdtemp()
        lao_dir = os.path.join(archive, unicode(qti.identifier))
        non_cc = os.path.join(archive, unicode('non_cc_assessments'))
        os.makedirs(lao_dir)
        os.makedirs(non_cc)
        lao_path = os.path.join(lao_dir, '%s.xml' % qti.identifier)
        with open(lao_path, 'w') as lao:
            lao.write(export.encode('utf-8'))
        meta_path = os.path.join(lao_dir, 'assessment_meta.xml')
        with open(meta_path, 'w') as meta:
            meta.write(m_exp.encode('utf-8'))
        renderer = get_renderer('manifest', '.pt', package='nti.app.products.courseware.qti')
        for source_path, target in qti.dependencies.items():
            target_path = os.path.join(archive, target)
            if not os.path.exists(os.path.dirname(target_path)):
                os.makedirs(os.path.dirname(target_path))
            shutil.copy(source_path, target_path)

        context = {'dep_href': '%s/assessment_meta.xml' % unicode(qti.identifier),
                   'assessment_href': '%s/%s.xml' % (unicode(qti.identifier), unicode(qti.identifier)),
                   'identifier': unicode(qti.identifier),
                   'dependencies': qti.dependencies.values()}
        manifest = execute(renderer, {'context': context})
        man_path = os.path.join(archive, 'imsmanifest.xml')
        with open(man_path, 'w') as base:
            base.write(manifest)
        zipped = shutil.make_archive(qti.title, 'zip', archive)
        self.request.response.content_encoding = 'identity'
        self.request.response.content_type = 'application/zip; charset=UTF-8'
        self.request.response.content_disposition = 'attachment; filename="%s.zip"' % qti.title
        self.request.response.body_file = open(zipped, "rb")
        return self.request.response

    @view_config(context=INTIQuestionSetRef)
    @view_config(context=INTIAssignmentRef)
    def _export_ref(self):
        concrete = find_object_with_ntiid(self.context.target)
        return self._do_export(concrete)




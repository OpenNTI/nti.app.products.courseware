#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

import os
import shutil
import tempfile

from pyramid import httpexceptions as hexc

from pyramid.view import view_config
from pyramid.view import view_defaults

from zope import component

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.products.courseware.cartridge.renderer import execute
from nti.app.products.courseware.cartridge.renderer import get_renderer

from nti.app.products.courseware.qti.interfaces import IQTIAssessment

from nti.app.products.courseware.qti.models import CanvasQuizMeta

from nti.assessment.interfaces import IQAssessment

from nti.contenttypes.courses.interfaces import ICourseInstance

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

    @view_config(context=ICourseInstance)
    def export(self, assignment=None, course=None):
        course = course if course else self.context
        if assignment is None:
            params = self.request.params
            ntiid = params.get('ntiid') or params.get('NTIID')
            if ntiid is None:
                return hexc.HTTPUnprocessableEntity(u'NTIID parameter must be provided.')
            assignment = find_object_with_ntiid(ntiid)
            if not IQAssessment.providedBy(assignment):
                return hexc.HTTPUnprocessableEntity(u'Object %s is not an valid QTI type' % assignment)
        qti = component.queryMultiAdapter((assignment, course), IQTIAssessment)
        meta = CanvasQuizMeta(qti, course)
        m_exp = meta.meta()
        export = qti.export()
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
        for (dep_directory, deps) in qti.dependencies.items():
            for dep in deps:
                dep.export(os.path.join(archive, dep_directory))

        context = {'dep_href': '%s/assessment_meta.xml' % unicode(qti.identifier),
                   'assessment_href': '%s/%s.xml' % (unicode(qti.identifier), unicode(qti.identifier)),
                   'identifier': unicode(qti.identifier),
                   'dependencies': [os.path.join('dependencies', dep.path_to) for dep in qti.dependencies['dependencies']]}
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
    def export_ref(self):
        # Refs can resolve to a course
        concrete = find_object_with_ntiid(self.context.target)
        course = ICourseInstance(self.context)
        return self.export(concrete, course)




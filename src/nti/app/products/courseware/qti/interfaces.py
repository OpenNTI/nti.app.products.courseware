#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

from zope import interface

from nti.schema.field import ValidTextLine as TextLine, Number, DateTime, Int
from nti.schema.field import ValidText
from zope.schema import Bool, Choice

__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)


class IQTIAssessment(interface.Interface):
    """
    A QTI Assessment
    """


class IQTIItem(interface.Interface):
    """
    One unit of QTI Assessment
    """


class ICanvasQuizMeta(interface.Interface):

    title = TextLine(title=u'Quiz Title',
                     description=u'This will be the quiz title.',
                     required=True)

    description = ValidText(title=u'Quiz Description',
                            description=u'This will be the quiz description body.',
                            required=False)

    points_possible = Number(title=u'Points Possible',
                             description=u'The number of points possible for this quiz.',
                             default=100.0,
                             required=False)

    lock_at = DateTime(title=u'Unavailable date',
                       description=u'The DateTime to lock this quiz.',
                       required=False)

    unlock_at = DateTime(title=u'Available date',
                         description=u'The DateTime to unlock this quiz.',
                         required=False)

    module_locked = Bool(title=u'Module locked',
                         description=u'Should the module containing this quiz be locked?',
                         required=False,
                         default=False)

    due_at = DateTime(title=u'Due date',
                      description=u'The date this quiz is due.',
                      required=False)

    shuffle_answers = Bool(title=u'Shuffle Answers',
                           description=u'Should the answers be shuffled?',
                           required=False,
                           default=False)

    hide_results = Bool(title=u'Hide Results',
                        description=u'Should the quiz results be hidden?',
                        required=False,
                        default=False)

    require_lockdown_browser = Bool(title=u'Require LockDown browser',
                                    description=u'Should this quiz require the Respondus LockDown browser?',
                                    required=False,
                                    default=False)

    require_lockdown_browser_for_results = Bool(title=u'Require LockDown browser for results',
                                                description=u'Should this quiz require the Respondus LockDown browser '
                                                            u'to view the results?',
                                                required=False,
                                                default=False)

    require_lockdown_browser_monitor = Bool(title=u'Require LockDown browser monitor',
                                            description=u'Should this quiz require the Respondus LockDown browser'
                                                        u' monitor?',
                                            required=False,
                                            default=False)

    access_code = TextLine(title=u'Access Code',
                           description=u'The access code for this quiz',
                           required=False)

    show_correct_answers = Bool(title=u'Show correct answers',
                                description=u'Should the correct answers be shown for this quiz?',
                                required=False,
                                default=True)

    show_correct_answers_at = DateTime(title=u'Answers available date',
                                       description=u'The DateTime the answers to this quiz should be available.',
                                       required=False)

    hide_correct_answers_at = DateTime(title=u'Answers unavailable date',
                                       description=u'The DateTime the answers to this quiz become unavailable.',
                                       required=False)

    anonymous_submissions = Bool(title=u'Anonymous Submissions',
                                 description=u'Should these quiz submissions be anonymous?',
                                 required=False,
                                 default=False)

    # Not sure what this is
    could_be_locked = Bool(title=u'Could be locked',
                           description=u'Could this quiz be locked?',
                           required=False,
                           default=False)

    available = Bool(title=u'Available',
                     description=u'Is this quiz available?',
                     required=False,
                     default=False)

    # TODO figure out the units on this
    time_limit = Int(title=u'Time Limit',
                     description=u'The number of seconds allowed on this quiz',
                     required=False)

    allowed_attempts = Int(title=u'Allowed Attempts',
                           description=u'The number of allowed attempts.',
                           required=False,
                           default=1)

    one_question_at_a_time = Bool(title=u'One question at a time',
                                  description=u'Should the questions for this quiz be shown sequentially?',
                                  required=False,
                                  default=False)

    cant_go_back = Bool(title=u'Can\'t go back',
                        description=u'Can you go back after you answer a question?',
                        required=False,
                        default=False)

    one_time_results = Bool(title=u'One Time Results',
                            description=u'Are the results to this quiz only available one time?',
                            required=False,
                            default=False)

    show_correct_answers_last_attempt = Bool(title=u'Show Correct Answers on last attempt',
                                             description=u'Should the correct answers to this quiz be shown '
                                                         u'on the last attempt?')

    # Not sure what this is
    only_visible_to_overrides = Bool(title=u'Only visible to overrides',
                                     description=u'Is this quiz only available to overrides?',
                                     required=False,
                                     default=False)

    # This is defined in the Course Settings/assignment_groups.xml
    assignment_group_identifierref = TextLine(title=u'Assignment Group Identifier Ref',
                                              description=u'The identifier for the assignment group this belongs in.',
                                              required=False,
                                              default=u'Canvas')

    quiz_type = Choice(title=u'Quiz type',
                       description=u'The type for this quiz.',
                       required=False,
                       default=u'practice_quiz',
                       values=(u'practice_quiz',
                               u'assignment',
                               u'survey',
                               u'graded_survey'))

    scoring_policy = Choice(title=u'Scoring Policy',
                            description=u'The scoring policy for this quiz.',
                            required=False,
                            default=u'keep_highest',
                            values=(u'keep_highest',
                                    u'keep_latest',
                                    u'keep_average'))

    identifier = TextLine(title=u'Unique Identifier',
                          description=u'The identifier for this quiz. This MUST be non-numeric.',
                          required=True)


# Graded quizzes are assignments nested in quiz metadata
class ICanvasAssignmentSettings(interface.Interface):

    title = TextLine(title=u'Assignment Title',
                     description=u'The title for this assignment in the Assignments tab.',
                     required=True)

    # There may be more options here
    workflow_state = Choice(title=u'Assignment workflow state',
                            description=u'The assignment workflow state',
                            values=(u'available',
                                    u'unpublished'),
                            default=u'unpublished',
                            required=True)

    points_possible = Number(title=u'Points Possible',
                             description=u'The number of points possible for this assignment.',
                             default=100.0,
                             required=False)

    lock_at = DateTime(title=u'Unavailable date',
                       description=u'The DateTime to lock this assignment.',
                       required=False)

    unlock_at = DateTime(title=u'Available date',
                         description=u'The DateTime to unlock this assignment.',
                         required=False)

    quiz_identifierref = TextLine(title=u'Quiz Identifier Ref',
                                  description=u'The identifier of the quiz associated with this assignment.',
                                  required=False)

    module_locked = Bool(title=u'Module locked',
                         description=u'Should the module containing this quiz be locked?',
                         required=False,
                         default=False)

    due_at = DateTime(title=u'Due date',
                      description=u'The date this quiz is due.',
                      required=False)

    # This is defined in the Course Settings/assignment_groups.xml
    assignment_group_identifierref = TextLine(title=u'Assignment Group Identifier Ref',
                                              description=u'The identifier for the assignment group this belongs in.',
                                              required=False,
                                              default=u'Canvas')

    # TODO get these keys right
    submission_types = Choice(title=u'Assignment submission type',
                              description=u'The submission type for this assignment.',
                              required=False,
                              default=u'online_quiz',
                              values=(u'online_quiz',
                                      u'file_upload',
                                      u'paper'))

    identifier = TextLine(title=u'Unique Identifier',
                          description=u'The identifier for this quiz. This MUST be non-numeric.',
                          required=True)

    # TODO get these keys right
    grading_type = Choice(title=u'Assignment grading type',
                          description=u'The grading type for this assignment.',
                          required=False,
                          default=u'points',
                          values=(u'points',
                                  u'pass_fail'))

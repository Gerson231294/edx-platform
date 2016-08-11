"""
Tests for course utils.
"""

from django.test import TestCase
import mock
from opaque_keys.edx.locations import SlashSeparatedCourseKey
from student.tests.factories import UserFactory
from util.course import get_link_for_about_page


class CourseAboutLinkTestCase(TestCase):
    """ Tests for Course About link. """

    def setUp(self):
        super(CourseAboutLinkTestCase, self).setUp()
        self.user = UserFactory.create(password="password")

    def test_about_page_lms(self):
        """ Get URL for about page, no marketing site """
        with mock.patch.dict('django.conf.settings.FEATURES', {'ENABLE_MKTG_SITE': False}):
            self.assertEquals(self.get_about_page_link(), "http://localhost:8000/courses/mitX/101/test/about")
        with mock.patch.dict('django.conf.settings.FEATURES', {'ENABLE_MKTG_SITE': True}):
            with mock.patch(
                'openedx.core.djangoapps.catalog.utils.get_course_run',
                return_value={}
            ):
                self.assertEquals(self.get_about_page_link(), "http://localhost:8000/courses/mitX/101/test/about")

    def test_about_page_marketing_site(self):
        """ Get URL for about page, marketing site enabled """
        with mock.patch.dict('django.conf.settings.FEATURES', {'ENABLE_MKTG_SITE': True}):
            with mock.patch(
                'openedx.core.djangoapps.catalog.utils.get_course_run',
                return_value={"marketing_url": "https://marketing-url/course/course-title-mitX-101-test"}
            ):
                self.assertEquals(self.get_about_page_link(), "https://marketing-url/course/course-title-mitX-101-test")

    def get_about_page_link(self):
        """ create mock course and return the about page link."""
        course_key = SlashSeparatedCourseKey('mitX', '101', 'test')
        return get_link_for_about_page(course_key, self.user)

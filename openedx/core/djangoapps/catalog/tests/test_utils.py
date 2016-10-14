"""Tests covering utilities for integrating with the catalog service."""
import json
import urllib
import uuid

import ddt
from django.core.cache import cache
from django.test import TestCase
import httpretty
import mock
from opaque_keys.edx.keys import CourseKey
from openedx.core.djangolib.testing.utils import CacheIsolationTestCase

from openedx.core.djangoapps.catalog import utils
from openedx.core.djangoapps.catalog.models import CatalogIntegration
from openedx.core.djangoapps.catalog.tests import factories, mixins
from student.tests.factories import UserFactory


UTILS_MODULE = 'openedx.core.djangoapps.catalog.utils'


@mock.patch(UTILS_MODULE + '.get_edx_api_data')
# ConfigurationModels use the cache. Make every cache get a miss.
@mock.patch('config_models.models.cache.get', return_value=None)
class TestGetPrograms(mixins.CatalogIntegrationMixin, TestCase):
    """
    Tests covering retrieval of programs from the catalog service.
    """
    def setUp(self):
        super(TestGetPrograms, self).setUp()

        self.user = UserFactory()
        self.uuid = str(uuid.uuid4())
        self.type = 'FooBar'
        self.catalog_integration = self.create_catalog_integration(cache_ttl=1)

    def assert_contract(self, call_args, program_uuid=None, type=None):  # pylint: disable=redefined-builtin
        """Verify that API data retrieval utility is used correctly."""
        args, kwargs = call_args

        for arg in (self.catalog_integration, self.user, 'programs'):
            self.assertIn(arg, args)

        self.assertEqual(kwargs['resource_id'], program_uuid)

        cache_key = '{base}.programs{type}'.format(
            base=self.catalog_integration.CACHE_KEY,
            type='.' + type if type else ''
        )
        self.assertEqual(
            kwargs['cache_key'],
            cache_key if self.catalog_integration.is_cache_enabled else None
        )

        self.assertEqual(kwargs['api']._store['base_url'], self.catalog_integration.internal_api_url)  # pylint: disable=protected-access

        querystring = {
            'marketable': 1,
            'exclude_utm': 1,
        }
        if type:
            querystring['type'] = type
        self.assertEqual(kwargs['querystring'], querystring)

        return args, kwargs

    def test_get_programs(self, _mock_cache, mock_get_catalog_data):
        programs = [factories.Program() for __ in range(3)]
        mock_get_catalog_data.return_value = programs

        data = utils.get_programs(self.user)

        self.assert_contract(mock_get_catalog_data.call_args)
        self.assertEqual(data, programs)

    def test_get_one_program(self, _mock_cache, mock_get_catalog_data):
        program = factories.Program()
        mock_get_catalog_data.return_value = program

        data = utils.get_programs(self.user, uuid=self.uuid)

        self.assert_contract(mock_get_catalog_data.call_args, program_uuid=self.uuid)
        self.assertEqual(data, program)

    def test_get_programs_by_type(self, _mock_cache, mock_get_catalog_data):
        programs = [factories.Program() for __ in range(2)]
        mock_get_catalog_data.return_value = programs

        data = utils.get_programs(self.user, type=self.type)

        self.assert_contract(mock_get_catalog_data.call_args, type=self.type)
        self.assertEqual(data, programs)

    def test_programs_unavailable(self, _mock_cache, mock_get_catalog_data):
        mock_get_catalog_data.return_value = []

        data = utils.get_programs(self.user)

        self.assert_contract(mock_get_catalog_data.call_args)
        self.assertEqual(data, [])

    def test_cache_disabled(self, _mock_cache, mock_get_catalog_data):
        self.catalog_integration = self.create_catalog_integration(cache_ttl=0)
        utils.get_programs(self.user)
        self.assert_contract(mock_get_catalog_data.call_args)

    def test_config_missing(self, _mock_cache, _mock_get_catalog_data):
        """Verify that no errors occur if this method is called when catalog config is missing."""
        CatalogIntegration.objects.all().delete()

        data = utils.get_programs(self.user)
        self.assertEqual(data, [])


class TestMungeCatalogProgram(TestCase):
    """
    Tests covering querystring stripping.
    """
    catalog_program = factories.Program()

    def test_munge_catalog_program(self):
        munged = utils.munge_catalog_program(self.catalog_program)
        expected = {
            'id': self.catalog_program['uuid'],
            'name': self.catalog_program['title'],
            'subtitle': self.catalog_program['subtitle'],
            'category': self.catalog_program['type'],
            'marketing_slug': self.catalog_program['marketing_slug'],
            'organizations': [
                {
                    'display_name': organization['name'],
                    'key': organization['key']
                } for organization in self.catalog_program['authoring_organizations']
            ],
            'course_codes': [
                {
                    'display_name': course['title'],
                    'key': course['key'],
                    'organization': {
                        'display_name': course['owners'][0]['name'],
                        'key': course['owners'][0]['key']
                    },
                    'run_modes': [
                        {
                            'course_key': run['key'],
                            'run_key': CourseKey.from_string(run['key']).run,
                            'mode_slug': 'verified'
                        } for run in course['course_runs']
                    ],
                } for course in self.catalog_program['courses']
            ],
            'banner_image_urls': {
                'w1440h480': self.catalog_program['banner_image']['large']['url'],
                'w726h242': self.catalog_program['banner_image']['medium']['url'],
                'w435h145': self.catalog_program['banner_image']['small']['url'],
                'w348h116': self.catalog_program['banner_image']['x-small']['url'],
            },
        }

        self.assertEqual(munged, expected)


#@mock.patch(UTILS_MODULE + '.get_edx_api_data')
#@mock.patch('config_models.models.cache.get', return_value=None)
@httpretty.activate
class TestGetCourseRun(mixins.CatalogIntegrationMixin, CacheIsolationTestCase):
    """
    Tests covering retrieval of course runs from the catalog service.
    """

    ENABLED_CACHES = ['default']

    def setUp(self):
        super(TestGetCourseRun, self).setUp()

        self.user = UserFactory()
        #self.course_key = CourseKey.from_string('foo/bar/baz')
        #self.course_key = 'foo/bar/baz'
        self.catalog_integration = self.create_catalog_integration()
        self.course_key_1 = 'foo1/bar1/baz1'
        self.course_key_2 = 'foo2/bar2/baz2'
        self.course_key_3 = 'foo3/bar3/baz3'
        self.course_key_4 = 'foo4/bar4/baz4'
        # self.course_keys = ['foo1/bar1/baz1', 'foo2/bar2/baz2', 'foo3/bar3/baz3', 'foo4/bar4/baz4']
        # self.register_catalog_course_run_response(
        #      self.course_keys,
        #      [
        #          self.minimum_catalog_course_run_object(
        #              "foo1/bar1/baz1", "https://marketing-url/course/course-title-foo1-bar1-baz1"
        #          ),
        #          self.minimum_catalog_course_run_object(
        #              "foo2/bar2/baz2", "https://marketing-url/course/course-title-foo2-bar2-baz2"
        #          ),
        #          self.minimum_catalog_course_run_object("foo3/bar3/baz3", None),
        #      ]
        # )

    def minimum_catalog_course_run_object(self, course_key, has_marketing_url=True):
        return {
            "key": course_key,
            "marketing_url": ("https://marketing-url/course/course-title-{}".format(course_key)
                              if has_marketing_url else None),
            "test_key": "test_value",
        }

    def expected_data_object(self, course_key, has_marketing_url=True):
        return {
            "key": course_key,
            "marketing_url": ("https://marketing-url/course/course-title-{}".format(course_key)
                              if has_marketing_url else None),
            "test_key": "test_value",
        }

    # def assert_contract(self, call_args):
    #     """Verify that API data retrieval utility is used correctly."""
    #     args, kwargs = call_args
    #
    #     for arg in (self.catalog_integration, self.user, 'course_runs'):
    #         self.assertIn(arg, args)
    #
    #     #self.assertEqual(kwargs['resource_id'], unicode(self.course_key))
    #     self.assertEqual(kwargs['resource_id'], self.course_key)
    #     self.assertEqual(kwargs['api']._store['base_url'], self.catalog_integration.internal_api_url)  # pylint: disable=protected-access
    #
    #     return args, kwargs

    def test_config_missing(self):
        """Verify that no errors occur if this method is called when catalog config is missing."""
        CatalogIntegration.objects.all().delete()

        data = utils.get_course_runs(self.user, [])
        self.assertEqual(data, {})

    def test_get_course_run(self):
        course_keys = [self.course_key_1]
        self.register_catalog_course_run_response(
             course_keys, [self.minimum_catalog_course_run_object(self.course_key_1)]
        )

        course_catalog_data_dict = utils.get_course_runs(self.user, course_keys)
        expected_data = {self.course_key_1: self.expected_data_object(self.course_key_1)}
        self.assertEqual(expected_data, course_catalog_data_dict)

    def test_get_multiple_course_run(self):
        course_keys = [self.course_key_1, self.course_key_2, self.course_key_3]
        self.register_catalog_course_run_response(course_keys, [
            self.minimum_catalog_course_run_object(self.course_key_1),
            self.minimum_catalog_course_run_object(self.course_key_2),
            self.minimum_catalog_course_run_object(self.course_key_3, has_marketing_url=False),
        ])

        course_catalog_data_dict = utils.get_course_runs(self.user, course_keys)
        expected_data = {
            self.course_key_1: self.expected_data_object(self.course_key_1),
            self.course_key_2: self.expected_data_object(self.course_key_2),
            self.course_key_3: self.expected_data_object(self.course_key_3, has_marketing_url=False),
        }
        self.assertEqual(expected_data, course_catalog_data_dict)

    def test_course_run_unavailable(self):
        course_keys = [self.course_key_1, self.course_key_4]
        self.register_catalog_course_run_response(
            course_keys, [self.minimum_catalog_course_run_object(self.course_key_1)]
        )

        course_catalog_data_dict = utils.get_course_runs(self.user, course_keys)
        expected_data = {self.course_key_1: self.expected_data_object(self.course_key_1)}
        self.assertEqual(expected_data, course_catalog_data_dict)

    def test_cached_course_run_data(self):
        course_keys = [self.course_key_1, self.course_key_2]
        self.register_catalog_course_run_response(
             course_keys,
             [
                 self.minimum_catalog_course_run_object(
                     self.course_key_1, self.expected_data_object(self.course_key_1)
                 ),
                 self.minimum_catalog_course_run_object(
                     self.course_key_2, self.expected_data_object(self.course_key_2)
                 ),
             ]
        )
        expected_data = {
            self.course_key_1: self.expected_data_object(self.course_key_1),
            self.course_key_2: self.expected_data_object(self.course_key_2)
        }

        course_catalog_data_dict = utils.get_course_runs(self.user, course_keys)
        self.assertEqual(expected_data, course_catalog_data_dict)
        cached_data = cache.get_many(course_keys)
        self.assertEqual(set(course_keys), set(cached_data.keys()))

        with mock.patch('openedx.core.djangoapps.catalog.utils.get_edx_api_data') as mock_method:
            course_catalog_data_dict = utils.get_course_runs(self.user, course_keys)
            self.assertEqual(0, mock_method.call_count)
            self.assertEqual(expected_data, course_catalog_data_dict)











    # def test_get_course_run(self, _mock_cache, mock_get_catalog_data):
    #     course_run = factories.CourseRun()
    #     mock_get_catalog_data.return_value = course_run
    #
    #     data = utils.get_course_runs(self.user, [self.course_key])
    #
    #     self.assert_contract(mock_get_catalog_data.call_args)
    #     self.assertEqual(data, course_run)
    #
    # def test_course_run_unavailable(self, _mock_cache, mock_get_catalog_data):
    #     mock_get_catalog_data.return_value = []
    #
    #     data = utils.get_course_runs(self.user, [self.course_key])
    #
    #     self.assert_contract(mock_get_catalog_data.call_args)
    #     self.assertEqual(data, {})
    #
    # def test_cache_disabled(self, _mock_cache, mock_get_catalog_data):
    #     utils.get_course_runs(self.user, [self.course_key])
    #
    #     _, kwargs = self.assert_contract(mock_get_catalog_data.call_args)
    #
    #     self.assertIsNone(kwargs['cache_key'])
    #
    # def test_cache_enabled(self, _mock_cache, mock_get_catalog_data):
    #     catalog_integration = self.create_catalog_integration(cache_ttl=1)
    #
    #     utils.get_course_runs(self.user, [self.course_key])
    #
    #     _, kwargs = mock_get_catalog_data.call_args
    #
    #     self.assertEqual(kwargs['cache_key'], catalog_integration.CACHE_KEY)
    #
    # def test_config_missing(self, _mock_cache, _mock_get_catalog_data):
    #     """Verify that no errors occur if this method is called when catalog config is missing."""
    #     CatalogIntegration.objects.all().delete()
    #
    #     data = utils.get_course_runs(self.user, [self.course_key])
    #     self.assertEqual(data, {})


# @mock.patch(UTILS_MODULE + '.get_course_runs')
# @mock.patch(UTILS_MODULE + '.strip_querystring')
class TestGetRunMarketingUrl(TestCase):
    """
    Tests covering retrieval of course run marketing URLs.
    """
    def setUp(self):
        super(TestGetRunMarketingUrl, self).setUp()

        #self.course_key = CourseKey.from_string('foo/bar/baz')
        #self.course_key = 'foo/bar/baz'
        self.course_keys = ['foo1/bar1/baz1', 'foo2/bar2/baz2']
        self.user = UserFactory()

   def test_get_run_marketing_url(self):
        # course_run = factories.CourseRun()
        # mock_get_course_run.return_value = course_run
       
        #url = utils.get_run_marketing_urls(self.user, [self.course_key])
        # self.register_catalog_course_run_response(
        #     self.course_key,
        #     [{"key": self.course_key, "marketing_url": "https://marketing-url/course/course-title-foo-bar-baz"}]
        # )
        expected_data = {
            'foo1/bar1/baz1': 'https://marketing-url/course/course-title-foo1-bar1-baz1',
            'foo2/bar2/baz2': 'https://marketing-url/course/course-title-foo2-bar2-baz2'
        }
        with mock.patch('openedx.core.djangoapps.catalog.utils.get_course_runs', return_value={
            'foo1/bar1/baz1' : {
                'key': 'foo1/bar1/baz1',
                'marketing_url': 'https://marketing-url/course/course-title-foo1-bar1-baz1',
                'test_key': 'test_value1',
            },
            'foo2/bar2/baz2' : {
                'key': 'foo2/bar2/baz2',
                'marketing_url': 'https://marketing-url/course/course-title-foo2-bar2-baz2',
                'test_key': 'test_value2',
            }
        }):
            course_marketing_url_dict = utils.get_run_marketing_urls(self.user, self.course_keys)
            self.assertEqual(expected_data, course_marketing_url_dict)
            #print course_marketing_url_dict

        #self.assertEqual(url, course_run['marketing_url'])
            
    def test_marketing_url_catalog_course_not_found(self):
        expected_data = {
            'foo1/bar1/baz1': 'https://marketing-url/course/course-title-foo1-bar1-baz1'
        }
        with mock.patch('openedx.core.djangoapps.catalog.utils.get_course_runs', return_value={
            'foo1/bar1/baz1' : {
                'key': 'foo1/bar1/baz1',
                'marketing_url': 'https://marketing-url/course/course-title-foo1-bar1-baz1',
                'test_key': 'test_value1',
            }
        }):
            course_marketing_url_dict = utils.get_run_marketing_urls(self.user, self.course_keys)
            self.assertEqual(expected_data, course_marketing_url_dict)

    def test_marketing_url_missing(self):
        expected_data = {
            'foo1/bar1/baz1': 'https://marketing-url/course/course-title-foo1-bar1-baz1',
            'foo2/bar2/baz2': None
        }
        with mock.patch('openedx.core.djangoapps.catalog.utils.get_course_runs', return_value={
            'foo1/bar1/baz1' : {
                'key': 'foo1/bar1/baz1',
                'marketing_url': 'https://marketing-url/course/course-title-foo1-bar1-baz1',
                'test_key': 'test_value1',
            },
            'foo2/bar2/baz2' : {
                'key': 'foo2/bar2/baz2',
                'marketing_url': None,
                'test_key': 'test_value2',
            }
        }):
            course_marketing_url_dict = utils.get_run_marketing_urls(self.user, self.course_keys)
            self.assertEqual(expected_data, course_marketing_url_dict)

    # def test_marketing_url_empty(self, mock_strip, mock_get_course_run):
    #     course_run = factories.CourseRun()
    #     course_run['marketing_url'] = ''
    #     mock_get_course_run.return_value = course_run
    #
    #     url = utils.get_run_marketing_urls(self.user, [self.course_key])
    #
    #     self.assertFalse(mock_strip.called)
    #     self.assertEqual(url, None)
    #
    # def test_marketing_url_missing(self, mock_strip, mock_get_course_run):
    #     mock_get_course_run.return_value = {}
    #
    #     url = utils.get_run_marketing_urls(self.user, [self.course_key])
    #
    #     self.assertFalse(mock_strip.called)
    #     self.assertEqual(url, None)


        url = utils.get_run_marketing_urls(self.user, [self.course_key])

        self.assertFalse(mock_strip.called)
        self.assertEqual(url, None)


@ddt.ddt
class TestStripQuerystring(TestCase):
    """Tests covering querystring stripping."""
    bare_url = 'https://www.example.com/path'

    @ddt.data(
        bare_url,
        bare_url + '?foo=bar&baz=qux',
    )
    def test_strip_querystring(self, url):
        self.assertEqual(utils.strip_querystring(url), self.bare_url)

"""Helper functions for working with the catalog service."""
import logging
from urlparse import urlparse

from django.conf import settings
from django.core.cache import cache
from edx_rest_api_client.client import EdxRestApiClient
from opaque_keys.edx.keys import CourseKey
from openedx.core.djangoapps.api_admin.utils import course_discovery_api_client

from openedx.core.djangoapps.catalog.models import CatalogIntegration
from openedx.core.lib.edx_api_utils import get_edx_api_data
from openedx.core.lib.token_utils import JwtBuilder


log = logging.getLogger(__name__)


def create_catalog_api_client(user, catalog_integration):
    """Returns an API client which can be used to make catalog API requests."""
    scopes = ['email', 'profile']
    expires_in = settings.OAUTH_ID_TOKEN_EXPIRATION
    jwt = JwtBuilder(user).build_token(scopes, expires_in)

    return EdxRestApiClient(catalog_integration.internal_api_url, jwt=jwt)


def get_programs(user, uuid=None, type=None):  # pylint: disable=redefined-builtin
    """Retrieve marketable programs from the catalog service.

    Keyword Arguments:
        uuid (string): UUID identifying a specific program.
        type (string): Filter programs by type (e.g., "MicroMasters" will only return MicroMasters programs).

    Returns:
        list of dict, representing programs.
        dict, if a specific program is requested.
    """
    catalog_integration = CatalogIntegration.current()

    if catalog_integration.enabled:
        api = create_catalog_api_client(user, catalog_integration)

        cache_key = '{base}.programs{type}'.format(
            base=catalog_integration.CACHE_KEY,
            type='.' + type if type else ''
        )

        querystring = {
            'marketable': 1,
            'exclude_utm': 1,
        }
        if type:
            querystring['type'] = type

        return get_edx_api_data(
            catalog_integration,
            user,
            'programs',
            resource_id=uuid,
            cache_key=cache_key if catalog_integration.is_cache_enabled else None,
            api=api,
            querystring=querystring,
        )
    else:
        return []


def munge_catalog_program(catalog_program):
    """Make a program from the catalog service look like it came from the programs service.

    Catalog-based MicroMasters need to be displayed in the LMS. However, the LMS
    currently retrieves all program data from the soon-to-be-retired programs service.
    Consuming program data exclusively from the catalog service would have taken more time
    than we had prior to the MicroMasters launch. This is a functional middle ground
    introduced by ECOM-5460. Cleaning up this debt is tracked by ECOM-4418.

    Arguments:
        catalog_program (dict): The catalog service's representation of a program.

    Return:
        dict, imitating the schema used by the programs service.
    """
    return {
        'id': catalog_program['uuid'],
        'name': catalog_program['title'],
        'subtitle': catalog_program['subtitle'],
        'category': catalog_program['type'],
        'marketing_slug': catalog_program['marketing_slug'],
        'organizations': [
            {
                'display_name': organization['name'],
                'key': organization['key']
            } for organization in catalog_program['authoring_organizations']
        ],
        'course_codes': [
            {
                'display_name': course['title'],
                'key': course['key'],
                'organization': {
                    # The Programs schema only supports one organization here.
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
            } for course in catalog_program['courses']
        ],
        'banner_image_urls': {
            'w1440h480': catalog_program['banner_image']['large']['url'],
            'w726h242': catalog_program['banner_image']['medium']['url'],
            'w435h145': catalog_program['banner_image']['small']['url'],
            'w348h116': catalog_program['banner_image']['x-small']['url'],
        },
    }


def get_course_runs(user, course_keys=[]):  # pylint: disable=dangerous-default-value
    """Get a course run's data from the course catalog service.

    Arguments:
        course_keys (CourseKey): A list of Course key object identifying the run whose data we want.
        user (User): The user to authenticate as when making requests to the catalog service.

    Returns:
        dict, empty if no data could be retrieved.
    """
    course_catalog_data_dict = cache.get_many(course_keys)
    print "\n cached data \n"
    print course_catalog_data_dict
    print "\n asked keys \n"
    print course_keys
    if len(course_catalog_data_dict.keys()) != len(course_keys):
        found_keys = course_catalog_data_dict.keys()
        for key in course_keys:
            if key in found_keys:
                course_keys.remove(key)
        print "\n missed keys \n"
        print course_keys
        log.debug("Catalog data not found in cache against Course Keys: '{}'".format(",".join(course_keys)))

        catalog_integration = CatalogIntegration.current()
        if catalog_integration.enabled:
            print "\n catalog integration enabled \n"
            #api = create_catalog_api_client(user, catalog_integration)
            api = course_discovery_api_client(user)

            catalog_data = get_edx_api_data(
                catalog_integration,
                user,
                'course_runs',
                api=api,
                querystring={'keys': ",".join(course_keys), 'exclude_utm': 1},
            )
            print "\n catalog_data \n"
            print catalog_data
            if catalog_data:
                for catalog_course_run in catalog_data:
                    cache.set(catalog_course_run["key"], catalog_course_run, None)
                    course_catalog_data_dict[catalog_course_run["key"]] = catalog_course_run
    return course_catalog_data_dict
    # data = get_edx_api_data(
    #     catalog_integration,
    #     user,
    #     'course_runs',
    #     resource_id=unicode(course_key),
    #     cache_key=catalog_integration.CACHE_KEY if catalog_integration.is_cache_enabled else None,
    #     api=api,
    #     querystring={'exclude_utm': 1},
    # )

    # if catalog_integration.enabled:
    #     api = create_catalog_api_client(user, catalog_integration)
    #
    #     data = get_edx_api_data(
    #         catalog_integration,
    #         user,
    #         'course_runs',
    #         resource_id=unicode(course_key),
    #         cache_key=catalog_integration.CACHE_KEY if catalog_integration.is_cache_enabled else None,
    #         api=api,
    #     )
    #
    #     return data if data else {}
    # else:
    #     return {}


# def get_run_marketing_url(course_key, user):
#     """Get a course run's marketing URL from the course catalog service.
#
#     Arguments:
#         course_key (CourseKey): Course key object identifying the run whose marketing URL we want.
#         user (User): The user to authenticate as when making requests to the catalog service.
#
#     Returns:
#         string, the marketing URL, or None if no URL is available.
#     """
#     course_run = get_course_run(course_key, user)
#     marketing_url = course_run.get('marketing_url')
#
#     if marketing_url:
#         # This URL may include unwanted UTM parameters in the querystring.
#         # For more, see https://en.wikipedia.org/wiki/UTM_parameters.
#         return strip_querystring(marketing_url)
#     else:
#         return None

def get_run_marketing_urls(user, course_keys=[]):  # pylint: disable=dangerous-default-value
    """Get a course run's marketing URL from the course catalog service.

    Arguments:
        course_key (CourseKey): Course key object identifying the run whose marketing URL we want.
        user (User): The user to authenticate as when making requests to the catalog service.

    Returns:
        string, the marketing URL, or None if no URL is available.
    """
    # from merging
    # course_run = get_course_run(course_key, user)
    # return course_run.get('marketing_url')

    course_marketing_url_dict = {}
    print "\n in get run marketing urls \n"
    course_catalog_dict = get_course_runs(user, course_keys)
    print "\n course_catalog_dict \n"
    print course_catalog_dict
    if not course_catalog_dict:
        return course_marketing_url_dict

    for course_key in course_keys:
        if course_key in course_catalog_dict:
            marketing_url = course_catalog_dict[course_key].get('marketing_url')
            # if marketing_url:
            # This URL may include unwanted UTM parameters in the querystring.
            # For more, see https://en.wikipedia.org/wiki/UTM_parameters.
            # return strip_querystring(marketing_url)
            course_marketing_url_dict[course_key] = strip_querystring(marketing_url) if marketing_url else None

    print "\n course_marketing_url_dict \n"
    print course_marketing_url_dict
    return course_marketing_url_dict


def strip_querystring(url):
    """Strip the querystring from the provided URL.

    urlparse's ParseResult is a subclass of namedtuple. _replace is part of namedtuple's
    public API: https://docs.python.org/2/library/collections.html#collections.somenamedtuple._replace.
    The name starts with an underscore to prevent conflicts with field names.
    """
    return urlparse(url)._replace(query='').geturl()  # pylint: disable=no-member

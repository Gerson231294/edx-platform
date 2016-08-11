"""
Common Functions to Validate Configurations
"""


def validate_lms_config(settings):
    """
    Validates configurations for lms and raise ValueError if not valid
    """
    validate_common_config(settings)

    # validate feature based configurations here


def validate_cms_config(settings):
    """
    Validates configurations for lms and raise ValueError if not valid
    """
    validate_common_config(settings)

    # validate feature based configurations here


def validate_common_config(settings):
    """
    Validates configurations common for all apps
    """
    if not getattr(settings, 'LMS_ROOT_URL', None):
        raise ValueError("'LMS_ROOT_URL' is not defined.")

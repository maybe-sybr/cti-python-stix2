import re

from . import registry, version
from .base import _DomainObject
from .exceptions import DuplicateRegistrationError
from .properties import (
    ListProperty, ObjectReferenceProperty, ReferenceProperty, _validate_type,
)
from .utils import PREFIX_21_REGEX

# Properties ending in "_ref/s" need to be instances of specific types to meet
# our interpretation of section 3.1 of the spec
_VERSION_REF_TYPES_MAP = {
    "2.0": (ObjectReferenceProperty, ReferenceProperty),
    "2.1": (ReferenceProperty,),
}
# Any unknown versions are presumed to be newer than STIX 2.1 so we'll define
# this to enforce the 2.1 compatible type in such situations
_UNKNOWN_VERSION_REF_TYPES = _VERSION_REF_TYPES_MAP["2.1"]


def _validate_ref_props(props_map, version):
    """
    Validate that reference properties contain an expected type.

    Args:
        props_map (mapping): A mapping of STIX object properties to be checked.
        version (str): Which STIX2 version the properties must confirm to.

    Raises:
        ValueError: If the properties do not conform.
    """
    try:
        ref_prop_types = _VERSION_REF_TYPES_MAP[version]
    except KeyError:
        ref_prop_types = _UNKNOWN_VERSION_REF_TYPES

    for prop_name, prop_obj in props_map.items():
        tail = prop_name.rsplit("_", 1)[-1]
        if tail == "ref" and not isinstance(prop_obj, ref_prop_types):
            raise ValueError(
                f"{prop_name!r} is named like a reference property but is not "
                f"a subclass of any of {ref_prop_types!r}.",
            )
        elif tail == "refs" and not all((
            isinstance(prop_obj, ListProperty),
            isinstance(getattr(prop_obj, "contained", None), ref_prop_types),
        )):
            raise ValueError(
                f"{prop_name!r} is named like a reference list property but is not "
                f"a 'ListProperty' containing a subclass of any of {ref_prop_types!r}.",
            )


def _validate_props(props_map, version):
    """
    Validate that a map of properties is conformant for this STIX `version`.

    Args:
        props_map (mapping): A mapping of STIX object properties to be checked.
        version (str): Which STIX2 version the properties must confirm to.

    Raises:
        ValueError: If the properties do not conform.
    """
    # Confirm conformance with STIX 2.1+ requirements for property names
    if version != "2.0":
        for prop_name, prop_value in props_map.items():
            if not re.match(PREFIX_21_REGEX, prop_name):
                raise ValueError("Property name '%s' must begin with an alpha character." % prop_name)
    # Confirm conformance to section 3.1 regarding identifier properties
    _validate_ref_props(props_map, version)


def _register_object(new_type, version=version.DEFAULT_VERSION):
    """Register a custom STIX Object type.

    Args:
        new_type (class): A class to register in the Object map.
        version (str): Which STIX2 version to use. (e.g. "2.0", "2.1"). If
            None, use latest version.

    Raises:
        ValueError: If the class being registered wasn't created with the
            @CustomObject decorator.
        DuplicateRegistrationError: If the class has already been registered.

    """

    if not issubclass(new_type, _DomainObject):
        raise ValueError(
            "'%s' must be created with the @CustomObject decorator." %
            new_type.__name__,
        )

    if not version:
        version = version.DEFAULT_VERSION

    _validate_props(new_type._properties, version)

    OBJ_MAP = registry.STIX2_OBJ_MAPS[version]['objects']
    if new_type._type in OBJ_MAP.keys():
        raise DuplicateRegistrationError("STIX Object", new_type._type)
    OBJ_MAP[new_type._type] = new_type


def _register_marking(new_marking, version=version.DEFAULT_VERSION):
    """Register a custom STIX Marking Definition type.

    Args:
        new_marking (class): A class to register in the Marking map.
        version (str): Which STIX2 version to use. (e.g. "2.0", "2.1"). If
            None, use latest version.

    """
    if not version:
        version = version.DEFAULT_VERSION

    mark_type = new_marking._type
    _validate_type(mark_type, version)
    _validate_props(new_marking._properties, version)

    OBJ_MAP_MARKING = registry.STIX2_OBJ_MAPS[version]['markings']
    if mark_type in OBJ_MAP_MARKING.keys():
        raise DuplicateRegistrationError("STIX Marking", mark_type)
    OBJ_MAP_MARKING[mark_type] = new_marking


def _register_observable(new_observable, version=version.DEFAULT_VERSION):
    """Register a custom STIX Cyber Observable type.

    Args:
        new_observable (class): A class to register in the Observables map.
        version (str): Which STIX2 version to use. (e.g. "2.0", "2.1"). If
            None, use latest version.

    """
    if not version:
        version = version.DEFAULT_VERSION

    _validate_props(new_observable._properties, version)

    OBJ_MAP_OBSERVABLE = registry.STIX2_OBJ_MAPS[version]['observables']
    if new_observable._type in OBJ_MAP_OBSERVABLE.keys():
        raise DuplicateRegistrationError("Cyber Observable", new_observable._type)
    OBJ_MAP_OBSERVABLE[new_observable._type] = new_observable


def _register_extension(
    new_extension, version=version.DEFAULT_VERSION,
):
    """Register a custom extension to any STIX Object type.

    Args:
        new_extension (class): A class to register in the Extensions map.
        version (str): Which STIX2 version to use. (e.g. "2.0", "2.1").
            Defaults to the latest supported version.

    """
    ext_type = new_extension._type

    _validate_type(ext_type, version)
    if version == "2.1":
        if not (ext_type.endswith('-ext') or ext_type.startswith('extension-definition--')):
            raise ValueError(
                "Invalid extension type name '%s': must end with '-ext' or start with 'extension-definition--<UUID>'." %
                ext_type,
            )

    # Need to check both toplevel and nested properties
    combined_props = {
        **new_extension._properties,
        **getattr(new_extension, "_toplevel_properties", dict()),
    }
    if not combined_props:
        raise ValueError(
            "Invalid extension: must define at least one property: " +
            ext_type,
        )
    _validate_props(combined_props, version)

    EXT_MAP = registry.STIX2_OBJ_MAPS[version]['extensions']

    if ext_type in EXT_MAP:
        raise DuplicateRegistrationError("Extension", ext_type)
    EXT_MAP[ext_type] = new_extension

"""
Immich REST API client.

`ImmichClient` is composed from one mixin per API area (see `client/`), on top of
`ImmichClientBase`, which holds the credentials, the writable config override and
the authenticated `_request` helper. Import it from here, as before.
"""

from .client.base import ImmichClientBase
from .client.health import HealthApi
from .client.assets import AssetsApi
from .client.search import SearchApi
from .client.albums import AlbumsApi
from .client.video import VideoApi
from .client.thumbnails import ThumbnailsApi
from .client.sharing import SharingApi
from .client.people import PeopleApi
from .client.edits import EditsApi
from .client.trash import TrashApi
from .client.duplicates import DuplicatesApi
from .client.tags import TagsApi
from .client.upload import UploadApi
from .client.maps import MapsApi
from .client.memories import MemoriesApi
from .client.timeline import TimelineApi
from .client.stacks import StacksApi
from .client.partners import PartnersApi
from .client.activities import ActivitiesApi
from .client.download import DownloadApi


class ImmichClient(
    HealthApi,
    AssetsApi,
    SearchApi,
    AlbumsApi,
    VideoApi,
    ThumbnailsApi,
    SharingApi,
    PeopleApi,
    EditsApi,
    TrashApi,
    DuplicatesApi,
    TagsApi,
    UploadApi,
    MapsApi,
    MemoriesApi,
    TimelineApi,
    StacksApi,
    PartnersApi,
    ActivitiesApi,
    DownloadApi,
    ImmichClientBase,
):
    """Async HTTP client for the Immich REST API."""


__all__ = ["ImmichClient"]

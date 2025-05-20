```html
<!-- static\index.html -->

<!DOCTYPE html>
<html>
<head>
    <title>Document Processing GUI</title>
</head>
<body>
    <h1>Document Processing GUI</h1>
    <button onclick="runScript()">Run Script</button>
    
    <!-- New input field and button for checking new documents -->
    <input type="text" id="collectionName" placeholder="Enter collection name">
    <button onclick="checkCollection()">Ingest</button>
    
    <pre id="log"></pre>

    <script>
        function runScript() {
            fetch('/run-script/', { method: 'POST' })
                .then(response => response.json())
                .then(data => console.log(data));
        }

        function checkCollection() {
            const collection = document.getElementById('collectionName').value.trim();
            if (collection === '') {
                alert('Please enter a collection name.');
                return;
            }

            fetch(`/run-script/${encodeURIComponent(collection)}`, { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    console.log(data);
                    alert(data.message);
                })
                .catch(error => console.error('Error:', error));
        }

        function fetchLogs() {
            fetch('/logs/')
                .then(response => response.text())
                .then(data => {
                    document.getElementById('log').innerText = data;
                });
        }

        setInterval(fetchLogs, 1000);
    </script>
</body>
</html>

```

```python
# Modified_Unstructured_Library_Files\file_download.py

import copy
import errno
import fnmatch
import inspect
import io
import json
import os
import re
import shutil
import stat
import tempfile
import time
import uuid
import warnings
from contextlib import contextmanager
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any, BinaryIO, Dict, Generator, Literal, Optional, Tuple, Union
from urllib.parse import quote, urlparse

import requests

from huggingface_hub import constants

from . import __version__  # noqa: F401 # for backward compatibility
from .constants import (
    DEFAULT_ETAG_TIMEOUT,
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_REVISION,
    DOWNLOAD_CHUNK_SIZE,
    ENDPOINT,
    HF_HUB_CACHE,
    HF_HUB_DISABLE_SYMLINKS_WARNING,
    HF_HUB_DOWNLOAD_TIMEOUT,
    HF_HUB_ENABLE_HF_TRANSFER,
    HF_HUB_ETAG_TIMEOUT,
    HF_TRANSFER_CONCURRENCY,
    HUGGINGFACE_CO_URL_TEMPLATE,
    HUGGINGFACE_HEADER_X_LINKED_ETAG,
    HUGGINGFACE_HEADER_X_LINKED_SIZE,
    HUGGINGFACE_HEADER_X_REPO_COMMIT,
    HUGGINGFACE_HUB_CACHE,  # noqa: F401 # for backward compatibility
    REPO_ID_SEPARATOR,
    REPO_TYPES,
    REPO_TYPES_URL_PREFIXES,
)
from .utils import (
    EntryNotFoundError,
    FileMetadataError,
    GatedRepoError,
    LocalEntryNotFoundError,
    OfflineModeIsEnabled,
    RepositoryNotFoundError,
    RevisionNotFoundError,
    SoftTemporaryDirectory,
    WeakFileLock,
    build_hf_headers,
    get_fastai_version,  # noqa: F401 # for backward compatibility
    get_fastcore_version,  # noqa: F401 # for backward compatibility
    get_graphviz_version,  # noqa: F401 # for backward compatibility
    get_jinja_version,  # noqa: F401 # for backward compatibility
    get_pydot_version,  # noqa: F401 # for backward compatibility
    get_session,
    get_tf_version,  # noqa: F401 # for backward compatibility
    get_torch_version,  # noqa: F401 # for backward compatibility
    hf_raise_for_status,
    is_fastai_available,  # noqa: F401 # for backward compatibility
    is_fastcore_available,  # noqa: F401 # for backward compatibility
    is_graphviz_available,  # noqa: F401 # for backward compatibility
    is_jinja_available,  # noqa: F401 # for backward compatibility
    is_pydot_available,  # noqa: F401 # for backward compatibility
    is_tf_available,  # noqa: F401 # for backward compatibility
    is_torch_available,  # noqa: F401 # for backward compatibility
    logging,
    reset_sessions,
    tqdm,
    validate_hf_hub_args,
)
from .utils._runtime import _PY_VERSION  # noqa: F401 # for backward compatibility
from .utils._typing import HTTP_METHOD_T
from .utils.insecure_hashlib import sha256


logger = logging.get_logger(__name__)

# Regex to get filename from a "Content-Disposition" header for CDN-served files
HEADER_FILENAME_PATTERN = re.compile(r'filename="(?P<filename>.*?)";')


_are_symlinks_supported_in_dir: Dict[str, bool] = {}


def are_symlinks_supported(cache_dir: Union[str, Path, None] = None) -> bool:
    """Return whether the symlinks are supported on the machine.

    Since symlinks support can change depending on the mounted disk, we need to check
    on the precise cache folder. By default, the default HF cache directory is checked.

    Args:
        cache_dir (`str`, `Path`, *optional*):
            Path to the folder where cached files are stored.

    Returns: [bool] Whether symlinks are supported in the directory.
    """
    # Defaults to HF cache
    if cache_dir is None:
        cache_dir = HF_HUB_CACHE
    cache_dir = str(Path(cache_dir).expanduser().resolve())  # make it unique

    # Check symlink compatibility only once (per cache directory) at first time use
    if cache_dir not in _are_symlinks_supported_in_dir:
        _are_symlinks_supported_in_dir[cache_dir] = True

        os.makedirs(cache_dir, exist_ok=True)
        with SoftTemporaryDirectory(dir=cache_dir) as tmpdir:
            src_path = Path(tmpdir) / "dummy_file_src"
            src_path.touch()
            dst_path = Path(tmpdir) / "dummy_file_dst"

            # Relative source path as in `_create_symlink``
            relative_src = os.path.relpath(src_path, start=os.path.dirname(dst_path))
            try:
                os.symlink(relative_src, dst_path)
            except OSError:
                # Likely running on Windows
                _are_symlinks_supported_in_dir[cache_dir] = False

                if not HF_HUB_DISABLE_SYMLINKS_WARNING:
                    message = (
                        "`huggingface_hub` cache-system uses symlinks by default to"
                        " efficiently store duplicated files but your machine does not"
                        f" support them in {cache_dir}. Caching files will still work"
                        " but in a degraded version that might require more space on"
                        " your disk. This warning can be disabled by setting the"
                        " `HF_HUB_DISABLE_SYMLINKS_WARNING` environment variable. For"
                        " more details, see"
                        " https://huggingface.co/docs/huggingface_hub/how-to-cache#limitations."
                    )
                    if os.name == "nt":
                        message += (
                            "\nTo support symlinks on Windows, you either need to"
                            " activate Developer Mode or to run Python as an"
                            " administrator. In order to see activate developer mode,"
                            " see this article:"
                            " https://docs.microsoft.com/en-us/windows/apps/get-started/enable-your-device-for-development"
                        )
                    warnings.warn(message)

    return _are_symlinks_supported_in_dir[cache_dir]


# Return value when trying to load a file from cache but the file does not exist in the distant repo.
_CACHED_NO_EXIST = object()
_CACHED_NO_EXIST_T = Any
REGEX_COMMIT_HASH = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class HfFileMetadata:
    """Data structure containing information about a file versioned on the Hub.

    Returned by [`get_hf_file_metadata`] based on a URL.

    Args:
        commit_hash (`str`, *optional*):
            The commit_hash related to the file.
        etag (`str`, *optional*):
            Etag of the file on the server.
        location (`str`):
            Location where to download the file. Can be a Hub url or not (CDN).
        size (`size`):
            Size of the file. In case of an LFS file, contains the size of the actual
            LFS file, not the pointer.
    """

    commit_hash: Optional[str]
    etag: Optional[str]
    location: str
    size: Optional[int]


@validate_hf_hub_args
def hf_hub_url(
    repo_id: str,
    filename: str,
    *,
    subfolder: Optional[str] = None,
    repo_type: Optional[str] = None,
    revision: Optional[str] = None,
    endpoint: Optional[str] = None,
) -> str:
    """Construct the URL of a file from the given information.

    The resolved address can either be a huggingface.co-hosted url, or a link to
    Cloudfront (a Content Delivery Network, or CDN) for large files which are
    more than a few MBs.

    Args:
        repo_id (`str`):
            A namespace (user or an organization) name and a repo name separated
            by a `/`.
        filename (`str`):
            The name of the file in the repo.
        subfolder (`str`, *optional*):
            An optional value corresponding to a folder inside the repo.
        repo_type (`str`, *optional*):
            Set to `"dataset"` or `"space"` if downloading from a dataset or space,
            `None` or `"model"` if downloading from a model. Default is `None`.
        revision (`str`, *optional*):
            An optional Git revision id which can be a branch name, a tag, or a
            commit hash.

    Example:

    ```python
    >>> from huggingface_hub import hf_hub_url

    >>> hf_hub_url(
    ...     repo_id="julien-c/EsperBERTo-small", filename="pytorch_model.bin"
    ... )
    'https://huggingface.co/julien-c/EsperBERTo-small/resolve/main/pytorch_model.bin'
    ```

    <Tip>

    Notes:

        Cloudfront is replicated over the globe so downloads are way faster for
        the end user (and it also lowers our bandwidth costs).

        Cloudfront aggressively caches files by default (default TTL is 24
        hours), however this is not an issue here because we implement a
        git-based versioning system on huggingface.co, which means that we store
        the files on S3/Cloudfront in a content-addressable way (i.e., the file
        name is its hash). Using content-addressable filenames means cache can't
        ever be stale.

        In terms of client-side caching from this library, we base our caching
        on the objects' entity tag (`ETag`), which is an identifier of a
        specific version of a resource [1]_. An object's ETag is: its git-sha1
        if stored in git, or its sha256 if stored in git-lfs.

    </Tip>

    References:

    -  [1] https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/ETag
    """
    if subfolder == "":
        subfolder = None
    if subfolder is not None:
        filename = f"{subfolder}/{filename}"

    if repo_type not in REPO_TYPES:
        raise ValueError("Invalid repo type")

    if repo_type in REPO_TYPES_URL_PREFIXES:
        repo_id = REPO_TYPES_URL_PREFIXES[repo_type] + repo_id

    if revision is None:
        revision = DEFAULT_REVISION
    url = HUGGINGFACE_CO_URL_TEMPLATE.format(
        repo_id=repo_id, revision=quote(revision, safe=""), filename=quote(filename)
    )
    # Update endpoint if provided
    if endpoint is not None and url.startswith(ENDPOINT):
        url = endpoint + url[len(ENDPOINT) :]
    return url


def url_to_filename(url: str, etag: Optional[str] = None) -> str:
    """Generate a local filename from a url.

    Convert `url` into a hashed filename in a reproducible way. If `etag` is
    specified, append its hash to the url's, delimited by a period. If the url
    ends with .h5 (Keras HDF5 weights) adds '.h5' to the name so that TF 2.0 can
    identify it as a HDF5 file (see
    https://github.com/tensorflow/tensorflow/blob/00fad90125b18b80fe054de1055770cfb8fe4ba3/tensorflow/python/keras/engine/network.py#L1380)

    Args:
        url (`str`):
            The address to the file.
        etag (`str`, *optional*):
            The ETag of the file.

    Returns:
        The generated filename.
    """
    url_bytes = url.encode("utf-8")
    filename = sha256(url_bytes).hexdigest()

    if etag:
        etag_bytes = etag.encode("utf-8")
        filename += "." + sha256(etag_bytes).hexdigest()

    if url.endswith(".h5"):
        filename += ".h5"

    return filename


def filename_to_url(
    filename,
    cache_dir: Optional[str] = None,
    legacy_cache_layout: bool = False,
) -> Tuple[str, str]:
    """
    Return the url and etag (which may be `None`) stored for `filename`. Raise
    `EnvironmentError` if `filename` or its stored metadata do not exist.

    Args:
        filename (`str`):
            The name of the file
        cache_dir (`str`, *optional*):
            The cache directory to use instead of the default one.
        legacy_cache_layout (`bool`, *optional*, defaults to `False`):
            If `True`, uses the legacy file cache layout i.e. just call `hf_hub_url`
            then `cached_download`. This is deprecated as the new cache layout is
            more powerful.
    """
    if not legacy_cache_layout:
        warnings.warn(
            "`filename_to_url` uses the legacy way cache file layout",
            FutureWarning,
        )

    if cache_dir is None:
        cache_dir = HF_HUB_CACHE
    if isinstance(cache_dir, Path):
        cache_dir = str(cache_dir)

    cache_path = os.path.join(cache_dir, filename)
    if not os.path.exists(cache_path):
        raise EnvironmentError(f"file {cache_path} not found")

    meta_path = cache_path + ".json"
    if not os.path.exists(meta_path):
        raise EnvironmentError(f"file {meta_path} not found")

    with open(meta_path, encoding="utf-8") as meta_file:
        metadata = json.load(meta_file)
    url = metadata["url"]
    etag = metadata["etag"]

    return url, etag


def _request_wrapper(
    method: HTTP_METHOD_T, url: str, *, follow_relative_redirects: bool = False, **params
) -> requests.Response:
    """Wrapper around requests methods to follow relative redirects if `follow_relative_redirects=True` even when
    `allow_redirection=False`.

    Args:
        method (`str`):
            HTTP method, such as 'GET' or 'HEAD'.
        url (`str`):
            The URL of the resource to fetch.
        follow_relative_redirects (`bool`, *optional*, defaults to `False`)
            If True, relative redirection (redirection to the same site) will be resolved even when `allow_redirection`
            kwarg is set to False. Useful when we want to follow a redirection to a renamed repository without
            following redirection to a CDN.
        **params (`dict`, *optional*):
            Params to pass to `requests.request`.
    """
    # Recursively follow relative redirects
    if follow_relative_redirects:
        response = _request_wrapper(
            method=method,
            url=url,
            follow_relative_redirects=False,
            **params,
        )

        # If redirection, we redirect only relative paths.
        # This is useful in case of a renamed repository.
        if 300 <= response.status_code <= 399:
            parsed_target = urlparse(response.headers["Location"])
            if parsed_target.netloc == "":
                # This means it is a relative 'location' headers, as allowed by RFC 7231.
                # (e.g. '/path/to/resource' instead of 'http://domain.tld/path/to/resource')
                # We want to follow this relative redirect !
                #
                # Highly inspired by `resolve_redirects` from requests library.
                # See https://github.com/psf/requests/blob/main/requests/sessions.py#L159
                next_url = urlparse(url)._replace(path=parsed_target.path).geturl()
                return _request_wrapper(method=method, url=next_url, follow_relative_redirects=True, **params)
        return response

    # Perform request and return if status_code is not in the retry list.
    response = get_session().request(method=method, url=url, **params)
    hf_raise_for_status(response)
    return response


def http_get(
    url: str,
    temp_file: BinaryIO,
    *,
    proxies: Optional[Dict] = None,
    resume_size: float = 0,
    headers: Optional[Dict[str, str]] = None,
    expected_size: Optional[int] = None,
    displayed_filename: Optional[str] = None,
    _nb_retries: int = 5,
    _tqdm_bar: Optional[tqdm] = None,
) -> None:
    """
    Download a remote file. Do not gobble up errors, and will return errors tailored to the Hugging Face Hub.

    If ConnectionError (SSLError) or ReadTimeout happen while streaming data from the server, it is most likely a
    transient error (network outage?). We log a warning message and try to resume the download a few times before
    giving up. The method gives up after 5 attempts if no new data has being received from the server.

    Args:
        url (`str`):
            The URL of the file to download.
        temp_file (`BinaryIO`):
            The file-like object where to save the file.
        proxies (`dict`, *optional*):
            Dictionary mapping protocol to the URL of the proxy passed to `requests.request`.
        resume_size (`float`, *optional*):
            The number of bytes already downloaded. If set to 0 (default), the whole file is download. If set to a
            positive number, the download will resume at the given position.
        headers (`dict`, *optional*):
            Dictionary of HTTP Headers to send with the request.
        expected_size (`int`, *optional*):
            The expected size of the file to download. If set, the download will raise an error if the size of the
            received content is different from the expected one.
        displayed_filename (`str`, *optional*):
            The filename of the file that is being downloaded. Value is used only to display a nice progress bar. If
            not set, the filename is guessed from the URL or the `Content-Disposition` header.
    """
    hf_transfer = None
    if HF_HUB_ENABLE_HF_TRANSFER:
        if resume_size != 0:
            warnings.warn("'hf_transfer' does not support `resume_size`: falling back to regular download method")
        elif proxies is not None:
            warnings.warn("'hf_transfer' does not support `proxies`: falling back to regular download method")
        else:
            try:
                import hf_transfer  # type: ignore[no-redef]
            except ImportError:
                raise ValueError(
                    "Fast download using 'hf_transfer' is enabled"
                    " (HF_HUB_ENABLE_HF_TRANSFER=1) but 'hf_transfer' package is not"
                    " available in your environment. Try `pip install hf_transfer`."
                )

    initial_headers = headers
    headers = copy.deepcopy(headers) or {}
    if resume_size > 0:
        headers["Range"] = "bytes=%d-" % (resume_size,)

    r = _request_wrapper(
        method="GET", url=url, stream=True, proxies=proxies, headers=headers, timeout=HF_HUB_DOWNLOAD_TIMEOUT
    )
    hf_raise_for_status(r)
    content_length = r.headers.get("Content-Length")

    # NOTE: 'total' is the total number of bytes to download, not the number of bytes in the file.
    #       If the file is compressed, the number of bytes in the saved file will be higher than 'total'.
    total = resume_size + int(content_length) if content_length is not None else None

    if displayed_filename is None:
        displayed_filename = url
        content_disposition = r.headers.get("Content-Disposition")
        if content_disposition is not None:
            match = HEADER_FILENAME_PATTERN.search(content_disposition)
            if match is not None:
                # Means file is on CDN
                displayed_filename = match.groupdict()["filename"]

    # Truncate filename if too long to display
    if len(displayed_filename) > 40:
        displayed_filename = f"(…){displayed_filename[-40:]}"

    consistency_error_message = (
        f"Consistency check failed: file should be of size {expected_size} but has size"
        f" {{actual_size}} ({displayed_filename}).\nWe are sorry for the inconvenience. Please retry download and"
        " pass `force_download=True, resume_download=False` as argument.\nIf the issue persists, please let us"
        " know by opening an issue on https://github.com/huggingface/huggingface_hub."
    )

    # Stream file to buffer
    progress = _tqdm_bar
    if progress is None:
        progress = tqdm(
            unit="B",
            unit_scale=True,
            total=total,
            initial=resume_size,
            desc=displayed_filename,
            disable=True if (logger.getEffectiveLevel() == logging.NOTSET) else None,
            # ^ set `disable=None` rather than `disable=False` by default to disable progress bar when no TTY attached
            # see https://github.com/huggingface/huggingface_hub/pull/2000
        )

    if hf_transfer and total is not None and total > 5 * DOWNLOAD_CHUNK_SIZE:
        supports_callback = "callback" in inspect.signature(hf_transfer.download).parameters
        if not supports_callback:
            warnings.warn(
                "You are using an outdated version of `hf_transfer`. "
                "Consider upgrading to latest version to enable progress bars "
                "using `pip install -U hf_transfer`."
            )
        try:
            hf_transfer.download(
                url=url,
                filename=temp_file.name,
                max_files=HF_TRANSFER_CONCURRENCY,
                chunk_size=DOWNLOAD_CHUNK_SIZE,
                headers=headers,
                parallel_failures=3,
                max_retries=5,
                **({"callback": progress.update} if supports_callback else {}),
            )
        except Exception as e:
            raise RuntimeError(
                "An error occurred while downloading using `hf_transfer`. Consider"
                " disabling HF_HUB_ENABLE_HF_TRANSFER for better error handling."
            ) from e
        if not supports_callback:
            progress.update(total)
        if expected_size is not None and expected_size != os.path.getsize(temp_file.name):
            raise EnvironmentError(
                consistency_error_message.format(
                    actual_size=os.path.getsize(temp_file.name),
                )
            )
        return
    new_resume_size = resume_size
    try:
        for chunk in r.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
            if chunk:  # filter out keep-alive new chunks
                progress.update(len(chunk))
                temp_file.write(chunk)
                new_resume_size += len(chunk)
                # Some data has been downloaded from the server so we reset the number of retries.
                _nb_retries = 5
    except (requests.ConnectionError, requests.ReadTimeout) as e:
        # If ConnectionError (SSLError) or ReadTimeout happen while streaming data from the server, it is most likely
        # a transient error (network outage?). We log a warning message and try to resume the download a few times
        # before giving up. Tre retry mechanism is basic but should be enough in most cases.
        if _nb_retries <= 0:
            logger.warning("Error while downloading from %s: %s\nMax retries exceeded.", url, str(e))
            raise
        logger.warning("Error while downloading from %s: %s\nTrying to resume download...", url, str(e))
        time.sleep(1)
        reset_sessions()  # In case of SSLError it's best to reset the shared requests.Session objects
        return http_get(
            url=url,
            temp_file=temp_file,
            proxies=proxies,
            resume_size=new_resume_size,
            headers=initial_headers,
            expected_size=expected_size,
            _nb_retries=_nb_retries - 1,
            _tqdm_bar=_tqdm_bar,
        )

    progress.close()

    if expected_size is not None and expected_size != temp_file.tell():
        raise EnvironmentError(
            consistency_error_message.format(
                actual_size=temp_file.tell(),
            )
        )


@validate_hf_hub_args
def cached_download(
    url: str,
    *,
    library_name: Optional[str] = None,
    library_version: Optional[str] = None,
    cache_dir: Union[str, Path, None] = None,
    user_agent: Union[Dict, str, None] = None,
    force_download: bool = False,
    force_filename: Optional[str] = None,
    proxies: Optional[Dict] = None,
    etag_timeout: float = DEFAULT_ETAG_TIMEOUT,
    resume_download: bool = False,
    token: Union[bool, str, None] = None,
    local_files_only: bool = False,
    legacy_cache_layout: bool = False,
) -> str:
    
    # Determine the value for local_files_only based on the environment variable
    # with priority given to the environment variable if it exists.
    # Check if the 'LOCAL_FILES_ONLY' environment variable is set
    env_local_files_only = os.getenv("LOCAL_FILES_ONLY")
    if env_local_files_only is not None:
        # Convert the environment variable value from string to boolean
        local_files_only_env_bool = env_local_files_only.lower() in ["1", "true", "t", "yes", "y"]
        # Override the parameter value with the environment variable value
        local_files_only = local_files_only_env_bool




    """
    Download from a given URL and cache it if it's not already present in the
    local cache.

    Given a URL, this function looks for the corresponding file in the local
    cache. If it's not there, download it. Then return the path to the cached
    file.

    Will raise errors tailored to the Hugging Face Hub.

    Args:
        url (`str`):
            The path to the file to be downloaded.
        library_name (`str`, *optional*):
            The name of the library to which the object corresponds.
        library_version (`str`, *optional*):
            The version of the library.
        cache_dir (`str`, `Path`, *optional*):
            Path to the folder where cached files are stored.
        user_agent (`dict`, `str`, *optional*):
            The user-agent info in the form of a dictionary or a string.
        force_download (`bool`, *optional*, defaults to `False`):
            Whether the file should be downloaded even if it already exists in
            the local cache.
        force_filename (`str`, *optional*):
            Use this name instead of a generated file name.
        proxies (`dict`, *optional*):
            Dictionary mapping protocol to the URL of the proxy passed to
            `requests.request`.
        etag_timeout (`float`, *optional* defaults to `10`):
            When fetching ETag, how many seconds to wait for the server to send
            data before giving up which is passed to `requests.request`.
        resume_download (`bool`, *optional*, defaults to `False`):
            If `True`, resume a previously interrupted download.
        token (`bool`, `str`, *optional*):
            A token to be used for the download.
                - If `True`, the token is read from the HuggingFace config
                  folder.
                - If a string, it's used as the authentication token.
        local_files_only (`bool`, *optional*, defaults to `False`):
            If `True`, avoid downloading the file and return the path to the
            local cached file if it exists.
        legacy_cache_layout (`bool`, *optional*, defaults to `False`):
            Set this parameter to `True` to mention that you'd like to continue
            the old cache layout. Putting this to `True` manually will not raise
            any warning when using `cached_download`. We recommend using
            `hf_hub_download` to take advantage of the new cache.

    Returns:
        Local path (string) of file or if networking is off, last version of
        file cached on disk.

    <Tip>

    Raises the following errors:

        - [`EnvironmentError`](https://docs.python.org/3/library/exceptions.html#EnvironmentError)
          if `token=True` and the token cannot be found.
        - [`OSError`](https://docs.python.org/3/library/exceptions.html#OSError)
          if ETag cannot be determined.
        - [`ValueError`](https://docs.python.org/3/library/exceptions.html#ValueError)
          if some parameter value is invalid
        - [`~utils.RepositoryNotFoundError`]
          If the repository to download from cannot be found. This may be because it doesn't exist,
          or because it is set to `private` and you do not have access.
        - [`~utils.RevisionNotFoundError`]
          If the revision to download from cannot be found.
        - [`~utils.EntryNotFoundError`]
          If the file to download cannot be found.
        - [`~utils.LocalEntryNotFoundError`]
          If network is disabled or unavailable and file is not found in cache.

    </Tip>
    """
    if HF_HUB_ETAG_TIMEOUT != DEFAULT_ETAG_TIMEOUT:
        # Respect environment variable above user value
        etag_timeout = HF_HUB_ETAG_TIMEOUT

    if not legacy_cache_layout:
        warnings.warn(
            "'cached_download' is the legacy way to download files from the HF hub, please consider upgrading to"
            " 'hf_hub_download'",
            FutureWarning,
        )

    if cache_dir is None:
        cache_dir = HF_HUB_CACHE
    if isinstance(cache_dir, Path):
        cache_dir = str(cache_dir)

    os.makedirs(cache_dir, exist_ok=True)

    headers = build_hf_headers(
        token=token,
        library_name=library_name,
        library_version=library_version,
        user_agent=user_agent,
    )

    url_to_download = url
    etag = None
    expected_size = None
    if not local_files_only:
        try:
            # Temporary header: we want the full (decompressed) content size returned to be able to check the
            # downloaded file size
            headers["Accept-Encoding"] = "identity"
            r = _request_wrapper(
                method="HEAD",
                url=url,
                headers=headers,
                allow_redirects=False,
                follow_relative_redirects=True,
                proxies=proxies,
                timeout=etag_timeout,
            )
            headers.pop("Accept-Encoding", None)
            hf_raise_for_status(r)
            etag = r.headers.get(HUGGINGFACE_HEADER_X_LINKED_ETAG) or r.headers.get("ETag")
            # We favor a custom header indicating the etag of the linked resource, and
            # we fallback to the regular etag header.
            # If we don't have any of those, raise an error.
            if etag is None:
                raise FileMetadataError(
                    "Distant resource does not have an ETag, we won't be able to reliably ensure reproducibility."
                )
            # We get the expected size of the file, to check the download went well.
            expected_size = _int_or_none(r.headers.get("Content-Length"))
            # In case of a redirect, save an extra redirect on the request.get call,
            # and ensure we download the exact atomic version even if it changed
            # between the HEAD and the GET (unlikely, but hey).
            # Useful for lfs blobs that are stored on a CDN.
            if 300 <= r.status_code <= 399:
                url_to_download = r.headers["Location"]
                headers.pop("authorization", None)
                expected_size = None  # redirected -> can't know the expected size
        except (requests.exceptions.SSLError, requests.exceptions.ProxyError):
            # Actually raise for those subclasses of ConnectionError
            raise
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            OfflineModeIsEnabled,
        ):
            # Otherwise, our Internet connection is down.
            # etag is None
            pass

    filename = force_filename if force_filename is not None else url_to_filename(url, etag)

    # get cache path to put the file
    cache_path = os.path.join(cache_dir, filename)

    # etag is None == we don't have a connection or we passed local_files_only.
    # try to get the last downloaded one
    if etag is None:
        if os.path.exists(cache_path) and not force_download:
            return cache_path
        else:
            matching_files = [
                file
                for file in fnmatch.filter(os.listdir(cache_dir), filename.split(".")[0] + ".*")
                if not file.endswith(".json") and not file.endswith(".lock")
            ]
            if len(matching_files) > 0 and not force_download and force_filename is None:
                return os.path.join(cache_dir, matching_files[-1])
            else:
                # If files cannot be found and local_files_only=True,
                # the models might've been found if local_files_only=False
                # Notify the user about that
                if local_files_only:
                    raise LocalEntryNotFoundError(
                        "Cannot find the requested files in the cached path and"
                        " outgoing traffic has been disabled. To enable model look-ups"
                        " and downloads online, set 'local_files_only' to False."
                    )
                else:
                    raise LocalEntryNotFoundError(
                        "Connection error, and we cannot find the requested files in"
                        " the cached path. Please try again or make sure your Internet"
                        " connection is on."
                    )

    # From now on, etag is not None.
    if os.path.exists(cache_path) and not force_download:
        return cache_path

    # Prevent parallel downloads of the same file with a lock.
    lock_path = cache_path + ".lock"

    # Some Windows versions do not allow for paths longer than 255 characters.
    # In this case, we must specify it is an extended path by using the "\\?\" prefix.
    if os.name == "nt" and len(os.path.abspath(lock_path)) > 255:
        lock_path = "\\\\?\\" + os.path.abspath(lock_path)

    if os.name == "nt" and len(os.path.abspath(cache_path)) > 255:
        cache_path = "\\\\?\\" + os.path.abspath(cache_path)

    with WeakFileLock(lock_path):
        # If the download just completed while the lock was activated.
        if os.path.exists(cache_path) and not force_download:
            # Even if returning early like here, the lock will be released.
            return cache_path

        if resume_download:
            incomplete_path = cache_path + ".incomplete"

            @contextmanager
            def _resumable_file_manager() -> Generator[io.BufferedWriter, None, None]:
                with open(incomplete_path, "ab") as f:
                    yield f

            temp_file_manager = _resumable_file_manager
            if os.path.exists(incomplete_path):
                resume_size = os.stat(incomplete_path).st_size
            else:
                resume_size = 0
        else:
            temp_file_manager = partial(  # type: ignore
                tempfile.NamedTemporaryFile, mode="wb", dir=cache_dir, delete=False
            )
            resume_size = 0

        # Download to temporary file, then copy to cache dir once finished.
        # Otherwise you get corrupt cache entries if the download gets interrupted.
        with temp_file_manager() as temp_file:
            logger.info("downloading %s to %s", url, temp_file.name)

            http_get(
                url_to_download,
                temp_file,
                proxies=proxies,
                resume_size=resume_size,
                headers=headers,
                expected_size=expected_size,
            )

        logger.info("storing %s in cache at %s", url, cache_path)
        _chmod_and_replace(temp_file.name, cache_path)

        if force_filename is None:
            logger.info("creating metadata file for %s", cache_path)
            meta = {"url": url, "etag": etag}
            meta_path = cache_path + ".json"
            with open(meta_path, "w") as meta_file:
                json.dump(meta, meta_file)

    return cache_path


def _normalize_etag(etag: Optional[str]) -> Optional[str]:
    """Normalize ETag HTTP header, so it can be used to create nice filepaths.

    The HTTP spec allows two forms of ETag:
      ETag: W/"<etag_value>"
      ETag: "<etag_value>"

    For now, we only expect the second form from the server, but we want to be future-proof so we support both. For
    more context, see `TestNormalizeEtag` tests and https://github.com/huggingface/huggingface_hub/pull/1428.

    Args:
        etag (`str`, *optional*): HTTP header

    Returns:
        `str` or `None`: string that can be used as a nice directory name.
        Returns `None` if input is None.
    """
    if etag is None:
        return None
    return etag.lstrip("W/").strip('"')


def _create_relative_symlink(src: str, dst: str, new_blob: bool = False) -> None:
    """Alias method used in `transformers` conversion script."""
    return _create_symlink(src=src, dst=dst, new_blob=new_blob)


def _create_symlink(src: str, dst: str, new_blob: bool = False) -> None:
    """Create a symbolic link named dst pointing to src.

    By default, it will try to create a symlink using a relative path. Relative paths have 2 advantages:
    - If the cache_folder is moved (example: back-up on a shared drive), relative paths within the cache folder will
      not break.
    - Relative paths seems to be better handled on Windows. Issue was reported 3 times in less than a week when
      changing from relative to absolute paths. See https://github.com/huggingface/huggingface_hub/issues/1398,
      https://github.com/huggingface/diffusers/issues/2729 and https://github.com/huggingface/transformers/pull/22228.
      NOTE: The issue with absolute paths doesn't happen on admin mode.
    When creating a symlink from the cache to a local folder, it is possible that a relative path cannot be created.
    This happens when paths are not on the same volume. In that case, we use absolute paths.


    The result layout looks something like
        └── [ 128]  snapshots
            ├── [ 128]  2439f60ef33a0d46d85da5001d52aeda5b00ce9f
            │   ├── [  52]  README.md -> ../../../blobs/d7edf6bd2a681fb0175f7735299831ee1b22b812
            │   └── [  76]  pytorch_model.bin -> ../../../blobs/403450e234d65943a7dcf7e05a771ce3c92faa84dd07db4ac20f592037a1e4bd

    If symlinks cannot be created on this platform (most likely to be Windows), the workaround is to avoid symlinks by
    having the actual file in `dst`. If it is a new file (`new_blob=True`), we move it to `dst`. If it is not a new file
    (`new_blob=False`), we don't know if the blob file is already referenced elsewhere. To avoid breaking existing
    cache, the file is duplicated on the disk.

    In case symlinks are not supported, a warning message is displayed to the user once when loading `huggingface_hub`.
    The warning message can be disabled with the `DISABLE_SYMLINKS_WARNING` environment variable.
    """
    try:
        os.remove(dst)
    except OSError:
        pass

    abs_src = os.path.abspath(os.path.expanduser(src))
    abs_dst = os.path.abspath(os.path.expanduser(dst))
    abs_dst_folder = os.path.dirname(abs_dst)

    # Use relative_dst in priority
    try:
        relative_src = os.path.relpath(abs_src, abs_dst_folder)
    except ValueError:
        # Raised on Windows if src and dst are not on the same volume. This is the case when creating a symlink to a
        # local_dir instead of within the cache directory.
        # See https://docs.python.org/3/library/os.path.html#os.path.relpath
        relative_src = None

    try:
        commonpath = os.path.commonpath([abs_src, abs_dst])
        _support_symlinks = are_symlinks_supported(commonpath)
    except ValueError:
        # Raised if src and dst are not on the same volume. Symlinks will still work on Linux/Macos.
        # See https://docs.python.org/3/library/os.path.html#os.path.commonpath
        _support_symlinks = os.name != "nt"
    except PermissionError:
        # Permission error means src and dst are not in the same volume (e.g. destination path has been provided
        # by the user via `local_dir`. Let's test symlink support there)
        _support_symlinks = are_symlinks_supported(abs_dst_folder)
    except OSError as e:
        # OS error (errno=30) means that the commonpath is readonly on Linux/MacOS.
        if e.errno == errno.EROFS:
            _support_symlinks = are_symlinks_supported(abs_dst_folder)
        else:
            raise

    # Symlinks are supported => let's create a symlink.
    if _support_symlinks:
        src_rel_or_abs = relative_src or abs_src
        logger.debug(f"Creating pointer from {src_rel_or_abs} to {abs_dst}")
        try:
            os.symlink(src_rel_or_abs, abs_dst)
            return
        except FileExistsError:
            if os.path.islink(abs_dst) and os.path.realpath(abs_dst) == os.path.realpath(abs_src):
                # `abs_dst` already exists and is a symlink to the `abs_src` blob. It is most likely that the file has
                # been cached twice concurrently (exactly between `os.remove` and `os.symlink`). Do nothing.
                return
            else:
                # Very unlikely to happen. Means a file `dst` has been created exactly between `os.remove` and
                # `os.symlink` and is not a symlink to the `abs_src` blob file. Raise exception.
                raise
        except PermissionError:
            # Permission error means src and dst are not in the same volume (e.g. download to local dir) and symlink
            # is supported on both volumes but not between them. Let's just make a hard copy in that case.
            pass

    # Symlinks are not supported => let's move or copy the file.
    if new_blob:
        logger.info(f"Symlink not supported. Moving file from {abs_src} to {abs_dst}")
        shutil.move(abs_src, abs_dst)
    else:
        logger.info(f"Symlink not supported. Copying file from {abs_src} to {abs_dst}")
        shutil.copyfile(abs_src, abs_dst)


def _cache_commit_hash_for_specific_revision(storage_folder: str, revision: str, commit_hash: str) -> None:
    """Cache reference between a revision (tag, branch or truncated commit hash) and the corresponding commit hash.

    Does nothing if `revision` is already a proper `commit_hash` or reference is already cached.
    """
    if revision != commit_hash:
        ref_path = Path(storage_folder) / "refs" / revision
        ref_path.parent.mkdir(parents=True, exist_ok=True)
        if not ref_path.exists() or commit_hash != ref_path.read_text():
            # Update ref only if has been updated. Could cause useless error in case
            # repo is already cached and user doesn't have write access to cache folder.
            # See https://github.com/huggingface/huggingface_hub/issues/1216.
            ref_path.write_text(commit_hash)


@validate_hf_hub_args
def repo_folder_name(*, repo_id: str, repo_type: str) -> str:
    """Return a serialized version of a hf.co repo name and type, safe for disk storage
    as a single non-nested folder.

    Example: models--julien-c--EsperBERTo-small
    """
    # remove all `/` occurrences to correctly convert repo to directory name
    parts = [f"{repo_type}s", *repo_id.split("/")]
    return REPO_ID_SEPARATOR.join(parts)


def _check_disk_space(expected_size: int, target_dir: Union[str, Path]) -> None:
    """Check disk usage and log a warning if there is not enough disk space to download the file.

    Args:
        expected_size (`int`):
            The expected size of the file in bytes.
        target_dir (`str`):
            The directory where the file will be stored after downloading.
    """

    target_dir = Path(target_dir)  # format as `Path`
    for path in [target_dir] + list(target_dir.parents):  # first check target_dir, then each parents one by one
        try:
            target_dir_free = shutil.disk_usage(path).free
            if target_dir_free < expected_size:
                warnings.warn(
                    "Not enough free disk space to download the file. "
                    f"The expected file size is: {expected_size / 1e6:.2f} MB. "
                    f"The target location {target_dir} only has {target_dir_free / 1e6:.2f} MB free disk space."
                )
            return
        except OSError:  # raise on anything: file does not exist or space disk cannot be checked
            pass


@validate_hf_hub_args
def hf_hub_download(
    repo_id: str,
    filename: str,
    *,
    subfolder: Optional[str] = None,
    repo_type: Optional[str] = None,
    revision: Optional[str] = None,
    library_name: Optional[str] = None,
    library_version: Optional[str] = None,
    cache_dir: Union[str, Path, None] = None,
    local_dir: Union[str, Path, None] = None,
    local_dir_use_symlinks: Union[bool, Literal["auto"]] = "auto",
    user_agent: Union[Dict, str, None] = None,
    force_download: bool = False,
    force_filename: Optional[str] = None,
    proxies: Optional[Dict] = None,
    etag_timeout: float = DEFAULT_ETAG_TIMEOUT,
    resume_download: bool = False,
    token: Union[bool, str, None] = None,
    local_files_only: bool = False,
    headers: Optional[Dict[str, str]] = None,
    legacy_cache_layout: bool = False,
    endpoint: Optional[str] = None,
) -> str:
    # Determine the value for local_files_only based on the environment variable
    # Check if the 'LOCAL_FILES_ONLY' environment variable is set
    env_local_files_only = os.getenv("LOCAL_FILES_ONLY")
    # with priority given to the environment variable if it exists.
    if env_local_files_only is not None:
        # Convert the environment variable value from string to boolean
        local_files_only_env_bool = env_local_files_only.lower() in ["1", "true", "t", "yes", "y"]
        # Override the parameter value with the environment variable value
        local_files_only = local_files_only_env_bool



    """Download a given file if it's not already present in the local cache.

    The new cache file layout looks like this:
    - The cache directory contains one subfolder per repo_id (namespaced by repo type)
    - inside each repo folder:
        - refs is a list of the latest known revision => commit_hash pairs
        - blobs contains the actual file blobs (identified by their git-sha or sha256, depending on
          whether they're LFS files or not)
        - snapshots contains one subfolder per commit, each "commit" contains the subset of the files
          that have been resolved at that particular commit. Each filename is a symlink to the blob
          at that particular commit.

    If `local_dir` is provided, the file structure from the repo will be replicated in this location. You can configure
    how you want to move those files:
      - If `local_dir_use_symlinks="auto"` (default), files are downloaded and stored in the cache directory as blob
        files. Small files (<5MB) are duplicated in `local_dir` while a symlink is created for bigger files. The goal
        is to be able to manually edit and save small files without corrupting the cache while saving disk space for
        binary files. The 5MB threshold can be configured with the `HF_HUB_LOCAL_DIR_AUTO_SYMLINK_THRESHOLD`
        environment variable.
      - If `local_dir_use_symlinks=True`, files are downloaded, stored in the cache directory and symlinked in `local_dir`.
        This is optimal in term of disk usage but files must not be manually edited.
      - If `local_dir_use_symlinks=False` and the blob files exist in the cache directory, they are duplicated in the
        local dir. This means disk usage is not optimized.
      - Finally, if `local_dir_use_symlinks=False` and the blob files do not exist in the cache directory, then the
        files are downloaded and directly placed under `local_dir`. This means if you need to download them again later,
        they will be re-downloaded entirely.

    ```
    [  96]  .
    └── [ 160]  models--julien-c--EsperBERTo-small
        ├── [ 160]  blobs
        │   ├── [321M]  403450e234d65943a7dcf7e05a771ce3c92faa84dd07db4ac20f592037a1e4bd
        │   ├── [ 398]  7cb18dc9bafbfcf74629a4b760af1b160957a83e
        │   └── [1.4K]  d7edf6bd2a681fb0175f7735299831ee1b22b812
        ├── [  96]  refs
        │   └── [  40]  main
        └── [ 128]  snapshots
            ├── [ 128]  2439f60ef33a0d46d85da5001d52aeda5b00ce9f
            │   ├── [  52]  README.md -> ../../blobs/d7edf6bd2a681fb0175f7735299831ee1b22b812
            │   └── [  76]  pytorch_model.bin -> ../../blobs/403450e234d65943a7dcf7e05a771ce3c92faa84dd07db4ac20f592037a1e4bd
            └── [ 128]  bbc77c8132af1cc5cf678da3f1ddf2de43606d48
                ├── [  52]  README.md -> ../../blobs/7cb18dc9bafbfcf74629a4b760af1b160957a83e
                └── [  76]  pytorch_model.bin -> ../../blobs/403450e234d65943a7dcf7e05a771ce3c92faa84dd07db4ac20f592037a1e4bd
    ```

    Args:
        repo_id (`str`):
            A user or an organization name and a repo name separated by a `/`.
        filename (`str`):
            The name of the file in the repo.
        subfolder (`str`, *optional*):
            An optional value corresponding to a folder inside the model repo.
        repo_type (`str`, *optional*):
            Set to `"dataset"` or `"space"` if downloading from a dataset or space,
            `None` or `"model"` if downloading from a model. Default is `None`.
        revision (`str`, *optional*):
            An optional Git revision id which can be a branch name, a tag, or a
            commit hash.
        library_name (`str`, *optional*):
            The name of the library to which the object corresponds.
        library_version (`str`, *optional*):
            The version of the library.
        cache_dir (`str`, `Path`, *optional*):
            Path to the folder where cached files are stored.
        local_dir (`str` or `Path`, *optional*):
            If provided, the downloaded file will be placed under this directory, either as a symlink (default) or
            a regular file (see description for more details).
        local_dir_use_symlinks (`"auto"` or `bool`, defaults to `"auto"`):
            To be used with `local_dir`. If set to "auto", the cache directory will be used and the file will be either
            duplicated or symlinked to the local directory depending on its size. It set to `True`, a symlink will be
            created, no matter the file size. If set to `False`, the file will either be duplicated from cache (if
            already exists) or downloaded from the Hub and not cached. See description for more details.
        user_agent (`dict`, `str`, *optional*):
            The user-agent info in the form of a dictionary or a string.
        force_download (`bool`, *optional*, defaults to `False`):
            Whether the file should be downloaded even if it already exists in
            the local cache.
        proxies (`dict`, *optional*):
            Dictionary mapping protocol to the URL of the proxy passed to
            `requests.request`.
        etag_timeout (`float`, *optional*, defaults to `10`):
            When fetching ETag, how many seconds to wait for the server to send
            data before giving up which is passed to `requests.request`.
        resume_download (`bool`, *optional*, defaults to `False`):
            If `True`, resume a previously interrupted download.
        token (`str`, `bool`, *optional*):
            A token to be used for the download.
                - If `True`, the token is read from the HuggingFace config
                  folder.
                - If a string, it's used as the authentication token.
        local_files_only (`bool`, *optional*, defaults to `False`):
            If `True`, avoid downloading the file and return the path to the
            local cached file if it exists.
        headers (`dict`, *optional*):
            Additional headers to be sent with the request.
        legacy_cache_layout (`bool`, *optional*, defaults to `False`):
            If `True`, uses the legacy file cache layout i.e. just call [`hf_hub_url`]
            then `cached_download`. This is deprecated as the new cache layout is
            more powerful.

    Returns:
        Local path (string) of file or if networking is off, last version of
        file cached on disk.

    <Tip>

    Raises the following errors:

        - [`EnvironmentError`](https://docs.python.org/3/library/exceptions.html#EnvironmentError)
          if `token=True` and the token cannot be found.
        - [`OSError`](https://docs.python.org/3/library/exceptions.html#OSError)
          if ETag cannot be determined.
        - [`ValueError`](https://docs.python.org/3/library/exceptions.html#ValueError)
          if some parameter value is invalid
        - [`~utils.RepositoryNotFoundError`]
          If the repository to download from cannot be found. This may be because it doesn't exist,
          or because it is set to `private` and you do not have access.
        - [`~utils.RevisionNotFoundError`]
          If the revision to download from cannot be found.
        - [`~utils.EntryNotFoundError`]
          If the file to download cannot be found.
        - [`~utils.LocalEntryNotFoundError`]
          If network is disabled or unavailable and file is not found in cache.

    </Tip>
    """
    if HF_HUB_ETAG_TIMEOUT != DEFAULT_ETAG_TIMEOUT:
        # Respect environment variable above user value
        etag_timeout = HF_HUB_ETAG_TIMEOUT

    if force_filename is not None:
        warnings.warn(
            "The `force_filename` parameter is deprecated as a new caching system, "
            "which keeps the filenames as they are on the Hub, is now in place.",
            FutureWarning,
        )
        legacy_cache_layout = True

    if legacy_cache_layout:
        url = hf_hub_url(
            repo_id,
            filename,
            subfolder=subfolder,
            repo_type=repo_type,
            revision=revision,
            endpoint=endpoint,
        )

        return cached_download(
            url,
            library_name=library_name,
            library_version=library_version,
            cache_dir=cache_dir,
            user_agent=user_agent,
            force_download=force_download,
            force_filename=force_filename,
            proxies=proxies,
            etag_timeout=etag_timeout,
            resume_download=resume_download,
            token=token,
            local_files_only=local_files_only,
            legacy_cache_layout=legacy_cache_layout,
        )

    if cache_dir is None:
        cache_dir = HF_HUB_CACHE
    if revision is None:
        revision = DEFAULT_REVISION
    if isinstance(cache_dir, Path):
        cache_dir = str(cache_dir)
    if isinstance(local_dir, Path):
        local_dir = str(local_dir)
    locks_dir = os.path.join(cache_dir, ".locks")

    if subfolder == "":
        subfolder = None
    if subfolder is not None:
        # This is used to create a URL, and not a local path, hence the forward slash.
        filename = f"{subfolder}/{filename}"

    if repo_type is None:
        repo_type = "model"
    if repo_type not in REPO_TYPES:
        raise ValueError(f"Invalid repo type: {repo_type}. Accepted repo types are: {str(REPO_TYPES)}")

    storage_folder = os.path.join(cache_dir, repo_folder_name(repo_id=repo_id, repo_type=repo_type))

    # cross platform transcription of filename, to be used as a local file path.
    relative_filename = os.path.join(*filename.split("/"))
    if os.name == "nt":
        if relative_filename.startswith("..\\") or "\\..\\" in relative_filename:
            raise ValueError(
                f"Invalid filename: cannot handle filename '{relative_filename}' on Windows. Please ask the repository"
                " owner to rename this file."
            )

    # if user provides a commit_hash and they already have the file on disk,
    # shortcut everything.
    if REGEX_COMMIT_HASH.match(revision):
        pointer_path = _get_pointer_path(storage_folder, revision, relative_filename)
        if os.path.exists(pointer_path):
            if local_dir is not None:
                return _to_local_dir(pointer_path, local_dir, relative_filename, use_symlinks=local_dir_use_symlinks)
            return pointer_path

    url = hf_hub_url(repo_id, filename, repo_type=repo_type, revision=revision, endpoint=endpoint)

    headers = build_hf_headers(
        token=token,
        library_name=library_name,
        library_version=library_version,
        user_agent=user_agent,
        headers=headers,
    )

    url_to_download = url
    etag = None
    commit_hash = None
    expected_size = None
    head_call_error: Optional[Exception] = None
    if not local_files_only:
        try:
            try:
                metadata = get_hf_file_metadata(
                    url=url,
                    token=token,
                    proxies=proxies,
                    timeout=etag_timeout,
                    library_name=library_name,
                    library_version=library_version,
                    user_agent=user_agent,
                )
            except EntryNotFoundError as http_error:
                # Cache the non-existence of the file and raise
                commit_hash = http_error.response.headers.get(HUGGINGFACE_HEADER_X_REPO_COMMIT)
                if commit_hash is not None and not legacy_cache_layout:
                    no_exist_file_path = Path(storage_folder) / ".no_exist" / commit_hash / relative_filename
                    no_exist_file_path.parent.mkdir(parents=True, exist_ok=True)
                    no_exist_file_path.touch()
                    _cache_commit_hash_for_specific_revision(storage_folder, revision, commit_hash)
                raise

            # Commit hash must exist
            commit_hash = metadata.commit_hash
            if commit_hash is None:
                raise FileMetadataError(
                    "Distant resource does not seem to be on huggingface.co. It is possible that a configuration issue"
                    " prevents you from downloading resources from https://huggingface.co. Please check your firewall"
                    " and proxy settings and make sure your SSL certificates are updated."
                )

            # Etag must exist
            etag = metadata.etag
            # We favor a custom header indicating the etag of the linked resource, and
            # we fallback to the regular etag header.
            # If we don't have any of those, raise an error.
            if etag is None:
                raise FileMetadataError(
                    "Distant resource does not have an ETag, we won't be able to reliably ensure reproducibility."
                )

            # Expected (uncompressed) size
            expected_size = metadata.size

            # In case of a redirect, save an extra redirect on the request.get call,
            # and ensure we download the exact atomic version even if it changed
            # between the HEAD and the GET (unlikely, but hey).
            #
            # If url domain is different => we are downloading from a CDN => url is signed => don't send auth
            # If url domain is the same => redirect due to repo rename AND downloading a regular file => keep auth
            if metadata.location != url:
                url_to_download = metadata.location
                if urlparse(url).netloc != urlparse(url_to_download).netloc:
                    # Remove authorization header when downloading a LFS blob
                    headers.pop("authorization", None)
        except (requests.exceptions.SSLError, requests.exceptions.ProxyError):
            # Actually raise for those subclasses of ConnectionError
            raise
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            OfflineModeIsEnabled,
        ) as error:
            # Otherwise, our Internet connection is down.
            # etag is None
            head_call_error = error
            pass
        except (RevisionNotFoundError, EntryNotFoundError):
            # The repo was found but the revision or entry doesn't exist on the Hub (never existed or got deleted)
            raise
        except requests.HTTPError as error:
            # Multiple reasons for an http error:
            # - Repository is private and invalid/missing token sent
            # - Repository is gated and invalid/missing token sent
            # - Hub is down (error 500 or 504)
            # => let's switch to 'local_files_only=True' to check if the files are already cached.
            #    (if it's not the case, the error will be re-raised)
            head_call_error = error
            pass
        except FileMetadataError as error:
            # Multiple reasons for a FileMetadataError:
            # - Wrong network configuration (proxy, firewall, SSL certificates)
            # - Inconsistency on the Hub
            # => let's switch to 'local_files_only=True' to check if the files are already cached.
            #    (if it's not the case, the error will be re-raised)
            head_call_error = error
            pass

    assert (
        local_files_only or etag is not None or head_call_error is not None
    ), "etag is empty due to uncovered problems"

    # etag can be None for several reasons:
    # 1. we passed local_files_only.
    # 2. we don't have a connection
    # 3. Hub is down (HTTP 500 or 504)
    # 4. repo is not found -for example private or gated- and invalid/missing token sent
    # 5. Hub is blocked by a firewall or proxy is not set correctly.
    # => Try to get the last downloaded one from the specified revision.
    #
    # If the specified revision is a commit hash, look inside "snapshots".
    # If the specified revision is a branch or tag, look inside "refs".
    if etag is None:
        # In those cases, we cannot force download.
        if force_download:
            if local_files_only:
                raise ValueError("Cannot pass 'force_download=True' and 'local_files_only=True' at the same time.")
            elif isinstance(head_call_error, OfflineModeIsEnabled):
                raise ValueError(
                    "Cannot pass 'force_download=True' when offline mode is enabled."
                ) from head_call_error
            else:
                raise ValueError("Force download failed due to the above error.") from head_call_error

        # Try to get "commit_hash" from "revision"
        commit_hash = None
        if REGEX_COMMIT_HASH.match(revision):
            commit_hash = revision
        else:
            ref_path = os.path.join(storage_folder, "refs", revision)
            if os.path.isfile(ref_path):
                with open(ref_path) as f:
                    commit_hash = f.read()

        # Return pointer file if exists
        if commit_hash is not None:
            pointer_path = _get_pointer_path(storage_folder, commit_hash, relative_filename)
            if os.path.exists(pointer_path):
                if local_dir is not None:
                    return _to_local_dir(
                        pointer_path, local_dir, relative_filename, use_symlinks=local_dir_use_symlinks
                    )
                return pointer_path

        # If we couldn't find an appropriate file on disk, raise an error.
        # If files cannot be found and local_files_only=True,
        # the models might've been found if local_files_only=False
        # Notify the user about that
        if local_files_only:
            raise LocalEntryNotFoundError(
                "Cannot find the requested files in the disk cache and outgoing traffic has been disabled. To enable"
                " hf.co look-ups and downloads online, set 'local_files_only' to False."
            )
        elif isinstance(head_call_error, RepositoryNotFoundError) or isinstance(head_call_error, GatedRepoError):
            # Repo not found or gated => let's raise the actual error
            raise head_call_error
        else:
            # Otherwise: most likely a connection issue or Hub downtime => let's warn the user
            raise LocalEntryNotFoundError(
                "An error happened while trying to locate the file on the Hub and we cannot find the requested files"
                " in the local cache. Please check your connection and try again or make sure your Internet connection"
                " is on."
            ) from head_call_error

    # From now on, etag and commit_hash are not None.
    assert etag is not None, "etag must have been retrieved from server"
    assert commit_hash is not None, "commit_hash must have been retrieved from server"
    blob_path = os.path.join(storage_folder, "blobs", etag)
    pointer_path = _get_pointer_path(storage_folder, commit_hash, relative_filename)

    os.makedirs(os.path.dirname(blob_path), exist_ok=True)
    os.makedirs(os.path.dirname(pointer_path), exist_ok=True)
    # if passed revision is not identical to commit_hash
    # then revision has to be a branch name or tag name.
    # In that case store a ref.
    _cache_commit_hash_for_specific_revision(storage_folder, revision, commit_hash)

    if os.path.exists(pointer_path) and not force_download:
        if local_dir is not None:
            return _to_local_dir(pointer_path, local_dir, relative_filename, use_symlinks=local_dir_use_symlinks)
        return pointer_path

    if os.path.exists(blob_path) and not force_download:
        # we have the blob already, but not the pointer
        if local_dir is not None:  # to local dir
            return _to_local_dir(blob_path, local_dir, relative_filename, use_symlinks=local_dir_use_symlinks)
        else:  # or in snapshot cache
            _create_symlink(blob_path, pointer_path, new_blob=False)
            return pointer_path

    # Prevent parallel downloads of the same file with a lock.
    # etag could be duplicated across repos,
    lock_path = os.path.join(locks_dir, repo_folder_name(repo_id=repo_id, repo_type=repo_type), f"{etag}.lock")

    # Some Windows versions do not allow for paths longer than 255 characters.
    # In this case, we must specify it is an extended path by using the "\\?\" prefix.
    if os.name == "nt" and len(os.path.abspath(lock_path)) > 255:
        lock_path = "\\\\?\\" + os.path.abspath(lock_path)

    if os.name == "nt" and len(os.path.abspath(blob_path)) > 255:
        blob_path = "\\\\?\\" + os.path.abspath(blob_path)

    Path(lock_path).parent.mkdir(parents=True, exist_ok=True)
    with WeakFileLock(lock_path):
        # If the download just completed while the lock was activated.
        if os.path.exists(pointer_path) and not force_download:
            # Even if returning early like here, the lock will be released.
            if local_dir is not None:
                return _to_local_dir(pointer_path, local_dir, relative_filename, use_symlinks=local_dir_use_symlinks)
            return pointer_path

        if resume_download:
            incomplete_path = blob_path + ".incomplete"

            @contextmanager
            def _resumable_file_manager() -> Generator[io.BufferedWriter, None, None]:
                with open(incomplete_path, "ab") as f:
                    yield f

            temp_file_manager = _resumable_file_manager
            if os.path.exists(incomplete_path):
                resume_size = os.stat(incomplete_path).st_size
            else:
                resume_size = 0
        else:
            temp_file_manager = partial(  # type: ignore
                tempfile.NamedTemporaryFile, mode="wb", dir=cache_dir, delete=False
            )
            resume_size = 0

        # Download to temporary file, then copy to cache dir once finished.
        # Otherwise you get corrupt cache entries if the download gets interrupted.
        with temp_file_manager() as temp_file:
            logger.info("downloading %s to %s", url, temp_file.name)

            if expected_size is not None:  # might be None if HTTP header not set correctly
                # Check tmp path
                _check_disk_space(expected_size, os.path.dirname(temp_file.name))

                # Check destination
                _check_disk_space(expected_size, os.path.dirname(blob_path))
                if local_dir is not None:
                    _check_disk_space(expected_size, local_dir)

            http_get(
                url_to_download,
                temp_file,
                proxies=proxies,
                resume_size=resume_size,
                headers=headers,
                expected_size=expected_size,
                displayed_filename=filename,
            )

        if local_dir is None:
            logger.debug(f"Storing {url} in cache at {blob_path}")
            _chmod_and_replace(temp_file.name, blob_path)
            _create_symlink(blob_path, pointer_path, new_blob=True)
        else:
            local_dir_filepath = os.path.join(local_dir, relative_filename)
            os.makedirs(os.path.dirname(local_dir_filepath), exist_ok=True)

            # If "auto" (default) copy-paste small files to ease manual editing but symlink big files to save disk
            # In both cases, blob file is cached.
            is_big_file = os.stat(temp_file.name).st_size > constants.HF_HUB_LOCAL_DIR_AUTO_SYMLINK_THRESHOLD
            if local_dir_use_symlinks is True or (local_dir_use_symlinks == "auto" and is_big_file):
                logger.debug(f"Storing {url} in cache at {blob_path}")
                _chmod_and_replace(temp_file.name, blob_path)
                logger.debug("Create symlink to local dir")
                _create_symlink(blob_path, local_dir_filepath, new_blob=False)
            elif local_dir_use_symlinks == "auto" and not is_big_file:
                logger.debug(f"Storing {url} in cache at {blob_path}")
                _chmod_and_replace(temp_file.name, blob_path)
                logger.debug("Duplicate in local dir (small file and use_symlink set to 'auto')")
                shutil.copyfile(blob_path, local_dir_filepath)
            else:
                logger.debug(f"Storing {url} in local_dir at {local_dir_filepath} (not cached).")
                _chmod_and_replace(temp_file.name, local_dir_filepath)
            pointer_path = local_dir_filepath  # for return value

    return pointer_path


@validate_hf_hub_args
def try_to_load_from_cache(
    repo_id: str,
    filename: str,
    cache_dir: Union[str, Path, None] = None,
    revision: Optional[str] = None,
    repo_type: Optional[str] = None,
) -> Union[str, _CACHED_NO_EXIST_T, None]:
    """
    Explores the cache to return the latest cached file for a given revision if found.

    This function will not raise any exception if the file in not cached.

    Args:
        cache_dir (`str` or `os.PathLike`):
            The folder where the cached files lie.
        repo_id (`str`):
            The ID of the repo on huggingface.co.
        filename (`str`):
            The filename to look for inside `repo_id`.
        revision (`str`, *optional*):
            The specific model version to use. Will default to `"main"` if it's not provided and no `commit_hash` is
            provided either.
        repo_type (`str`, *optional*):
            The type of the repository. Will default to `"model"`.

    Returns:
        `Optional[str]` or `_CACHED_NO_EXIST`:
            Will return `None` if the file was not cached. Otherwise:
            - The exact path to the cached file if it's found in the cache
            - A special value `_CACHED_NO_EXIST` if the file does not exist at the given commit hash and this fact was
              cached.

    Example:

    ```python
    from huggingface_hub import try_to_load_from_cache, _CACHED_NO_EXIST

    filepath = try_to_load_from_cache()
    if isinstance(filepath, str):
        # file exists and is cached
        ...
    elif filepath is _CACHED_NO_EXIST:
        # non-existence of file is cached
        ...
    else:
        # file is not cached
        ...
    ```
    """
    if revision is None:
        revision = "main"
    if repo_type is None:
        repo_type = "model"
    if repo_type not in REPO_TYPES:
        raise ValueError(f"Invalid repo type: {repo_type}. Accepted repo types are: {str(REPO_TYPES)}")
    if cache_dir is None:
        cache_dir = HF_HUB_CACHE

    object_id = repo_id.replace("/", "--")
    repo_cache = os.path.join(cache_dir, f"{repo_type}s--{object_id}")
    if not os.path.isdir(repo_cache):
        # No cache for this model
        return None

    refs_dir = os.path.join(repo_cache, "refs")
    snapshots_dir = os.path.join(repo_cache, "snapshots")
    no_exist_dir = os.path.join(repo_cache, ".no_exist")

    # Resolve refs (for instance to convert main to the associated commit sha)
    if os.path.isdir(refs_dir):
        revision_file = os.path.join(refs_dir, revision)
        if os.path.isfile(revision_file):
            with open(revision_file) as f:
                revision = f.read()

    # Check if file is cached as "no_exist"
    if os.path.isfile(os.path.join(no_exist_dir, revision, filename)):
        return _CACHED_NO_EXIST

    # Check if revision folder exists
    if not os.path.exists(snapshots_dir):
        return None
    cached_shas = os.listdir(snapshots_dir)
    if revision not in cached_shas:
        # No cache for this revision and we won't try to return a random revision
        return None

    # Check if file exists in cache
    cached_file = os.path.join(snapshots_dir, revision, filename)
    return cached_file if os.path.isfile(cached_file) else None


@validate_hf_hub_args
def get_hf_file_metadata(
    url: str,
    token: Union[bool, str, None] = None,
    proxies: Optional[Dict] = None,
    timeout: Optional[float] = DEFAULT_REQUEST_TIMEOUT,
    library_name: Optional[str] = None,
    library_version: Optional[str] = None,
    user_agent: Union[Dict, str, None] = None,
    headers: Optional[Dict[str, str]] = None,
) -> HfFileMetadata:
    """Fetch metadata of a file versioned on the Hub for a given url.

    Args:
        url (`str`):
            File url, for example returned by [`hf_hub_url`].
        token (`str` or `bool`, *optional*):
            A token to be used for the download.
                - If `True`, the token is read from the HuggingFace config
                  folder.
                - If `False` or `None`, no token is provided.
                - If a string, it's used as the authentication token.
        proxies (`dict`, *optional*):
            Dictionary mapping protocol to the URL of the proxy passed to
            `requests.request`.
        timeout (`float`, *optional*, defaults to 10):
            How many seconds to wait for the server to send metadata before giving up.
        library_name (`str`, *optional*):
            The name of the library to which the object corresponds.
        library_version (`str`, *optional*):
            The version of the library.
        user_agent (`dict`, `str`, *optional*):
            The user-agent info in the form of a dictionary or a string.
        headers (`dict`, *optional*):
            Additional headers to be sent with the request.

    Returns:
        A [`HfFileMetadata`] object containing metadata such as location, etag, size and
        commit_hash.
    """
    headers = build_hf_headers(
        token=token,
        library_name=library_name,
        library_version=library_version,
        user_agent=user_agent,
        headers=headers,
    )
    headers["Accept-Encoding"] = "identity"  # prevent any compression => we want to know the real size of the file

    # Retrieve metadata
    r = _request_wrapper(
        method="HEAD",
        url=url,
        headers=headers,
        allow_redirects=False,
        follow_relative_redirects=True,
        proxies=proxies,
        timeout=timeout,
    )
    hf_raise_for_status(r)

    # Return
    return HfFileMetadata(
        commit_hash=r.headers.get(HUGGINGFACE_HEADER_X_REPO_COMMIT),
        # We favor a custom header indicating the etag of the linked resource, and
        # we fallback to the regular etag header.
        etag=_normalize_etag(r.headers.get(HUGGINGFACE_HEADER_X_LINKED_ETAG) or r.headers.get("ETag")),
        # Either from response headers (if redirected) or defaults to request url
        # Do not use directly `url`, as `_request_wrapper` might have followed relative
        # redirects.
        location=r.headers.get("Location") or r.request.url,  # type: ignore
        size=_int_or_none(r.headers.get(HUGGINGFACE_HEADER_X_LINKED_SIZE) or r.headers.get("Content-Length")),
    )


def _int_or_none(value: Optional[str]) -> Optional[int]:
    try:
        return int(value)  # type: ignore
    except (TypeError, ValueError):
        return None


def _chmod_and_replace(src: str, dst: str) -> None:
    """Set correct permission before moving a blob from tmp directory to cache dir.

    Do not take into account the `umask` from the process as there is no convenient way
    to get it that is thread-safe.

    See:
    - About umask: https://docs.python.org/3/library/os.html#os.umask
    - Thread-safety: https://stackoverflow.com/a/70343066
    - About solution: https://github.com/huggingface/huggingface_hub/pull/1220#issuecomment-1326211591
    - Fix issue: https://github.com/huggingface/huggingface_hub/issues/1141
    - Fix issue: https://github.com/huggingface/huggingface_hub/issues/1215
    """
    # Get umask by creating a temporary file in the cached repo folder.
    tmp_file = Path(dst).parent.parent / f"tmp_{uuid.uuid4()}"
    try:
        tmp_file.touch()
        cache_dir_mode = Path(tmp_file).stat().st_mode
        os.chmod(src, stat.S_IMODE(cache_dir_mode))
    finally:
        tmp_file.unlink()

    shutil.move(src, dst)


def _get_pointer_path(storage_folder: str, revision: str, relative_filename: str) -> str:
    # Using `os.path.abspath` instead of `Path.resolve()` to avoid resolving symlinks
    snapshot_path = os.path.join(storage_folder, "snapshots")
    pointer_path = os.path.join(snapshot_path, revision, relative_filename)
    if Path(os.path.abspath(snapshot_path)) not in Path(os.path.abspath(pointer_path)).parents:
        raise ValueError(
            "Invalid pointer path: cannot create pointer path in snapshot folder if"
            f" `storage_folder='{storage_folder}'`, `revision='{revision}'` and"
            f" `relative_filename='{relative_filename}'`."
        )
    return pointer_path


def _to_local_dir(
    path: str, local_dir: str, relative_filename: str, use_symlinks: Union[bool, Literal["auto"]]
) -> str:
    """Place a file in a local dir (different than cache_dir).

    Either symlink to blob file in cache or duplicate file depending on `use_symlinks` and file size.
    """
    # Using `os.path.abspath` instead of `Path.resolve()` to avoid resolving symlinks
    local_dir_filepath = os.path.join(local_dir, relative_filename)
    if Path(os.path.abspath(local_dir)) not in Path(os.path.abspath(local_dir_filepath)).parents:
        raise ValueError(
            f"Cannot copy file '{relative_filename}' to local dir '{local_dir}': file would not be in the local"
            " directory."
        )

    os.makedirs(os.path.dirname(local_dir_filepath), exist_ok=True)
    real_blob_path = os.path.realpath(path)

    # If "auto" (default) copy-paste small files to ease manual editing but symlink big files to save disk
    if use_symlinks == "auto":
        use_symlinks = os.stat(real_blob_path).st_size > constants.HF_HUB_LOCAL_DIR_AUTO_SYMLINK_THRESHOLD

    if use_symlinks:
        _create_symlink(real_blob_path, local_dir_filepath, new_blob=False)
    else:
        shutil.copyfile(real_blob_path, local_dir_filepath)
    return local_dir_filepath

```

```python
# Modified_Unstructured_Library_Files\tables.py


# https://github.com/microsoft/table-transformer/blob/main/src/inference.py
# https://github.com/NielsRogge/Transformers-Tutorials/blob/master/Table%20Transformer/Using_Table_Transformer_for_table_detection_and_table_structure_recognition.ipynb
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Union

import cv2
import numpy as np
import torch
from PIL import Image
from transformers import DetrImageProcessor, TableTransformerForObjectDetection

from unstructured_inference.config import inference_config
from unstructured_inference.inference.layoutelement import table_cells_to_dataframe
from unstructured_inference.logger import logger
from unstructured_inference.models.table_postprocess import Rect
from unstructured_inference.models.unstructuredmodel import UnstructuredModel
from unstructured_inference.utils import pad_image_with_background_color

from . import table_postprocess as postprocess


class UnstructuredTableTransformerModel(UnstructuredModel):
    """Unstructured model wrapper for table-transformer."""

    def __init__(self):
        pass

    def predict(self, x: Image, ocr_tokens: Optional[List[Dict]] = None):
        """Predict table structure deferring to run_prediction with ocr tokens

        Note:
        `ocr_tokens` is a list of dictionaries representing OCR tokens,
        where each dictionary has the following format:
        {
            "bbox": [int, int, int, int],  # Bounding box coordinates of the token
            "block_num": int,  # Block number
            "line_num": int,   # Line number
            "span_num": int,   # Span number
            "text": str,  # Text content of the token
        }
        The bounding box coordinates should match the table structure.
        FIXME: refactor token data into a dataclass so we have clear expectations of the fields
        """
        super().predict(x)
        return self.run_prediction(x, ocr_tokens=ocr_tokens)

    def initialize(
        self,
        model: Union[str, Path, TableTransformerForObjectDetection] = None,
        device: Optional[str] = "cuda" if torch.cuda.is_available() else "cpu",
    ):
        """Loads the donut model using the specified parameters"""
        self.device = device
        self.feature_extractor = DetrImageProcessor()

        try:
            logger.info("Loading the table structure model ...")

            ######################
            # Apply the tracing to all events (including lines of code)
            # sys.settrace(my_trace_function)
            ####################

            self.model = TableTransformerForObjectDetection.from_pretrained(model)
            self.model.eval()

        except EnvironmentError:
            
        ######################
            # flush_trace_buffer()
            # sys.settrace(None)
        ######################
            logger.critical("Failed to initialize the model.")
            logger.critical("Ensure that the model is correct")
            raise ImportError(
                "Review the parameters to initialize a UnstructuredTableTransformerModel obj",
            )
        self.model.to(device)


    # def initialize(
    #     self, 
    #     model: Union[str, Path, TableTransformerForObjectDetection] = None, 
    #     device: Optional[str] = "cuda" if torch.cuda.is_available() else "cpu"):
    #     """Loads the table structure model using the specified parameters"""
    #     self.device = device
    #     self.feature_extractor = DetrImageProcessor()

    #     try:
    #         logger.info("Loading the table structure model ...")
    #         # Correctly handle a Path object or a directory as a model input
    #         if isinstance(model, Path):
    #             # Load model from a directory path
    #             self.model = TableTransformerForObjectDetection.from_pretrained(str(model), local_files_only=True)
    #         else:
    #             # Load model normally (from Hugging Face Hub or cached directory)
    #             self.model = TableTransformerForObjectDetection.from_pretrained(model)
    #         self.model.eval()
    #     except EnvironmentError as e:
    #         logger.critical("Failed to initialize the model.")
    #         logger.critical(f"Ensure that the model is correct: {str(e)}")
    #         raise ImportError("Review the parameters to initialize a UnstructuredTableTransformerModel object")
        
    #     self.model.to(self.device)





    def get_structure(
        self,
        x: Image,
        pad_for_structure_detection: int = inference_config.TABLE_IMAGE_BACKGROUND_PAD,
    ) -> dict:
        """get the table structure as a dictionary contaning different types of elements as
        key-value pairs; check table-transformer documentation for more information"""
        with torch.no_grad():
            logger.info(f"padding image by {pad_for_structure_detection} for structure detection")
            encoding = self.feature_extractor(
                pad_image_with_background_color(x, pad_for_structure_detection),
                return_tensors="pt",
            ).to(self.device)
            outputs_structure = self.model(**encoding)
            outputs_structure["pad_for_structure_detection"] = pad_for_structure_detection
            return outputs_structure

    def run_prediction(
        self,
        x: Image,
        pad_for_structure_detection: int = inference_config.TABLE_IMAGE_BACKGROUND_PAD,
        ocr_tokens: Optional[List[Dict]] = None,
        result_format: Optional[str] = "html",
    ):
        """Predict table structure"""
        outputs_structure = self.get_structure(x, pad_for_structure_detection)
        if ocr_tokens is None:
            raise ValueError("Cannot predict table structure with no OCR tokens")

        recognized_table = recognize(outputs_structure, x, tokens=ocr_tokens)
        if len(recognized_table) > 0:
            prediction = recognized_table[0]
        # NOTE(robinson) - This means that the table was not recognized
        else:
            return ""

        if result_format == "html":
            # Convert cells to HTML
            prediction = cells_to_html(prediction) or ""
        elif result_format == "dataframe":
            prediction = table_cells_to_dataframe(prediction)
        return prediction


tables_agent: UnstructuredTableTransformerModel = UnstructuredTableTransformerModel()


def load_agent():
    """Loads the Table agent as a global variable to ensure that we only load it once."""
    global tables_agent

    if not hasattr(tables_agent, "model"):
        logger.info("Loading the Table agent ...")
        tables_agent.initialize("microsoft/table-transformer-structure-recognition")

        # model_path = Path(r"G:\Torch_Models\microsoft\table-transformer-structure-recognition")
        # tables_agent.initialize(model_path)


    return


def get_class_map(data_type: str):
    """Defines class map dictionaries"""
    if data_type == "structure":
        class_map = {
            "table": 0,
            "table column": 1,
            "table row": 2,
            "table column header": 3,
            "table projected row header": 4,
            "table spanning cell": 5,
            "no object": 6,
        }
    elif data_type == "detection":
        class_map = {"table": 0, "table rotated": 1, "no object": 2}
    return class_map


structure_class_thresholds = {
    "table": inference_config.TT_TABLE_CONF,
    "table column": inference_config.TABLE_COLUMN_CONF,
    "table row": inference_config.TABLE_ROW_CONF,
    "table column header": inference_config.TABLE_COLUMN_HEADER_CONF,
    "table projected row header": inference_config.TABLE_PROJECTED_ROW_HEADER_CONF,
    "table spanning cell": inference_config.TABLE_SPANNING_CELL_CONF,
    # FIXME (yao) this parameter doesn't seem to be used at all in inference? Can we remove it
    "no object": 10,
}


def recognize(outputs: dict, img: Image, tokens: list):
    """Recognize table elements."""
    str_class_name2idx = get_class_map("structure")
    str_class_idx2name = {v: k for k, v in str_class_name2idx.items()}
    str_class_thresholds = structure_class_thresholds

    # Post-process detected objects, assign class labels
    objects = outputs_to_objects(outputs, img.size, str_class_idx2name)

    # Further process the detected objects so they correspond to a consistent table
    tables_structure = objects_to_structures(objects, tokens, str_class_thresholds)
    # Enumerate all table cells: grid cells and spanning cells
    return [structure_to_cells(structure, tokens)[0] for structure in tables_structure]


def outputs_to_objects(outputs, img_size, class_idx2name):
    """Output table element types."""
    m = outputs["logits"].softmax(-1).max(-1)
    pred_labels = list(m.indices.detach().cpu().numpy())[0]
    pred_scores = list(m.values.detach().cpu().numpy())[0]
    pred_bboxes = outputs["pred_boxes"].detach().cpu()[0]

    pad = outputs.get("pad_for_structure_detection", 0)
    scale_size = (img_size[0] + pad * 2, img_size[1] + pad * 2)
    pred_bboxes = [elem.tolist() for elem in rescale_bboxes(pred_bboxes, scale_size)]
    # unshift the padding; padding effectively shifted the bounding boxes of structures in the
    # original image with half of the total pad
    shift_size = pad

    objects = []
    for label, score, bbox in zip(pred_labels, pred_scores, pred_bboxes):
        class_label = class_idx2name[int(label)]
        if class_label != "no object":
            objects.append(
                {
                    "label": class_label,
                    "score": float(score),
                    "bbox": [float(elem) - shift_size for elem in bbox],
                },
            )

    return objects


# for output bounding box post-processing
def box_cxcywh_to_xyxy(x):
    """Convert rectangle format from center-x, center-y, width, height to
    x-min, y-min, x-max, y-max."""
    x_c, y_c, w, h = x.unbind(-1)
    b = [(x_c - 0.5 * w), (y_c - 0.5 * h), (x_c + 0.5 * w), (y_c + 0.5 * h)]
    return torch.stack(b, dim=1)


def rescale_bboxes(out_bbox, size):
    """Rescale relative bounding box to box of size given by size."""
    img_w, img_h = size
    b = box_cxcywh_to_xyxy(out_bbox)
    b = b * torch.tensor([img_w, img_h, img_w, img_h], dtype=torch.float32)
    return b


def iob(bbox1, bbox2):
    """
    Compute the intersection area over box area, for bbox1.
    """
    intersection = Rect(bbox1).intersect(Rect(bbox2))

    bbox1_area = Rect(bbox1).get_area()
    if bbox1_area > 0:
        return intersection.get_area() / bbox1_area

    return 0


def objects_to_structures(objects, tokens, class_thresholds):
    """
    Process the bounding boxes produced by the table structure recognition model into
    a *consistent* set of table structures (rows, columns, spanning cells, headers).
    This entails resolving conflicts/overlaps, and ensuring the boxes meet certain alignment
    conditions (for example: rows should all have the same width, etc.).
    """

    tables = [obj for obj in objects if obj["label"] == "table"]
    table_structures = []

    for table in tables:
        table_objects = [
            obj
            for obj in objects
            if iob(obj["bbox"], table["bbox"]) >= inference_config.TABLE_IOB_THRESHOLD
        ]
        table_tokens = [
            token
            for token in tokens
            if iob(token["bbox"], table["bbox"]) >= inference_config.TABLE_IOB_THRESHOLD
        ]

        structure = {}

        columns = [obj for obj in table_objects if obj["label"] == "table column"]
        rows = [obj for obj in table_objects if obj["label"] == "table row"]
        column_headers = [obj for obj in table_objects if obj["label"] == "table column header"]
        spanning_cells = [obj for obj in table_objects if obj["label"] == "table spanning cell"]
        for obj in spanning_cells:
            obj["projected row header"] = False
        projected_row_headers = [
            obj for obj in table_objects if obj["label"] == "table projected row header"
        ]
        for obj in projected_row_headers:
            obj["projected row header"] = True
        spanning_cells += projected_row_headers
        for obj in rows:
            obj["column header"] = False
            for header_obj in column_headers:
                if iob(obj["bbox"], header_obj["bbox"]) >= inference_config.TABLE_IOB_THRESHOLD:
                    obj["column header"] = True

        # Refine table structures
        rows = postprocess.refine_rows(rows, table_tokens, class_thresholds["table row"])
        columns = postprocess.refine_columns(
            columns,
            table_tokens,
            class_thresholds["table column"],
        )

        # Shrink table bbox to just the total height of the rows
        # and the total width of the columns
        row_rect = Rect()
        for obj in rows:
            row_rect.include_rect(obj["bbox"])
        column_rect = Rect()
        for obj in columns:
            column_rect.include_rect(obj["bbox"])
        table["row_column_bbox"] = [
            column_rect.x_min,
            row_rect.y_min,
            column_rect.x_max,
            row_rect.y_max,
        ]
        table["bbox"] = table["row_column_bbox"]

        # Process the rows and columns into a complete segmented table
        columns = postprocess.align_columns(columns, table["row_column_bbox"])
        rows = postprocess.align_rows(rows, table["row_column_bbox"])

        structure["rows"] = rows
        structure["columns"] = columns
        structure["column headers"] = column_headers
        structure["spanning cells"] = spanning_cells

        if len(rows) > 0 and len(columns) > 1:
            structure = refine_table_structure(structure, class_thresholds)

        table_structures.append(structure)

    return table_structures


def refine_table_structure(table_structure, class_thresholds):
    """
    Apply operations to the detected table structure objects such as
    thresholding, NMS, and alignment.
    """
    rows = table_structure["rows"]
    columns = table_structure["columns"]

    # Process the headers
    column_headers = table_structure["column headers"]
    column_headers = postprocess.apply_threshold(
        column_headers,
        class_thresholds["table column header"],
    )
    column_headers = postprocess.nms(column_headers)
    column_headers = align_headers(column_headers, rows)

    # Process spanning cells
    spanning_cells = [
        elem for elem in table_structure["spanning cells"] if not elem["projected row header"]
    ]
    projected_row_headers = [
        elem for elem in table_structure["spanning cells"] if elem["projected row header"]
    ]
    spanning_cells = postprocess.apply_threshold(
        spanning_cells,
        class_thresholds["table spanning cell"],
    )
    projected_row_headers = postprocess.apply_threshold(
        projected_row_headers,
        class_thresholds["table projected row header"],
    )
    spanning_cells += projected_row_headers
    # Align before NMS for spanning cells because alignment brings them into agreement
    # with rows and columns first; if spanning cells still overlap after this operation,
    # the threshold for NMS can basically be lowered to just above 0
    spanning_cells = postprocess.align_supercells(spanning_cells, rows, columns)
    spanning_cells = postprocess.nms_supercells(spanning_cells)

    postprocess.header_supercell_tree(spanning_cells)

    table_structure["columns"] = columns
    table_structure["rows"] = rows
    table_structure["spanning cells"] = spanning_cells
    table_structure["column headers"] = column_headers

    return table_structure


def align_headers(headers, rows):
    """
    Adjust the header boundary to be the convex hull of the rows it intersects
    at least 50% of the height of.

    For now, we are not supporting tables with multiple headers, so we need to
    eliminate anything besides the top-most header.
    """

    aligned_headers = []

    for row in rows:
        row["column header"] = False

    header_row_nums = []
    for header in headers:
        for row_num, row in enumerate(rows):
            row_height = row["bbox"][3] - row["bbox"][1]
            min_row_overlap = max(row["bbox"][1], header["bbox"][1])
            max_row_overlap = min(row["bbox"][3], header["bbox"][3])
            overlap_height = max_row_overlap - min_row_overlap
            if overlap_height / row_height >= 0.5:
                header_row_nums.append(row_num)

    if len(header_row_nums) == 0:
        return aligned_headers

    header_rect = Rect()
    if header_row_nums[0] > 0:
        header_row_nums = list(range(header_row_nums[0] + 1)) + header_row_nums

    last_row_num = -1
    for row_num in header_row_nums:
        if row_num == last_row_num + 1:
            row = rows[row_num]
            row["column header"] = True
            header_rect = header_rect.include_rect(row["bbox"])
            last_row_num = row_num
        else:
            # Break as soon as a non-header row is encountered.
            # This ignores any subsequent rows in the table labeled as a header.
            # Having more than 1 header is not supported currently.
            break

    header = {"bbox": header_rect.get_bbox()}
    aligned_headers.append(header)

    return aligned_headers


def compute_confidence_score(cell_match_scores):
    """
    Compute a confidence score based on how well the page tokens
    slot into the cells reported by the model
    """
    try:
        mean_match_score = sum(cell_match_scores) / len(cell_match_scores)
        min_match_score = min(cell_match_scores)
        confidence_score = (mean_match_score + min_match_score) / 2
    except ZeroDivisionError:
        confidence_score = 0
    return confidence_score


def structure_to_cells(table_structure, tokens):
    """
    Assuming the row, column, spanning cell, and header bounding boxes have
    been refined into a set of consistent table structures, process these
    table structures into table cells. This is a universal representation
    format for the table, which can later be exported to Pandas or CSV formats.
    Classify the cells as header/access cells or data cells
    based on if they intersect with the header bounding box.
    """
    columns = table_structure["columns"]
    rows = table_structure["rows"]
    spanning_cells = table_structure["spanning cells"]
    cells = []
    subcells = []
    # Identify complete cells and subcells
    for column_num, column in enumerate(columns):
        for row_num, row in enumerate(rows):
            column_rect = Rect(list(column["bbox"]))
            row_rect = Rect(list(row["bbox"]))
            cell_rect = row_rect.intersect(column_rect)
            header = "column header" in row and row["column header"]
            cell = {
                "bbox": cell_rect.get_bbox(),
                "column_nums": [column_num],
                "row_nums": [row_num],
                "column header": header,
            }

            cell["subcell"] = False
            for spanning_cell in spanning_cells:
                spanning_cell_rect = Rect(list(spanning_cell["bbox"]))
                if (
                    spanning_cell_rect.intersect(cell_rect).get_area() / cell_rect.get_area()
                ) > inference_config.TABLE_IOB_THRESHOLD:
                    cell["subcell"] = True
                    break

            if cell["subcell"]:
                subcells.append(cell)
            else:
                # cell text = extract_text_inside_bbox(table_spans, cell['bbox'])
                # cell['cell text'] = cell text
                cell["projected row header"] = False
                cells.append(cell)

    for spanning_cell in spanning_cells:
        spanning_cell_rect = Rect(list(spanning_cell["bbox"]))
        cell_columns = set()
        cell_rows = set()
        cell_rect = None
        header = True
        for subcell in subcells:
            subcell_rect = Rect(list(subcell["bbox"]))
            subcell_rect_area = subcell_rect.get_area()
            if (
                subcell_rect.intersect(spanning_cell_rect).get_area() / subcell_rect_area
            ) > inference_config.TABLE_IOB_THRESHOLD:
                if cell_rect is None:
                    cell_rect = Rect(list(subcell["bbox"]))
                else:
                    cell_rect.include_rect(list(subcell["bbox"]))
                cell_rows = cell_rows.union(set(subcell["row_nums"]))
                cell_columns = cell_columns.union(set(subcell["column_nums"]))
                # By convention here, all subcells must be classified
                # as header cells for a spanning cell to be classified as a header cell;
                # otherwise, this could lead to a non-rectangular header region
                header = header and "column header" in subcell and subcell["column header"]
        if len(cell_rows) > 0 and len(cell_columns) > 0:
            cell = {
                "bbox": cell_rect.get_bbox(),
                "column_nums": list(cell_columns),
                "row_nums": list(cell_rows),
                "column header": header,
                "projected row header": spanning_cell["projected row header"],
            }
            cells.append(cell)

    _, _, cell_match_scores = postprocess.slot_into_containers(cells, tokens)
    confidence_score = compute_confidence_score(cell_match_scores)

    # Dilate rows and columns before final extraction
    # dilated_columns = fill_column_gaps(columns, table_bbox)
    dilated_columns = columns
    # dilated_rows = fill_row_gaps(rows, table_bbox)
    dilated_rows = rows
    for cell in cells:
        column_rect = Rect()
        for column_num in cell["column_nums"]:
            column_rect.include_rect(list(dilated_columns[column_num]["bbox"]))
        row_rect = Rect()
        for row_num in cell["row_nums"]:
            row_rect.include_rect(list(dilated_rows[row_num]["bbox"]))
        cell_rect = column_rect.intersect(row_rect)
        cell["bbox"] = cell_rect.get_bbox()

    span_nums_by_cell, _, _ = postprocess.slot_into_containers(
        cells,
        tokens,
        overlap_threshold=0.001,
        forced_assignment=False,
    )

    for cell, cell_span_nums in zip(cells, span_nums_by_cell):
        cell_spans = [tokens[num] for num in cell_span_nums]
        # TODO: Refine how text is extracted; should be character-based, not span-based;
        # but need to associate
        cell["cell text"] = postprocess.extract_text_from_spans(
            cell_spans,
            remove_integer_superscripts=False,
        )
        cell["spans"] = cell_spans

    # Adjust the row, column, and cell bounding boxes to reflect the extracted text
    num_rows = len(rows)
    rows = postprocess.sort_objects_top_to_bottom(rows)
    num_columns = len(columns)
    columns = postprocess.sort_objects_left_to_right(columns)
    min_y_values_by_row = defaultdict(list)
    max_y_values_by_row = defaultdict(list)
    min_x_values_by_column = defaultdict(list)
    max_x_values_by_column = defaultdict(list)
    for cell in cells:
        min_row = min(cell["row_nums"])
        max_row = max(cell["row_nums"])
        min_column = min(cell["column_nums"])
        max_column = max(cell["column_nums"])
        for span in cell["spans"]:
            min_x_values_by_column[min_column].append(span["bbox"][0])
            min_y_values_by_row[min_row].append(span["bbox"][1])
            max_x_values_by_column[max_column].append(span["bbox"][2])
            max_y_values_by_row[max_row].append(span["bbox"][3])
    for row_num, row in enumerate(rows):
        if len(min_x_values_by_column[0]) > 0:
            row["bbox"][0] = min(min_x_values_by_column[0])
        if len(min_y_values_by_row[row_num]) > 0:
            row["bbox"][1] = min(min_y_values_by_row[row_num])
        if len(max_x_values_by_column[num_columns - 1]) > 0:
            row["bbox"][2] = max(max_x_values_by_column[num_columns - 1])
        if len(max_y_values_by_row[row_num]) > 0:
            row["bbox"][3] = max(max_y_values_by_row[row_num])
    for column_num, column in enumerate(columns):
        if len(min_x_values_by_column[column_num]) > 0:
            column["bbox"][0] = min(min_x_values_by_column[column_num])
        if len(min_y_values_by_row[0]) > 0:
            column["bbox"][1] = min(min_y_values_by_row[0])
        if len(max_x_values_by_column[column_num]) > 0:
            column["bbox"][2] = max(max_x_values_by_column[column_num])
        if len(max_y_values_by_row[num_rows - 1]) > 0:
            column["bbox"][3] = max(max_y_values_by_row[num_rows - 1])
    for cell in cells:
        row_rect = None
        column_rect = None
        for row_num in cell["row_nums"]:
            if row_rect is None:
                row_rect = Rect(list(rows[row_num]["bbox"]))
            else:
                row_rect.include_rect(list(rows[row_num]["bbox"]))
        for column_num in cell["column_nums"]:
            if column_rect is None:
                column_rect = Rect(list(columns[column_num]["bbox"]))
            else:
                column_rect.include_rect(list(columns[column_num]["bbox"]))
        cell_rect = row_rect.intersect(column_rect)
        if cell_rect.get_area() > 0:
            cell["bbox"] = cell_rect.get_bbox()
            pass

    return cells, confidence_score


def fill_cells(cells: List[dict]) -> List[dict]:
    """add empty cells to pad cells that spans multiple rows for html conversion

    For example if a cell takes row 0 and 1 and column 0, we add a new empty cell at row 1 and
    column 0. This padding ensures the structure of the output table is intact. In this example the
    cell data is {"row_nums": [0, 1], "column_nums": [0], ...}

    A cell contains the following keys relevent to the html conversion:
    row_nums: List[int]
        the row numbers this cell belongs to; for cells spanning multiple rows there are more than
        one numbers
    column_nums: List[int]
        the columns numbers this cell belongs to; for cells spanning multiple columns there are more
        than one numbers
    cell text: str
        the text in this cell

    """
    new_cells = cells.copy()
    for cell in cells:
        for extra_row in sorted(cell["row_nums"][1:]):
            new_cell = cell.copy()
            new_cell["row_nums"] = [extra_row]
            new_cell["cell text"] = ""
            new_cells.append(new_cell)
    return new_cells


def cells_to_html(cells):
    """Convert table structure to html format."""
    cells = sorted(fill_cells(cells), key=lambda k: (min(k["row_nums"]), min(k["column_nums"])))

    table = ET.Element("table")
    current_row = -1

    for cell in cells:
        this_row = min(cell["row_nums"])

        attrib = {}
        colspan = len(cell["column_nums"])
        if colspan > 1:
            attrib["colspan"] = str(colspan)
        rowspan = len(cell["row_nums"])
        if rowspan > 1:
            attrib["rowspan"] = str(rowspan)
        if this_row > current_row:
            current_row = this_row
            if cell["column header"]:
                cell_tag = "th"
                row = ET.SubElement(table, "thead")
            else:
                cell_tag = "td"
                row = ET.SubElement(table, "tr")
        tcell = ET.SubElement(row, cell_tag, attrib=attrib)
        tcell.text = cell["cell text"]

    return str(ET.tostring(table, encoding="unicode", short_empty_elements=False))


def zoom_image(image: Image, zoom: float) -> Image:
    """scale an image based on the zoom factor using cv2; the scaled image is post processed by
    dilation then erosion to improve edge sharpness for OCR tasks"""
    if zoom <= 0:
        # no zoom but still does dilation and erosion
        zoom = 1
    new_image = cv2.resize(
        cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR),
        None,
        fx=zoom,
        fy=zoom,
        interpolation=cv2.INTER_CUBIC,
    )

    kernel = np.ones((1, 1), np.uint8)
    new_image = cv2.dilate(new_image, kernel, iterations=1)
    new_image = cv2.erode(new_image, kernel, iterations=1)

    return Image.fromarray(new_image)

```

```python
# run_ingest.py

# run_ingest.py

from pathlib import Path
import os
import sys
import argparse
from datetime import datetime
from typing import List

# Your existing imports and code here...
from partition_pdf_and_docx_Final5 import process_documents
# from Get_SEP_Files import get_files
from Get_Docs_From_EmPower_with_Auth2 import download_documents
from sep_file_manager import SEPs
from document_filter import filter_documents_by_type

# Set up argument parser
parser = argparse.ArgumentParser(description="Process documents with optional parameters.")

parser.add_argument("index", nargs='?', default="JAC_SKE_PROD_TEST", help="Index name (namespace) to use.")

parser.add_argument("--max_chunk_size", type=int, default=5000, help="Maximum chunk size.")
parser.add_argument("--html_summaries", type=lambda x: (str(x).lower() == 'true'), default=True, help="Generate HTML summaries (True/False).")
parser.add_argument("--store_debug_files_files", type=lambda x: (str(x).lower() == 'true'), default=True, help="Store debug files (True/False).")
parser.add_argument("--element_dir_path", type=str, default="elements_dir", help="Path to elements directory.")
parser.add_argument("--docs_to_ingest", type=str, default="docs", help="Path to documents to ingest.")

args = parser.parse_args()

# Assign variables from arguments
namespace = args.index
max_chunk_size = args.max_chunk_size
html_summaries = args.html_summaries
store_debug_files_files = args.store_debug_files_files
element_dir_path = Path(args.element_dir_path)
docs_to_ingest = Path(args.docs_to_ingest)
json_dir_path = element_dir_path  # Assuming json_dir_path is the same as element_dir_path

# Debug print statements (optional)
print(f"Using namespace: {namespace}")
print(f"max_chunk_size: {max_chunk_size}")
print(f"html_summaries: {html_summaries}")
print(f"store_debug_files_files: {store_debug_files_files}")
print(f"element_dir_path: {element_dir_path}")
print(f"docs_to_ingest: {docs_to_ingest}")

process_documents(
    WEAVIATE_DOCS_INDEX_NAME=namespace,
    max_chunk_size=max_chunk_size,
    doc_directory=docs_to_ingest,
    elements_directory=element_dir_path,
    json_dir=json_dir_path,
    html_summaries=html_summaries
)

```

```PlainText
 requirements.txt

aiohttp==3.9.5
aiosignal==1.3.1
annotated-types==0.6.0
antlr4-python3-runtime==4.9.3
anyio==4.3.0
attrs==23.2.0
Authlib==1.3.0
backoff==2.2.1
bcrypt==4.1.2
beautifulsoup4==4.12.3
cachetools==5.3.3
certifi==2024.2.2
cffi==1.16.0
chardet==5.2.0
charset-normalizer==3.3.2
chroma-hnswlib==0.7.3
chromadb==0.4.17
click==8.1.7
colorama==0.4.6
coloredlogs==15.0.1
contourpy==1.2.1
cryptography==42.0.5
cycler==0.12.1
dataclasses-json==0.6.4
dataclasses-json-speakeasy==0.5.11
Deprecated==1.2.14
distro==1.9.0
effdet==0.4.1
emoji==2.11.0
et-xmlfile==1.1.0
fastapi==0.110.1
filelock==3.13.3
filetype==1.2.0
flatbuffers==24.3.25
fonttools==4.51.0
frozenlist==1.4.1
fsspec==2024.3.1
google-auth==2.29.0
googleapis-common-protos==1.63.0
greenlet==3.0.3
grpcio==1.64.1
grpcio-health-checking==1.62.2
grpcio-tools==1.62.2
h11==0.14.0
httpcore==1.0.5
httptools==0.6.1
httpx==0.27.0
huggingface-hub==0.22.2
humanfriendly==10.0
idna==3.6
importlib_metadata==7.1.0
importlib_resources==6.4.0
iopath==0.1.10
Jinja2==3.1.3
joblib==1.3.2
jsonpatch==1.33
jsonpath-python==1.0.6
jsonpointer==2.4
kiwisolver==1.4.5
kubernetes==29.0.0
langchain==0.1.20
langchain-community==0.0.38
langchain-core==0.1.52
langchain-openai==0.1.7
langchain-text-splitters==0.0.2
langdetect==1.0.9
langsmith==0.1.59
layoutparser==0.3.4
lxml==5.2.1
Markdown==3.6
MarkupSafe==2.1.5
marshmallow==3.21.1
matplotlib==3.8.4
monotonic==1.6
mpmath==1.3.0
msg-parser==1.2.0
multidict==6.0.5
mypy-extensions==1.0.0
networkx==3.3
nltk==3.8.1
numpy==1.26.4
oauthlib==3.2.2
olefile==0.47
omegaconf==2.3.0
onnx==1.16.0
onnxruntime==1.15.0
openai==1.30.1
opencv-python==4.9.0.80
openpyxl==3.1.2
opentelemetry-api==1.16.0
opentelemetry-exporter-otlp-proto-grpc==1.16.0
opentelemetry-proto==1.16.0
opentelemetry-sdk==1.16.0
opentelemetry-semantic-conventions==0.37b0
orjson==3.10.3
overrides==7.7.0
packaging==23.2
pandas==2.2.1
pdf2image==1.17.0
pdfminer.six==20231228
pdfplumber==0.11.0
pikepdf==8.14.0
pillow==10.3.0
pillow_heif==0.16.0
portalocker==2.8.2
posthog==3.5.0
protobuf==4.25.3
psycopg2-binary==2.9.9
pulsar-client==3.5.0
pyasn1==0.6.0
pyasn1_modules==0.4.0
pycocotools==2.0.7
pycparser==2.22
pydantic==2.7.0
pydantic_core==2.18.1
pyodbc==5.1.0
pypandoc==1.13
pyparsing==3.1.2
pypdf==4.1.0
pypdfium2==4.28.0
PyPika==0.48.9
pyreadline3==3.4.1
pytesseract==0.3.10
python-dateutil==2.9.0.post0
python-docx==1.1.0
python-dotenv==1.0.1
python-iso639==2024.2.7
python-magic==0.4.27
python-multipart==0.0.9
python-pptx==0.6.23
pytz==2024.1
PyYAML==6.0.1
rapidfuzz==3.8.0
regex==2023.12.25
requests==2.31.0
requests-oauthlib==2.0.0
rsa==4.9
safetensors==0.4.2
scikit-learn==1.5.0
scipy==1.13.0
six==1.16.0
sniffio==1.3.1
soupsieve==2.5
SQLAlchemy==2.0.30
starlette==0.37.2
sympy==1.12
tabulate==0.9.0
tenacity==8.2.3
threadpoolctl==3.5.0
tiktoken==0.7.0
timm==0.9.16
tokenizers==0.15.2
tqdm==4.66.2
transformers==4.39.3
truststore==0.10.1
typer==0.9.0
typing-inspect==0.9.0
typing_extensions==4.11.0
tzdata==2024.1
unstructured==0.13.2
unstructured-client==0.18.0
unstructured-inference==0.7.25
unstructured.pytesseract==0.3.12
urllib3==2.2.1
uvicorn==0.29.0
validators==0.28.3
watchfiles==0.21.0
weaviate-client==4.6.4
websocket-client==1.7.0
websockets==12.0
wrapt==1.16.0
xlrd==2.0.1
XlsxWriter==3.2.0
yarl==1.9.4
zipp==3.18.1


```

```python
# partition_pdf_and_docx_Final5.py


## docker cp "C:\Users\Steve.Long\OneDrive - Leonardo DRS\Documents\_AI_TEAM\Ingestion_Docker\partition_pdf_and_docx_Final5.py" unstructured:/app/partition_pdf_and_docx_Final5.py

import os
import json

# Import NLTK and configure the data path to use the pre-copied nltk_data directory.
# This ensures that the necessary NLTK data (such as the 'punkt' tokenizer) is available 
# without needing to download it from the web, which is useful for running in a Docker container.
import nltk
nltk.data.path.append('/usr/local/share/nltk_data')

import pypandoc

from unstructured.partition.pdf import partition_pdf
from unstructured.partition.docx import partition_docx
from pathlib import Path
import logging
from typing import Optional, IO
# from typing import Any, Dict
# from unstructured.staging.weaviate import stage_for_weaviate
from unstructured.chunking.title import chunk_by_title
from langchain.indexes import index
from ExtendedSQLRecordManager4 import ExtendedSQLRecordManager
import weaviate
from weaviate.auth import AuthApiKey
from Weaviate_Schema import create_weaviate_schema
# from weaviate.connect import ConnectionParams, ProtocolParams
from langchain_community.vectorstores import Weaviate
from langchain_core.embeddings import Embeddings
from langchain_openai import AzureOpenAIEmbeddings
from openai import AzureOpenAI
from dotenv import load_dotenv
import math
# from bs4 import BeautifulSoup
# from sqlalchemy import inspect
import inspect
import time
# from langchain.prompts import  PromptTemplate
from HTML_Processing import llm_summarize_text_as_html
# from HTML_Processing0 import process_text_as_html
from ingestion_utilities import clean_table_of_contents,clean_record_of_changes, write_log_to_file, process_large_tables,process_images
from Acronym_Tools import process_acronym_text_as_html
# from write_all_elements_to_file2 import write_elements_to_text_file2
from unstructured.partition.xlsx import partition_xlsx
# default_html_summary_prompt= """\
# You will be given HTML content produced from partitioning a DOCX file using Unstructured-IO libraries, \
# where the HTML is stored in the metadata as 'text_as_html'. Your task is to provide a detailed, \
# semantically relevant description of the content represented by the HTML. This description will \
# be embedded using OpenAI's 'text-embedding-ada-002' model and used for semantic search purposes.\

# Ensure that your description includes unique terms, column and row names, categories, and table data. \
# However, you do not need to list every column or row. For repetitive labels, generalize them \
# to capture the essence of the content. For example, columns labeled as 'test1', 'test2', \
# 'test3', etc., can be summarized as 'tests'. Similarly, for columns labeled 'transponder \
# test pass/fail', 'ground system test pass/fail', and 'antenna test pass/fail', you can describe \
# them as 'pass/fail results for the transponder, antenna, and ground system'.\

# Your entire response will be embedded, so ensure that your description is only semantically \
# relevant and includes key information that will improve the search capabilities. Write the \
# description directly without prefacing it with phrases like 'The HTML content represents'.\

# If the provided HTML lacks semantic content, respond with 'None'. No semantic content includes \
# HTML that consists of empty tags, tags with only whitespace, purely structural or decorative elements, \
# or any content that does not provide meaningful information for understanding or searching the document.\
# """
# PromptTemplate(
#     input_variables=["max_chunk_size"],
#     template="""
# """


default_html_summary_prompt= """\
Your task is to provide a detailed, semantically relevant description of the provided HTML. \
This HTML represents content extracted from DOCX and PDF files using Unstructured-IO libraries. \
Your description will be converted into a vector embedding for semantic search purposes.

Ensure your description encapsulates unique terms, column/row names, categories, table data, titles, \
labels, and other key information. Minimize common, generic characteristics and focus on details that \
highlight the uniqueness of the content.

Your description shall be no more than 1000 words.

If the HTML lacks semantic content (e.g., empty tags, whitespace, \
purely structural or decorative elements), respond with 'None.' 
If the HTML contains an acronym list, respond with 'I FOUND YOU AN ACRONYM LIST.'

Write descriptions as if viewing the original content, not the HTML. Speak directly to the content \
without prefacing with phrases like 'The HTML content represents.' The reader should not be aware that \
the text was extracted or converted to HTML.
"""

html_content_1shot="""<table>
<thead>
<tr><th>Voltage  </th><th>Max Current  </th><th>Current Limit  </th></tr>
</thead>
<tbody>
<tr><td>22 V ±10%</td><td>5 A          </td><td>7 A            </td></tr>
</tbody>
</table>"""

html_summary_1shot="""\
The table presents electrical specifications for a device, listing voltage, maximum current, \
and current limit. The voltage is specified as 22 volts with a tolerance of plus or minus 10%. \
The maximum current is 5 amperes, and the current limit is 7 amperes.\
"""


# Load environment variables
try:
    load_dotenv()
except Exception as e:
    print(f"Error loading environment variables: {e}")

# Set environment variables
os.environ['CUDA_VISIBLE_DEVICES'] = '0'
os.environ['LOCAL_FILES_ONLY'] = 'True'
os.environ['TRANSFORMERS_OFFLINE'] = 'True'
os.environ['HF_HUB_OFFLINE'] = 'True'
# os.environ['HF_HUB_CACHE'] = "/app/.cache"
# os.environ['UNSTRUCTURED_CACHE_DIR'] = "/app/.cache"

WEAVIATE_URL = os.environ["WEAVIATE_URL"]
WEAVIATE_API_KEY = os.environ["WEAVIATE_API_KEY"]
RECORD_MANAGER_DB_URL = os.getenv('RECORD_MANAGER_DB_URL')

default_api_version = os.getenv("AZURE_OPENAI_API_VERSION")
model_4 = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
default_html_summary_model = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
default_embedder_model = os.getenv("AZURE_OPENAI_EMBEDDER")

LLM = AzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"), 
    api_key=os.getenv("AZURE_OPENAI_API_KEY"), 
    api_version=default_api_version
)

# Custom formatter to include more granular information
class CustomFormatter(logging.Formatter):
    def format(self, record):
        # Add the class and function name to the log record if available
        frame = inspect.currentframe()
        while frame:
            if 'self' in frame.f_locals and frame.f_locals['self'].__class__.__name__ != 'CustomFormatter':
                record.class_name = frame.f_locals['self'].__class__.__name__
                break
            frame = frame.f_back
        else:
            record.class_name = 'N/A'

        record.function_name = record.funcName
        record.line_number = record.lineno

        # Adjust timestamp precision
        record.asctime = self.formatTime(record, self.datefmt)
        
        return super().format(record)

    def formatTime(self, record, datefmt=None):
        if datefmt:
            return logging.Formatter.formatTime(self, record, datefmt)
        ct = self.converter(record.created)
        t = time.strftime("%Y-%m-%d %H:%M:%S", ct)
        return t

# Setup logging
log_file_path = Path(__file__).parent / '_RUN_INFO_WARNINGS_AND_ERRORS.txt'
log_format = (
    '%(asctime)s - %(levelname)-8s - %(module)-30s - %(class_name)-25s - '
    '%(function_name)-20s:%(line_number)-4d - %(message)s'
)

# Initialize logging with the basic config
logging.basicConfig(level=logging.INFO)

# Create file and stream handlers
file_handler = logging.FileHandler(log_file_path, mode='a')
stream_handler = logging.StreamHandler()

# Apply the custom formatter to handlers
formatter = CustomFormatter(log_format)
file_handler.setFormatter(formatter)
stream_handler.setFormatter(formatter)

# Get the logger and add handlers to it
logger = logging.getLogger(__name__)
logger.addHandler(file_handler)
logger.addHandler(stream_handler)

# Remove the default handlers to avoid duplicate logging
logger.propagate = False

# Test logging
logger.info('Test log entry')



keys_names_list = [
    "header_footer_type", 
    'attached_to_filename', 
    'parent_id',
    'links', 
    'url', 
    # 'detection_class_prob', 
    'sent_from', 
    'page_number',
    # 'coordinates', 
    'image_mime_type', 
    'document_title',
    #'orig_elements', 
    'sent_to', 
    'filetype', 
    # 'is_continuation', # added recently. 
    'emphasized_text_contents',# added recently. 
    'emphasized_text_tags', # added recently. 
    'section',# added recently. 
    'text_as_html',
    'languages', 
    'file_directory',
    'filename', 
    'file_path' 
    'link_texts', 
    'link_urls',
    'page_name', 
    'subject', 
    'last_modified',
    'section', 
    'regex_metadata', 
    'image_base64', 
    'signature', 
    'category_depth', 
    'data_source', 
    'image_path', 
    'detection_origin',
    'acronym_list',
    'key_terms',
    'references',
    'ToC',
    'currentRev',
    'table_category',
    'acronym_keys', 
    'acronym_values',
    'use4RAG',
    'plot_code'
    'clusterID'
    'tsne_x',
    'tsne_y',
]

def list_files(directory: Path, file_types: list):
    """
    Finds all file paths with extensions matching file_types.
    If multiple identical file paths are found that only differ by their extensions,
    selects only one file path using the list order provided in file_types as the preferred file type.

    Args:
        directory (Path): The directory to search for files.
        file_types (list): List of file extensions to look for.

    Returns:
        list: List of file paths.
    """
    try:
        files = []
        seen = {}
        for file_type in file_types:
            for file in directory.rglob(f'*.{file_type}'):
                base_name = file.stem
                if base_name not in seen:
                    seen[base_name] = file
                    files.append(file)
        return files
    except Exception as e:
        logger.error(f"Error listing files in directory {directory}: {e}")
        return []

def create_directory(path: Path):
    try:
        path.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.error(f"Failed to create directory {path}: {e}")



def object_to_dict(obj):
    """
    Convert an object's attributes to a dictionary, filtering out private attributes
    and callable methods. It only includes attributes that hold data.
    
    Args:
    obj: The object from which to extract attributes.

    Returns:
    A dictionary containing attribute names and their values.
    """
    try:
        return {
            attr: getattr(obj, attr)
            for attr in dir(obj)
            if not attr.startswith('__') and not callable(getattr(obj, attr))
        }
    except Exception as e:
        logger.error(f"Error converting object to dict: {e}")
        return {}

def calculate_chunk_params(elements, max_chunk_size):
    #reference https://vectify.ai/blog/LargeDocumentSummarization
    # Sum all characters in elements.page_content
    try:
        # Try to calculate document_size using page_content attribute
        document_size = sum(len(element.text) for element in elements)
    except AttributeError:
        # If there is an AttributeError, try using the text attribute instead
        logger.info(f"'text' attribute is not contained in 'element' object. Using 'page_content' attribute instead")
        document_size = sum(len(element.page_content) for element in elements)

    # Total chunk number
    K = math.ceil(document_size / max_chunk_size)
    # Average integer chunk size
    average_chunk_size = math.ceil(document_size / K)

    return average_chunk_size

def store_elements_to_JSON_file(elements, output_file_path):
    try:
        output_file_path = Path(output_file_path)

        # Ensure the directory exists
        output_file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with output_file_path.open('w', encoding='utf-8') as file:
            for element in elements:
                # Ensure the original elements are not altered by creating local variables
                text_lines = element.page_content.split('\n')
                non_empty_lines = [line.strip() for line in text_lines if line.strip()]
                text = '\n'.join(non_empty_lines)  # Join non-empty lines with a newline character

                metadata = element.metadata.get('filename', 'unknown')  # Get filename from metadata or use 'unknown'
                
                # Create the JSON structure
                data = {
                    "text": text,
                    "meta": {
                        "pile_set_name": metadata
                    }
                }
                
                # Write the JSON structure as a line to the file
                file.write(json.dumps(data, ensure_ascii=False) + '\n')
    except Exception as e:
        logger.error(f"Error storing elements to JSON file {output_file_path}: {e}")

def extract_title_from_text(text):
    prompt = f"""\
A chunk of text that was extracted from the cover page of a document will be provided to you. \
Read the chunk of extracted text and identify the title of the document. \
The title should contain two parts, the document type and the object the document pertains to. 
Examples of document types: Acceptance Test Procedure, Interface Control Document, System Requirements Document, etc...
Examples of objects: Lowpass Filter Assembly, Multiple-object Tracking Radar, Regulated Power Supply, etc...
Respond with only the title and nothing else."""
    
    content_1shot = """\
Hardware Design Description\n\nTriple Synthesizer Circuit Card Assembly\n\nPart Number 22011110-1\n\nContract \
Number  (Purchase Order)  ZA015836\n\nDocument Number  HDD22011110\n\nPrepared for:\n\nDRS Internal\n\n2 December 2022\
"""
    response_1shot = """\
Hardware Design Description, Triple Synthesizer Circuit Card Assembly\
"""

    
    try:
        response = LLM.chat.completions.create(
            model=model_4,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Extracted text: {content_1shot}"},
                {"role": "assistant", "content": f"{response_1shot}"},
                {"role": "user", "content": f"Extracted text: {text}"}
            ]
        )
        title = response.choices[0].message.content.strip()
        return title
    except Exception as e:
        logger.error(f"Error extracting title with GPT-4: {e}")
        return "Unknown Title"


def write_elements_to_text_file(elements,txt_file_path):
    try:
        with open(txt_file_path, 'w', encoding="utf-8") as file:
            for doc in elements:
                # Start a section for each document
                file.write('******\nElements Details:\n')

                # Iterate through each attribute of the Document object
                # Assuming Document class has attributes like 'page_content', 'metadata', etc.
                for attr in dir(doc):
                    # Filter out private and special methods/attributes
                    if not attr.startswith("__") and not callable(getattr(doc, attr)):
                        # Special handling for 'metadata' to print each key-value pair
                        if attr == 'metadata':
                            file.write(f'{attr}:\n')
                            for key, value in getattr(doc, attr).items():
                                file.write(f'  {key}: {value}\n')
                        else:
                            # For all other attributes, just print the value
                            value = getattr(doc, attr)
                            file.write(f'{attr}: {value}\n')

                # End of document section
                file.write('******\n\n\n')
    except Exception as e:
        logger.error(f"Failed to write text file: {e}")

def compute_embeddings(elements):
    embedder = get_embeddings_model()

    for element in elements:
        if element.page_content:
            embedding = embedder.embed_query(element.page_content)
            element.metadata["embedding"] = embedding
        else:
            element.metadata["embedding"] = ""

    return elements


def process_file(
        file_path: Path,
        base_dir: Path, 
        elements_dir: Path, 
        json_path: Path, 
        max_chunk_size=8000,
        module_logs=False,
        html_summary_prompt=default_html_summary_prompt,
        html_summary_model=default_html_summary_model,
        html_summaries=False,
        input_file:Optional[IO[bytes]] = None,
        input_file_type:Optional[str] = None,
        doc_name:Optional[Path] = None
    ):
    if not doc_name: 
        base_name = file_path.stem
    else:
        file_path = doc_name
        base_name = doc_name.stem

    images_directory = elements_dir / f"images_{base_name}"
    create_directory(images_directory)
    logger.info(f"Start process_file on {file_path}")

    enable_process_images = False

    if input_file: # if an input file is provided, don't use 'filename'
        filename = None
        calc_embeddings = True
        enable_process_images = True
    else:
        filename=str(file_path)
        calc_embeddings = False

    try:
        if file_path.suffix == '.pdf':
            logger.info(f"Start partition_pdf")
            elements = partition_pdf(
                file=input_file,
                filename=filename,
                strategy="hi_res",
                languages=['eng'],  # Updated from ocr_languages to languages based on deprecation warning
                extract_images_in_pdf=enable_process_images,
                extract_image_block_output_dir=str(images_directory),
                infer_table_structure=True,
            )
        elif file_path.suffix == '.docx':
            logger.info(f"Start partition_docx")
            elements = partition_docx(
                file=input_file,
                filename=filename,
                infer_table_structure=True,
                include_page_breaks=True,
                include_metadata=True, 
                metadata_last_modified=None,
                chunking_strategy=None,
                extract_images=enable_process_images, 
            )
        elif file_path.suffix == '.xlsx':
            logger.info(f"Start partition_xlsx")
            elements = partition_xlsx(
                file=input_file,
                filename=filename,
                include_header=True,
                include_metadata=True,
                metadata_last_modified=None
            )


        logger.info(f"Finished partitioning file")
        # Filter the list to exclude elements with categories "Header" or "Footer"
        elements = [element for element in elements if element.category not in ["Header", "Footer", "UncategorizedText"]]
        logger.info(f"removed Header, Footer, and UncategorizedText from elements")
        # Calculate chunk parameters dynamically using character count
        
        logger.info(f"max_chunk_size: {max_chunk_size}")
        logger.info(f"Element: {elements[0]}")
        average_chunk_size = calculate_chunk_params(elements, max_chunk_size)
        

        # Ensure non-negative integers for chunk_by_title parameters
        combine_text_under_n_chars = max(0, average_chunk_size // 4)
        max_characters = max(0, average_chunk_size)
        new_after_n_chars = max(0, average_chunk_size - 500)
        
        if max_characters <= 300:
            if max_characters < 200:
                overlap = 0
            else:
                overlap = round(max_characters * 0.5)
        else:
            overlap = 200

        elements = chunk_by_title(
            elements=elements, 
            combine_text_under_n_chars=combine_text_under_n_chars, 
            include_orig_elements=True, 
            max_characters=max_characters, 
            multipage_sections=True,
            new_after_n_chars=new_after_n_chars,
            overlap=overlap,
            overlap_all=False,
        )
        logger.info(f"finished chunk_by_title using avg chunk size:{average_chunk_size}")



        for element in elements:
            # Check if the old attribute 'text' exists
            if hasattr(element, 'text'):
                # Set the new attribute 'page_content' with the value from 'text'
                setattr(element, 'page_content', getattr(element, 'text'))
                
                # Optionally, remove the old attribute 'text' if no longer needed
                delattr(element, 'text')


        # Write GPT-4 responses to a separate text file
        if module_logs == True:
            before_ToC_output_file_path = elements_dir / f"before_ToC__Data.txt"
            write_log_to_file(
                elements, 
                before_ToC_output_file_path, 
                type = 'page_content', 
                 mode='w',
                logger = logger
            )

        if enable_process_images:
            excluded_strings = ["LEONARDO DRS", "DRS", "LEONARDO"] 
            process_images(elements, excluded_strings)
            logger.info(f"here:{enable_process_images}")
        logger.info(f"enable_process_images:{enable_process_images}")

        elements = process_large_tables(elements)
        clean_table_of_contents(elements, logger)
        clean_record_of_changes(elements, logger)


        # Iterate through each element in the elements list
        for element in elements:
            if hasattr(element.metadata, 'to_dict') and callable(getattr(element.metadata, 'to_dict')):
                # Convert metadata using to_dict if available.
                # This converts Unstructured's Document Object to Langchain's Document Object
                element.metadata = element.metadata.to_dict()
            else:
                # Convert metadata manually if no to_dict method is available
                element.metadata = object_to_dict(element.metadata)

            # Ensure all necessary keys are present in metadata
            for key in keys_names_list:
                if key not in element.metadata:
                    element.metadata[key] = None  # or provide a default value appropriate for the key


        if module_logs == True:
            after_output_file_path = elements_dir / f"after__Data.txt"
            write_log_to_file(
                elements, 
                after_output_file_path, 
                type = 'page_content', 
                 mode='w',
                logger = logger
            )


        # generate_embeddings_for_elements(elements)

        # process_elements_based_on_keyword(
        #     elements,
        #     'Embedding_Vector_Sample_ToC.txt', 
        #     'ToC', 
        #     'contents',
        #     z_threshold:= 2.0, 
        #     iqr_multiplier= 1.5
        # )




        # # Replace acronyms in page_content and update metadata with key_terms, then delete elements with acronyms
        elements, acronym_processing_log= process_acronym_text_as_html(elements, logger)


        # Process elements with text_as_html before storing
        elements = llm_summarize_text_as_html(
            elements, 
            html_summaries=html_summaries,
            logger =logger
            )

        if module_logs == True:
            after_output_file_path = elements_dir / f"after__Data.txt"
            write_log_to_file(
                elements, 
                after_output_file_path, 
                type = 'page_content', 
                 mode='w',
                logger = logger
            )


       
        if elements_dir:
            txt_file_path = elements_dir / f"ElementData_{base_name}.txt"
            write_elements_to_text_file(elements, txt_file_path)

    

        if json_path:
            output_file_name = Path(json_path) / f"{base_name}.json"
            store_elements_to_JSON_file(elements, output_file_name)


        final_elements = []
        for e in elements:
            if e.metadata['acronym_list'] == None:
                final_elements.append(e)

        

        logger.info(f"Processed {file_path.name}; content written to {elements_dir} and images saved in {images_directory}")

        ## calculate embeddings and add to the elements when calc_embeddings is True (single file bytes were provided to process_file())
        if calc_embeddings:
            elements = compute_embeddings(elements)



        return elements

    except Exception as e:
        logger.error(f"Failed to partition file {file_path}: {e}")
        
        # Handling DOCX conversion to PDF
        if file_path.suffix == '.docx':
            logger.info(f"Converting {file_path} to PDF file")
            pdf_path = elements_dir / f"{base_name}.pdf"
            try:
                pypandoc.convert_file(str(file_path), 'pdf', outputfile=str(pdf_path))
                logger.info(f"Converted DOCX to PDF: {pdf_path}")
                return process_file(pdf_path, base_dir, elements_dir, json_path, max_chunk_size)
            except Exception as convert_error:
                logger.error(f"Failed to convert DOCX to PDF: {convert_error}")

        return []

def get_embeddings_model(embedder_model=default_embedder_model, api_version=default_api_version) -> Embeddings:
    try:
        return AzureOpenAIEmbeddings(model=embedder_model, chunk_size=200, api_version=api_version)
    except Exception as e:
        logger.error(f"Error getting embeddings model: {e}")
        return None

def process_documents(
        WEAVIATE_DOCS_INDEX_NAME, 
        doc_directory,
        max_chunk_size=8000,  
        elements_directory=None, 
        json_dir=None,
        text_key='page_content', 
        embedder_model= default_embedder_model, 
        html_summary_model=default_html_summary_model, 
        html_summary_prompt=default_html_summary_prompt, 
        module_logs=False,
        html_summaries=False, 
        doc_extensions=["docx", "pdf"],
):
    try: 

        # WEAVIATE_DOCS_INDEX_NAME=f"weaviate/{WEAVIATE_DOCS_INDEX_NAME}"
        
        if isinstance(doc_directory, list):
            potential_files = [Path(file) for file in doc_directory]
        else:
            doc_directory = Path(doc_directory)
            if doc_directory.is_file():
                potential_files = [doc_directory]
            elif doc_directory.is_dir():
                potential_files = list_files(doc_directory, doc_extensions)#["docx", "pdf"])#, "txt"])
            else:
                raise ValueError("Invalid doc_directory value")

        record_manager = ExtendedSQLRecordManager(
            f"weaviate/{WEAVIATE_DOCS_INDEX_NAME}", 
            db_url=RECORD_MANAGER_DB_URL, 
            logger=logger
        )
   
        

        # Get the status of potential files
        new_files = []
        modified_files = []
        current_files = []
        
        for file in potential_files:
            status = record_manager.get_document_status(str(file))
            if status == 'new':
                new_files.append(file)
            elif status == 'modified':
                modified_files.append(file)
            elif status == 'current':
                current_files.append(file)

        logger.info(f"New files: {len(new_files)}")
        logger.info(f"Modified files: {len(modified_files)}")
        logger.info(f"Current files: {len(current_files)}")

        logger.info(f"Processing {len(new_files) + len(modified_files)} out of {len(potential_files)} documents.")
    
        elements = []
        for file in new_files + modified_files:
            try:
                current_elements_dir = elements_directory if not isinstance(elements_directory, list) else None
                current_json_dir = json_dir if not isinstance(json_dir, list) else None

                if isinstance(elements_directory, list):
                    current_elements_dir = elements_directory[(new_files + modified_files).index(file)]
                if isinstance(json_dir, list):
                    current_json_dir = json_dir[(new_files + modified_files).index(file)]

                elements.extend(
                    process_file(
                        file, 
                        file.parent, 
                        Path(current_elements_dir), 
                        current_json_dir, 
                        max_chunk_size,
                        module_logs, 
                        html_summary_prompt,
                        html_summary_model,
                        html_summaries
                    )
                )
            except Exception as e:
                logger.error(f"Error processing file {file}: {e}")

        if elements:
            for element in elements:
                # logger.info(f"page_content:{element.page_content}")
                file_directory = element.metadata.get('file_directory')
                filename = element.metadata.get('filename')

                if file_directory is not None and filename is not None:
                    element.metadata['file_path'] = str(Path(file_directory) / filename)
                else:
                    logger.warning(f"Missing file_directory or filename in element metadata: {element.metadata}")

            ingest_docs(
                elements, 
                record_manager, 
                WEAVIATE_DOCS_INDEX_NAME,
                text_key=text_key, 
                embedder_model=embedder_model, 
                html_summary_model=html_summary_model, 
                html_summary_prompt=html_summary_prompt,
                max_chunk_size=max_chunk_size, 
                module_logs=module_logs,
                html_summaries=html_summaries
            )
        else:
            logger.info("No elements to ingest.")

    except Exception as e:
        logger.error(f"Error processing documents: {e}")


def ingest_docs(elements, record_manager, INDEX_NAME, **kwargs):
    try:

        # for element in elements:
        #     element.metadata['url'] = r"https://aisfwb.empower.drs.com/Apps/OpenDocument.aspx?obj=0&docid=615460"


        filtered_elements = []
        acronym_keys = []
        acronym_values = []
        document_map_acronym = []

        for element in elements:
            element.metadata['use4RAG'] = True
            element.metadata['plot_code'] = 1
            element.metadata['clusterID'] = -1
            element.metadata['tsne_x'] = 0.0001
            element.metadata['tsne_y'] = 0.0001



        for element in elements:
            if not element.metadata.get('acronym_list'):
                filtered_elements.append(element)
            else:
                acronym = element.metadata.get('acronym_list', {})
                keys = list(acronym.keys())
                values = list(acronym.values())
                mapping = element.metadata.get('file_path', '')
                acronym_keys.append(keys)
                acronym_values.append(values)
                document_map_acronym.append(mapping)

        elements = filtered_elements

        for element in elements:
            file_path = element.metadata.get('file_path', '')
            if file_path in document_map_acronym:
                index = document_map_acronym.index(file_path)
                element.metadata['acronym_keys'] = acronym_keys[index]
                element.metadata['acronym_values'] = acronym_values[index]
            

        # # Define the connection parameters
        # connection_params = ConnectionParams(
        #     http=ProtocolParams(
        #         host="localhost",  # Change this to your Weaviate host if different
        #         port=8080,         # Change this to your Weaviate port if different
        #         secure=False       # Set to True if using HTTPS
        #     ),
        #     grpc=ProtocolParams(
        #         host="localhost",  # Change this to your Weaviate host if different
        #         port=50051,         # Change this to your Weaviate gRPC port if different
        #         secure=False       # Set to True if using HTTPS
        #     )
        # )

        # Create the client
        client = weaviate.Client(
            url=WEAVIATE_URL,
            auth_client_secret=AuthApiKey(api_key=WEAVIATE_API_KEY),
        )

        text_key = kwargs.get('text_key', 'page_content')
        embedder_model = kwargs.get('embedder_model')

        # Tokenization overrides with tuples (key, datatype, tokenization)
        tokenization_overrides = {
            "filename": ("text", "field"),
            "document_title": ("text", "field"),
            "key_terms": ("text[]", "word"),
            "link_texts": ("text[]", "word"),
            "link_urls": ("text[]", "word"),
            "acronym_list":(None, None),
            "acronym_keys":("text[]", "word"),
            "acronym_values":("text[]", "word"),
            "use4RAG": ("boolean", None)
        }


        schema_keys_names_list = create_weaviate_schema(
            client, 
            INDEX_NAME, 
            text_key, 
            elements,
            tokenization_overrides,
            logger=logger
        )

        # Create the vector store object
        vectorstore = Weaviate(
            client=client,
            index_name=INDEX_NAME,
            text_key=text_key,
            embedding=get_embeddings_model(embedder_model),
            by_text=False,
            attributes=schema_keys_names_list
        )

        indexing_stats = record_manager.add_document(
            elements,
            vectorstore,
            #cleanup="full",
            force_update=(os.environ.get("FORCE_UPDATE") or "false").lower() == "true",
            batch_size=kwargs.get('batch_size', 1000),
            **kwargs
        )
        logger.info(f"Indexing stats: {indexing_stats}")


    except Exception as e:
        logger.error(f"Error ingesting documents: {e}")


def main():
    try:
        dir_path = r"docs"#r"H:\\SEP-04 Project Engineering\\SEP-04-01(M) Process for Product Development.docx"#r"C:\Users\Steve.Long\Documents\2201 BOM scrub (5-17-22).xlsx"#r"L:\papers"#G:\Unstructured_Processing\JACSKE_Program_10000_Chunks"#H:\SEP-04 Project Engineering"#H:\\SEP-04 Project Engineering\\SEP-04-01(M) Process for Product Development.docx" #H:\SEP-04 Project Engineering"#
        store_dir = r"elements_dir"
        process_documents(
            WEAVIATE_DOCS_INDEX_NAME="test_22040712f", 
            max_chunk_size=10000, 
            doc_directory=dir_path, 
            elements_directory=store_dir, 
            json_dir=store_dir,
            module_logs=False,
            html_summaries = False,
            doc_extensions=['docx', 'pdf']#, "xlsx"]
        )
    except Exception as e:
        logger.error(f"Error in main function: {e}")

if __name__ == "__main__":
    main()

```

```python
# main.py

## docker cp "C:\Users\Steve.Long\OneDrive - Leonardo DRS\Documents\_AI_TEAM\Ingestion_Docker\main.py" Ingest:/app/main.py

from fastapi import FastAPI, BackgroundTasks, Query, File, UploadFile, HTTPException, status
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import subprocess
import os
import io
from pathlib import Path
from partition_pdf_and_docx_Final5 import process_file
from unstructured.documents.elements import Element


import truststore   # ensure OS-level CA store is honoured
# Inject corporate root/intermediate certs into the SSL truststore
truststore.inject_into_ssl()

app = FastAPI()

# Define the log file path from the environment variable
log_file = os.getenv('LOG_FILE_PATH', '/app/_RUN_INFO_WARNINGS_AND_ERRORS.txt')
#python_path = os.getenv('PYTHON_PATH', '/usr/bin/python3')

# Ensure the log file exists
with open(log_file, "w") as f:
    pass  # Create or clear the log file

@app.get("/")
def read_root():
    return {"message": "Welcome to the document processing GUI"}

@app.post("/run-script/")
def run_script(background_tasks: BackgroundTasks):
    def run():
        with open(log_file, "a") as f:
            # Run the run_ingest.py script and redirect its output to the log file
            process = subprocess.Popen(["python", "run_ingest.py"], stdout=f, stderr=f, env=os.environ)
            process.wait()  # Wait for the process to complete

    background_tasks.add_task(run)
    return {"message": "Script is running"}

# curl -Method POST -Uri "http://localhost:8000/run-script/JACSKE_TEST_20241126?max_chunk_size=5000&html_summaries=false&store_debug_files_files=false&element_dir_path=my_elements&docs_to_ingest=my_docs"
# curl -Method POST -Uri "http://localhost:8000/run-script/JACSKE_TEST_20241126?max_chunk_size=5000&html_summaries=false&store_debug_files_files=false"


@app.post("/run-script/{index}")
def run_script_with_index(
    index: str,
    background_tasks: BackgroundTasks,
    max_chunk_size: int = Query(None),
    html_summaries: bool = Query(None),
    store_debug_files_files: bool = Query(None),
    element_dir_path: str = Query(None),
    docs_to_ingest: str = Query(None)    
):
    def run():
        with open(log_file, "a") as f:
            # Build the command with arguments
            command = ["python", "run_ingest.py", index]

            # Append optional arguments if they are provided
            if max_chunk_size is not None:
                command.extend(["--max_chunk_size", str(max_chunk_size)])
            if html_summaries is not None:
                command.extend(["--html_summaries", str(html_summaries)])
            if store_debug_files_files is not None:
                command.extend(["--store_debug_files_files", str(store_debug_files_files)])
            if element_dir_path is not None:
                command.extend(["--element_dir_path", element_dir_path])
            if docs_to_ingest is not None:
                command.extend(["--docs_to_ingest", docs_to_ingest])

            # Run the run_ingest.py script with arguments
            process = subprocess.Popen(command, stdout=f, stderr=f, env=os.environ)
            process.wait()  # Wait for the process to complete

    background_tasks.add_task(run)
    return {"message": f"Script is running with index '{index}'"}

@app.get("/logs/")
def get_logs():
    def log_stream():
        with open(log_file, "r") as f:
            while True:
                line = f.readline()
                if not line:
                    break
                yield line

    return StreamingResponse(log_stream(), media_type="text/plain")

@app.get("/gui/")
def get_gui():
    return FileResponse("static/index.html")

@app.post("/ingest-new-docs/{collection}")
def check_new_docs(collection: str, background_tasks: BackgroundTasks):
    def run():
        with open(log_file, "a") as f:
            # Run the run_ingest.py script and redirect its output to the log file
            process = subprocess.Popen(["python", "ingest_docs.py"], stdout=f, stderr=f, env=os.environ)
            process.wait()  # Wait for the process to complete

    background_tasks.add_task(run)
    return {"message": f"Ingesting '{collection}'"}


## curl -X POST "http://localhost:8000/extract-text" -H "Content-Type: multipart/form-data" -F "file=@C:\\Users\\Steve.Long\\OneDrive - Leonardo DRS\\Desktop\\EmPower_Docs_Test_EmPower_Auth_Script\\HDD22011330_00.pdf"


@app.post("/extract-text")
async def extract_text(
    file: UploadFile = File(...),
    max_chunk_size: int = Query(8000),
    html_summaries: bool = Query(True)
):
    """
    Accepts a PDF, DOC, or DOCX file using multipart/form-data, processes it with
    the appropriate partitioning function, and returns extracted text chunks and metadata.
    """
    if not file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file was uploaded."
        )

    # Validate file extension
    filename = file.filename.lower()
    if not (filename.endswith(".pdf") or filename.endswith(".doc") or filename.endswith(".docx")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type. Only PDF, DOC, or DOCX files are supported."
        )

    # Read file content into a BytesIO buffer
    file_content = await file.read()
    file_like = io.BytesIO(file_content)


    # Determine which partitioning function to use based on extension
    try:

        elements = process_file(
            file_path=None,
            input_file=file_like,
            base_dir=None, 
            elements_dir=Path(r"elements_dir"), 
            json_path=Path(r"elements_dir"), 
            max_chunk_size=max_chunk_size,
            html_summaries=html_summaries,
            doc_name=Path(filename)
        )
        
        # Construct the response data
        response_data = []
        for elem in elements:
            elem.metadata['category'] = elem.category
            response_data.append({
                "page_content": elem.page_content,
                "metadata": elem.metadata,
            })
        return {"elements": response_data}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing file: {str(e)}"
        )


## curl -X POST "http://localhost:8000/extract-text-test-only" -H "Content-Type: multipart/form-data" -F "file=@C:\\Users\\Steve.Long\\OneDrive - Leonardo DRS\\Desktop\\EmPower_Docs_Test_EmPower_Auth_Script\\HDD22011330_00.pdf"
@app.post("/extract-text-test-only")
async def extract_text(
    file: UploadFile = File(...),
    max_chunk_size: int = Query(8000),
    html_summaries: bool = Query(True)
):
    """
    Accepts a PDF, DOC, or DOCX file using multipart/form-data and returns Fake Data (extracted text chunks and metadata).
    """
    if not file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file was uploaded."
        )

    # Validate file extension
    filename = file.filename.lower()
    if not (filename.endswith(".pdf") or filename.endswith(".doc") or filename.endswith(".docx")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type. Only PDF, DOC, or DOCX files are supported."
        )

    # Read file content into a BytesIO buffer
    file_content = await file.read()
    file_like = io.BytesIO(file_content)

    elements = []
    for index, _ in enumerate(range(5),start=1):
        x = Element()
        x.text = f'This is the text for element {index}'
        setattr(x, 'page_content', getattr(x, 'text'))
        x.metadata.filepath = f'this is the filepath for element {index}'

        if index ==1:
            x.metadata.image_base64 = [f"{index}VBORw0KGgoAAAANSUhEUgAA",f"{index}VBORw0KGgoAAAANSUhEUgBB"]
        else:
            x.metadata.image_base64 = [f"{index}VBORw0KGgoAAAANSUhEUgAA"]

        x.metadata.category = 'test_category'
        x.metadata.document_title = 'test_doc_title'
        x.metadata.filename = 'test_filename'
        x.metadata.text_as_html = ''
        x.metadata.url = ''

        x.metadata = x.metadata.to_dict()
        elements.append(x)

    try:
        # Construct the response data
        response_data = []
        for elem in elements:
            response_data.append({
                "page_content": elem.page_content,
                "metadata": elem.metadata
            })
        return {"elements": response_data}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing file: {str(e)}"
        )



app.mount("/static", StaticFiles(directory="static"), name="static")

```

```python
# ingestion_utilities.py

import os
import logging
from typing import Dict
import json
from bs4 import BeautifulSoup

from langchain_openai import AzureOpenAIEmbeddings, AzureOpenAI
from langchain_core.embeddings import Embeddings
import base64

default_api_version = os.getenv("AZURE_OPENAI_API_VERSION")
model_4 = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
default_html_summary_model = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
default_embedder_model = os.getenv("AZURE_OPENAI_EMBEDDER")

def get_embeddings_model(embedder_model=default_embedder_model, api_version=default_api_version) -> Embeddings:
    try:
        return AzureOpenAIEmbeddings(model=embedder_model, chunk_size=200, api_version=api_version)
    except Exception as e:
        print(f"Error getting embeddings model: {e}")
        return None

def get_llm(model=model_4, api_version=default_api_version):
    try:
        return AzureOpenAI(model=model, azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"), api_key=os.getenv("AZURE_OPENAI_API_KEY"), api_version=api_version)
    except Exception as e:
        print(f"Error getting LLM model: {e}")
        return None

def log_and_delete_element(element, logger: logging.Logger):
    try:
        logger.info(f"Deleting element {id(element)} from filename:{element.metadata['filename']}")
        logger.info(f"Element contents: {element.page_content[:200]}")
        logger.info(f"Element metadata: {element.metadata['text_as_html'][:200]}")
        
        print(f"Deleting element {id(element)} in filename:{element.metadata['filename']}")

    except Exception as e:
        try:
            logger.info(f"Deleting element {id(element)} from filename:{element.metadata.filename}")
            logger.info(f"Element contents: {element.page_content[:200]}")
            logger.info(f"Element metadata: {element.metadata.text_as_html[:200]}")
        
            print(f"Deleting element {id(element)} in filename:{element.metadata.filename}")


        except Exception as e:
            logger.error(f"Error logging element: {e}")

def write_log_to_file(log_data, file_path, logger: logging.Logger=None, type=None, mode='w'):
    
    try:
        if type == None:
            with open(file_path, mode, encoding='utf-8') as file:
                for response in log_data:
                    file.write(json.dumps(response, ensure_ascii=False) + '\n')

        elif type == 'page_content':
            with open(file_path, mode, encoding='utf-8') as file:
                for element in log_data:
                    page_content = element.page_content
                    file.write(page_content + '\n')

        elif type == 'text_as_html':
            with open(file_path, mode, encoding='utf-8') as file:
                for element in log_data:
                    text_as_html = element.metadata['text_as_html']
                    file.write(text_as_html + '\n')

        else:
            logger.error(f"In function write_log_to_file, 'type = {type}' is not valid. Log not stored to file {file_path}")

    except Exception as e:
        logger.error(f"Error writing log data to file {file_path}: {e}")


def clean_table_of_contents(elements, logger = None):
    """
    Iterates through a list of elements to clean up Table of Contents.

    :param elements: List of elements to process.
    """
    # for element in elements:
    #     # Check if the old attribute 'text' exists
    #     if hasattr(element, 'text'):
    #         # Set the new attribute 'page_content' with the value from 'text'
    #         setattr(element, 'page_content', getattr(element, 'text'))
            
    #         # Optionally, remove the old attribute 'text' if no longer needed
    #         delattr(element, 'text')

    try:
        
        # def normalize_whitespace(text):
        #     return ' '.join(text.split())
        log_delete = False

        for element in elements:
            if 'table of contents' in element.page_content.lower():                
                if hasattr(element.metadata, 'orig_elements') and element.metadata.orig_elements:
                    lines_to_delete = []
                    collecting = False
                    element_to_keep = []
                    for orig_elem in element.metadata.orig_elements:

                        if hasattr(orig_elem, 'text') and 'table of contents' in orig_elem.text.lower():
                            collecting = True
                        if collecting:
                            if hasattr(orig_elem, 'text'):
                                lines_to_delete.append(orig_elem.text)
                                log_delete = True
                            if orig_elem.category == 'PageBreak':
                                collecting = False
                        elif orig_elem.category == 'PageBreak':
                            element_to_keep.append('')
                        else:
                            element_to_keep.append(orig_elem.text)
                    
                    # Join lines_to_delete into a single string and normalize whitespace
                    element_to_keep_str = '\n\n'.join(element_to_keep)
                    
                    element.page_content = element_to_keep_str

                    if log_delete == True:
                        logger.info(f"Table of Contents found in file{element.metadata.filename}. Removing table from document chunks")
                       
                    return
    
    except Exception as e:
        return
    


def clean_record_of_changes(elements, logger=None):
    """
    Iterates through a list of elements to clean up Record of Change or Revision History.

    :param elements: List of elements to process.
    """
    try:
        if elements is None:
            raise ValueError("The 'elements' parameter is None.")

        element_to_keep = []
        table_found = False
        for element in elements:
            if hasattr(element.metadata, 'text_as_html') and element.metadata.text_as_html is not None:
                text_as_html = element.metadata.text_as_html

                if not table_found:  # assuming there is only one revision table
                    if 'record of changes' in text_as_html.lower() or 'revision history' in text_as_html.lower():
                        table_found = True
                        # log_and_delete_element(element, logger)
                        if logger:
                            logger.info(f"Revision history table found in file {element.metadata.filename}. Removing table from document chunks")
                    else:
                        element_to_keep.append(element)
                else:
                    element_to_keep.append(element)
            else:
                element_to_keep.append(element)

        if table_found:
            elements = element_to_keep
            return elements

        # Plan B - Revision table not found. Check again for revision history but not in a table
        log_delete = False
        for element in elements:
            if 'record of changes' in element.page_content.lower() or 'revision history' in element.page_content.lower():
                if hasattr(element.metadata, 'orig_elements') and element.metadata.orig_elements is not None:
                    lines_to_delete = []
                    collecting = False
                    element_to_keep = []
                    for orig_elem in element.metadata.orig_elements:
                        if hasattr(orig_elem, 'text') and ('record of changes' in orig_elem.text.lower() or 'revision history' in orig_elem.text.lower()):
                            collecting = True
                        if collecting:
                            if hasattr(orig_elem, 'text'):
                                lines_to_delete.append(orig_elem.text)
                                log_delete = True
                            if orig_elem.category == 'PageBreak':
                                collecting = False
                        elif orig_elem.category == 'PageBreak':
                            element_to_keep.append('')
                        else:
                            element_to_keep.append(orig_elem.text)

                    # Join lines_to_delete into a single string and normalize whitespace
                    element_to_keep_str = '\n'.join(element_to_keep)
                    element.page_content = element_to_keep_str

                    if log_delete and logger:
                        logger.info(f"Revision history found in file {element.metadata.filename}. Removing table from document chunks")

                    return elements

    except Exception as e:
        if logger:
            logger.error(f"An error occurred: {str(e)}")
        return


def process_table(html_content: str) -> Dict[str, str]:
    """
    Extract dictionary list from HTML table content.

    :param html_content: HTML content containing the table.
    :return: Dictionary of acronyms and their meanings.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    table = soup.find('table')

    table_dict = {}
    if table:
        for row in table.find_all('tr')[1:]:  # Skip the header row
            cells = row.find_all('td')
            if len(cells) == 2:
                first_column = cells[0].get_text(strip=True)
                second_column = cells[1].get_text(strip=True)
                table_dict[first_column] = second_column
    return table_dict

def combine_text_as_html(elements):

    
    text_as_html = elements[0].metadata.text_as_html
    for element in elements:
        text_as_html = f"{text_as_html}\n{element.metadata.text_as_html}"

    elements[0].metadata.text_as_html = text_as_html
    return elements[0]

def mostly_contains(text, substrings, threshold=0.6):
    """Check if any substring constitutes at least `threshold` percent of the text."""
    text_length = len(text)
    if text_length == 0:
        return False  # Avoid division by zero
    
    for substr in substrings:
        if text.count(substr) * len(substr) >= threshold * text_length:
            return True
    return False

def process_images(elements,excluded_strings=None):
    for e in elements:
        image_base64 = []
        for orig in e.metadata.orig_elements:
            if orig.category == "Image" and not mostly_contains(orig.text, excluded_strings):
                image_path = orig.metadata.image_path
                if image_path and os.path.exists(image_path):
                    with open(image_path, "rb") as f:
                        image_base64.append(base64.b64encode(f.read()).decode("utf-8"))
                    
                    # Delete the original file after processing
                    try:
                        os.remove(image_path)
                        print(f"Deleted: {image_path}")
                    except Exception as err:
                        print(f"Error deleting {image_path}: {err}")
        if image_base64:
            e.metadata.image_base64 = image_base64

def process_large_tables(elements, logger=None):
    try:
        table_found = False
        combine_tables = False
        table_to_combine = []
        new_elements = []

        for element in elements:
            if element.category == 'Table':
                if not table_found:
                    table_found = True
                    table_to_combine = [element]
                elif element.metadata.is_continuation:
                    table_to_combine.append(element)
                    combine_tables = True
                elif combine_tables:
                    temp = combine_text_as_html(table_to_combine)
                    new_elements.append(temp)
                    table_to_combine = [element]
                    table_found = True
                    combine_tables = False
                else:
                    new_elements.extend(table_to_combine)
                    table_to_combine = [element]
            elif table_found:
                if combine_tables:
                    temp = combine_text_as_html(table_to_combine)
                    new_elements.append(temp)
                else:
                    new_elements.extend(table_to_combine)
                table_found = False
                combine_tables = False
                table_to_combine = []
                new_elements.append(element)
            else:
                new_elements.append(element)

        # If there is a remaining table to combine at the end of the loop
        if table_to_combine:
            if combine_tables:
                temp = combine_text_as_html(table_to_combine)
                new_elements.append(temp)
            else:
                new_elements.extend(table_to_combine)

        elements = new_elements

    except Exception as e:
        if logger:
            logger.info(f"Error occurred during 'process_large_tables' for file: {element.metadata.filename}. Exception: {e}")
        else:
            print(f"Error occurred during 'process_large_tables' for file: {element.metadata.filename}. Exception: {e}")

    return elements

```

```python
# ingest_docs.py

from pathlib import Path
import os
from datetime import datetime
from typing import List
from partition_pdf_and_docx_Final5 import process_documents
from Get_Docs_From_EmPower_with_DocViewer import download_documents
from sep_file_manager import SEPs
from document_filter import filter_documents_by_type


def Ingest(collection):
    namespace = collection #"SEPs_F_T_C_W_A_V_Summaries"
    max_chunk_size = 10000
    html_summaries = True
    store_debug_files_files = True

    # EmPower Document Search Parameters
    Desired_PartNumber = '%22012%'
    Undesired_PartNumber = 'SK%'
    Document_Types = ['docx']#, 'pdf']
    After_This_Data_YYYY_MM_DD = '2020-01-01'

    # Construct the directories using the namespace and current date
    Base_Dir = Path(r"G:\Unstructured_Processing\Ingested")
    current_date = datetime.now().strftime("_%Y%m%d")
    Doc_dir = Base_Dir / namespace
    element_dir = Doc_dir / "elements"
    json_dir = Doc_dir / "jsons"

    Doc_dir.mkdir(parents=True, exist_ok=True)

    element_dir_path = None
    json_dir_path = None

    counter = 0
    if store_debug_files_files:
        while True:
            element_dir_path = element_dir / f"{current_date}_{counter}"
            json_dir_path = json_dir / f"{current_date}_{counter}"
            
            if not element_dir_path.exists() and not json_dir_path.exists():
                break
            counter += 1

        element_dir_path.mkdir(parents=True, exist_ok=True)
        json_dir_path.mkdir(parents=True, exist_ok=True)

    print(f"Storing ingestion debug files in: {element_dir_path}, {json_dir_path}")

    file_loading_process = namespace.lower()

    if "sep" in file_loading_process:
        seps = SEPs()
        docs_to_ingest = seps.get_files()
        doc_types = ['F', 'T', 'C', 'W', 'A', 'V']
        docs_to_ingest, removed_paths = filter_documents_by_type(docs_to_ingest, doc_types)

    elif "jac" in file_loading_process:
        docs_to_ingest = Doc_dir / "JACSKE_Docs"
        docs_to_ingest.mkdir(parents=True, exist_ok=True)

        download_documents(
            download_folder=docs_to_ingest, 
            Desired_PartNumber=Desired_PartNumber, 
            Document_Types=Document_Types, 
            Undesired_PartNumber=Undesired_PartNumber,
            After_This_Data_YYYY_MM_DD=After_This_Data_YYYY_MM_DD
        )

    process_documents(
        WEAVIATE_DOCS_INDEX_NAME=namespace, 
        max_chunk_size=max_chunk_size, 
        doc_directory=docs_to_ingest, 
        elements_directory=element_dir_path, 
        json_dir=json_dir_path,
        html_summaries=html_summaries
    )

    return

if __name__ == "__main__":
    Ingest("SEP_test_20241002")

```

```python
# Weaviate_Schema.py

import os
import pprint

WEAVIATE_URL = os.environ["WEAVIATE_URL"]
WEAVIATE_API_KEY = os.environ["WEAVIATE_API_KEY"]


def check_weaviate_schema_exist(client, class_name):
    try:
        class_schema = client.schema.get_class(class_name)
        print(f"Schema for class '{class_name}' exists:")
        print(class_schema)
        return True
    except Exception as e:
        print(f"Class '{class_name}' does not exist in the schema.")
        return False

def print_weaviate_schema(client):
    schema = client.schema.get()
    pprint.pprint(schema)

def determine_data_type(value):
    if isinstance(value, list):
        return "text[]"
    elif isinstance(value, int):
        return "int"
    elif isinstance(value, float):
        return "number"
    elif value is None:
        return "text"
    else:
        return "text"

def create_weaviate_schema(client, class_name, key, elements, tokenization_overrides, logger=None):
    try:
        schema = client.schema.get()
        existing_class = next((cls for cls in schema['classes'] if cls['class'] == class_name), None)

        if existing_class:
            existing_properties = {prop['name']: prop for prop in existing_class['properties']}
        else:
            existing_properties = {}

        other_keys = {k: determine_data_type(v) for k, v in elements[0].metadata.items()}

        # Define properties based on the input keys and tokenization_overrides
        properties = []
        key_name_list = []
        for key, data_type in other_keys.items():
            if key in tokenization_overrides:
                override = tokenization_overrides[key]
                if isinstance(override, tuple):
                    data_type, tokenization = override
                    if data_type == None or tokenization == None:
                        continue
                else:
                    tokenization = override
                    data_type = data_type
            else:
                tokenization = "word" if data_type in ["text", "text[]"] else None

            properties.append({
                "name": key,
                "dataType": ["text"] if data_type is None else [data_type],
                "description": f"This property was generated by Weaviate's auto-schema feature",
                "indexFilterable": True,
                "indexSearchable": data_type in ["text", "text[]"],
                "tokenization": tokenization
            })
            key_name_list.append(key)

        if existing_class:
            # Remove properties not present in the new schema
            schema_keys = [prop for prop in properties if prop['name'] in other_keys]
            schema_key_name_list = []
            not_schema_key_name_list = []
            for schema_key in schema_keys:
                if schema_key.get('name') in key_name_list:
                    schema_key_name_list.append(schema_key.get('name'))
                else:
                    not_schema_key_name_list.append(schema_key.get('name'))
            
            if not_schema_key_name_list:
                logger.error(f"in'create_weaviate_schema, the following keys found in elements' metadata are not found in the schema for class {class_name}: {not_schema_key_name_list}")

            return schema_key_name_list
        else:
            # Define the schema with optimized settings for best search performance
            class_obj = {
                "class": class_name,
                "description": "Documents for optimized search performance",
                "properties": properties,
                "invertedIndexConfig": {
                    "bm25": {"b": 0.75, "k1": 2.0},  # Adjusted for better term frequency impact
                    "cleanupIntervalSeconds": 60,
                    "stopwords": {"additions": None, "preset": "en", "removals": None}
                },
                "multiTenancyConfig": {"enabled": False},
                "replicationConfig": {"factor": 1},
                "shardingConfig": {
                    "actualCount": 1,
                    "actualVirtualCount": 128,
                    "desiredCount": 1,
                    "desiredVirtualCount": 128,
                    "function": "murmur3",
                    "key": "_id",
                    "strategy": "hash",
                    "virtualPerPhysical": 128
                },
                "vectorIndexConfig": {
                    "bq": {"enabled": False},
                    "cleanupIntervalSeconds": 300,
                    "distance": "cosine",
                    "dynamicEfFactor": 10,
                    "dynamicEfMax": 1000,
                    "dynamicEfMin": 500,
                    "ef": 1000,
                    "efConstruction": 200,
                    "flatSearchCutoff": 0,# Disable switching to flat search for exhaustive search
                    "maxConnections": 128,
                    "pq": {
                        "bitCompression": False,
                        "centroids": 256,
                        "enabled": False,
                        "encoder": {"distribution": "log-normal", "type": "kmeans"},
                        "segments": 0,
                        "trainingLimit": 100000
                    },
                    "skip": False,
                    "vectorCacheMaxObjects": 1000000000000
                },
                "vectorIndexType": "hnsw",
                "vectorizer": "none"  # external vectorizer
            }

            # Create the class in Weaviate
            client.schema.create_class(class_obj)
            logger.info(f"Weaviate schema created for class name: {class_name}.")
            return key_name_list
    except Exception as e:
        logger.error(f"An error occurred in create_weaviate_schema: {e}")



# # Create the client
# client = weaviate.Client(
#     url=WEAVIATE_URL,
#     auth_client_secret=AuthApiKey(api_key=WEAVIATE_API_KEY),
# )

# text_key = 'page_content'
# embedder_model = 'embedder_model'

# # Tokenization overrides with tuples (key, datatype, tokenization)
# tokenization_overrides = {
#     "filename": ("text", "field"),
#     "document_title": ("text", "field"),
#     "key_terms": ("text[]", "word"),
# }

# INDEX_NAME= 'Test_schema'

# elements = [
#     {
#         "page_content": "page content text",
#         "metadata": {
#             "filename": "document1.pdf",
#             "document_title": "Test Document",
#             "key_terms": ["term1", "term2", "term3"],
#             "page_count": 5,
#             "size": 1024.56,
#             "author": "John Doe",
#             "creation_date": "2024-06-25",
#             "is_active": True,
#             "version": None
#         }
#     },
#     {
#         "page_content": "page content text",
#         "metadata": {
#             "filename": "document2.docx",
#             "document_title": "Another Test Document",
#             "key_terms": ["keyword1", "keyword2"],
#             "page_count": 10,
#             "size": 2048.75,
#             "author": "Jane Smith",
#             "creation_date": "2024-06-24",
#             "is_active": False,
#             "version": "v1.0"
#         }
#     }
# ]

# create_weaviate_schema(
#     client, 
#     INDEX_NAME, 
#     text_key, 
#     elements,
#     tokenization_overrides
# )

```

```python
# POSTgresql_connect_test.py

from sqlalchemy import create_engine, text

# Set the database URL
db_url = 'postgresql://stevenlong:yourpassword@localhost:5433/RecordManager_Postgre_DB'

# Create an SQLAlchemy engine
engine = create_engine(db_url)

# Example function to test the connection
def test_connection(engine):
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT version();"))
            for row in result:
                print(row)
    except Exception as e:
        print(f"Error connecting to the database: {e}")

# Test the connection
test_connection(engine)

```

```python
# POSTgresql_connect_test.py

from sqlalchemy import create_engine, text

# Set the database URL
db_url = 'postgresql://stevenlong:yourpassword@localhost:5433/RecordManager_Postgre_DB'

# Create an SQLAlchemy engine
engine = create_engine(db_url)

# Example function to test the connection
def test_connection(engine):
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT version();"))
            for row in result:
                print(row)
    except Exception as e:
        print(f"Error connecting to the database: {e}")

# Test the connection
test_connection(engine)

```

```python
# HTML_Processing.py

import os
import logging
import json
from typing import List, Tuple, Any, Dict
from bs4 import BeautifulSoup
import numpy as np
from ingestion_utilities import get_embeddings_model
from sklearn.metrics.pairwise import cosine_similarity
from openai import AzureOpenAI

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception as e:
    print(f"Error loading environment variables: {e}")

# Set environment variables
os.environ['CUDA_VISIBLE_DEVICES'] = '0'
os.environ['LOCAL_FILES_ONLY'] = 'True'
os.environ['TRANSFORMERS_OFFLINE'] = 'True'
os.environ['HF_HUB_OFFLINE'] = 'True'

WEAVIATE_URL = os.environ["WEAVIATE_URL"]
WEAVIATE_API_KEY = os.environ["WEAVIATE_API_KEY"]
RECORD_MANAGER_DB_URL = os.getenv('RECORD_MANAGER_DB_URL')

default_api_version = os.getenv("AZURE_OPENAI_API_VERSION")
model_4 = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
default_html_summary_model = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
default_embedder_model = os.getenv("AZURE_OPENAI_EMBEDDER")

# LLM = get_llm(model=model_4)
LLM = AzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"), 
    api_key=os.getenv("AZURE_OPENAI_API_KEY"), 
    api_version=default_api_version
)

embeddings_client=get_embeddings_model(default_embedder_model)


# Default prompts
default_html_summary_prompt = "Your task is to summarize the HTML content provided to you. This HTML represents content extracted from a .docx file using Unstructured-IO libraries. Respond with a concise summary of the content."

html_1shota = """<html>
<head>
    <title>Example Document</title>
</head>
<body>
    <h1>Document Title</h1>
    <p>This is an example paragraph that provides some content about the document. It includes several sentences that give a brief overview of the document's topic.</p>
</body>
</html>"""

html_1shotb = "The example document is about a general topic and includes an overview and some details."

html_prompt = """Your task is to categorize the HTML content provided to you. This HTML represents content \
extracted from a .docx file using Unstructured-IO libraries. Your response must be one of the following categories:
1) Appendix
2) Table of Contents
3) References
4) Other

Respond with the category number and the appropriate JSON format:

1. Appendix:
{
    "category": 1,
    "acronyms": {
        "acronym1": "Acronym Definition",
        "acronym2": "Acronym Definition",
        "acronym3": "Acronym Definition"
    }
}

2. Table of Contents:
{
    "category": 2,
    "sections": ["section 1", "section 2", "section 3"]
}

3. References:
{
    "category": 3,
    "reference_list": ["reference1 document number", "reference2 document number", "reference3 document number"]
}

4. Other:
{
    "category": 4
}"""

def test_acronym_extraction(acronym_dict: Dict[str, str], threshold: float = 0.55) -> Tuple[bool, str]:
    """
    Validate the extracted acronym dictionary based on a percentage threshold.

    :param acronym_dict: Dictionary of acronyms and their meanings.
    :param threshold: Percentage threshold for validation (default is 55%).
    :return: Tuple containing a boolean indicating validity and a validation message.
    """
    if not acronym_dict:
        return False, "The dictionary is empty."
    
    total_pairs = len(acronym_dict)
    valid_pairs = sum(
        key.replace('-', '').replace(' ', '').isalnum() and isinstance(value, str) and bool(value) 
        for key, value in acronym_dict.items()
    )
    
    if total_pairs == 0:
        return False, "The dictionary is empty."
    
    valid_percentage = valid_pairs / total_pairs
    
    if valid_percentage >= threshold:
        return True, "The acronym list has been extracted correctly."
    else:
        return False, f"The acronym list did not meet the {threshold * 100}% validity threshold. Validity: {valid_percentage * 100:.2f}%"

def process_acronym_table(html_content: str) -> Dict[str, str]:
    """
    Extract acronym list from HTML table content.

    :param html_content: HTML content containing the table.
    :return: Dictionary of acronyms and their meanings.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    table = soup.find('table')

    acronym_dict = {}
    if table:
        for row in table.find_all('tr')[1:]:  # Skip the header row
            cells = row.find_all('td')
            if len(cells) == 2:
                acronym = cells[0].get_text(strip=True)
                meaning = cells[1].get_text(strip=True)
                acronym_dict[acronym] = meaning
    return acronym_dict

# def embed_text(text: str) -> np.ndarray:
#     """
#     Embed the given text using OpenAI's Ada model.

#     :param text: Text to be embedded.
#     :return: Numpy array containing the embedding.
#     """

    
    
#     # response = LLM.embeddings.create(input=text, model=default_embedder_model)
#     return embeddings_client.embed_query(text)#np.array(response['data'][0]['embedding'])

# def categorize_content_with_embeddings(elements: List[Any], threshold: float = 0.85) -> None:
#     """
#     Categorize HTML content using embeddings and cosine similarity.

#     :param elements: List of elements containing metadata and content.
#     :param threshold: Cosine similarity threshold for categorization.
#     """
#     contents_elements = [el for el in elements if 'contents' in el.metadata.get('text_as_html', '').lower()]
#     if not contents_elements:
#         return

#     embeddings = np.array([embed_text(el.metadata['text_as_html']) for el in contents_elements])
#     centroid = np.mean(embeddings, axis=0)
    
#     similarities = cosine_similarity(embeddings, centroid.reshape(1, -1))
#     for el, sim in zip(contents_elements, similarities):
#         if sim >= threshold:
#             el.metadata['category'] = 2  # Tag as Table of Contents

def process_html_element(element: Any, logger: logging.Logger) -> Dict[str, Any]:
    """
    Process a single HTML element.

    :param element: Element containing metadata and content.
    :param logger: Logger for logging information and errors.
    :return: Processed element metadata and content.
    """
    html_content = element.metadata.get('text_as_html', None)
    page_content = element.page_content

    if html_content is not None:
        soup = BeautifulSoup(html_content, 'html.parser')
        visible_texts = soup.stripped_strings
        visible_text = ' '.join(visible_texts)
        
        if visible_text.strip():
            table_dict = process_acronym_table(html_content)
            is_valid, validation_message = test_acronym_extraction(table_dict)

            if is_valid:
                element.metadata['acronym_list'] = table_dict
                logger.info(f"Extracted acronym list for element {id(element)} in {element.metadata['filename']}")
            else:
                logger.info(f"Acronym check failed for element {id(element)} in {element.metadata['filename']}, using embeddings for categorization")
                # Embed and categorize content as Table of Contents if applicable
                categorize_content_with_embeddings([element])
        
        elif not page_content.strip():
            logger.warning(f"page_content is empty and html contains no visible text in text_as_html metadata for element {id(element)} in {element.metadata['filename']}")
            # log_and_delete_element(element, logger)
            
    elif not page_content.strip():
        logger.warning(f"page_content is empty and no text_as_html metadata for element {id(element)} in {element.metadata['filename']} - Deleting element")
        # log_and_delete_element(element, logger)

    return element.metadata

def process_text_as_html(
        elements: List[Any], 
        html_summaries: bool = False,
        html_prompt: str = default_html_summary_prompt, 
        html_model: str = default_html_summary_model, 
        html_1shota: str = html_1shota,
        html_1shotb: str = html_1shotb,
        logger: logging.Logger = None
        ) -> Tuple[List[Any], List[Dict[str, Any]]]:
    
    logger = logger if logger else logging.getLogger(__name__)
    
    html_processing_output = []
    new_elements = []

    logger.info(f"Starting process_text_as_html for {elements[0].metadata['filename']} with {len(elements)} elements")

    for element in elements:
        try:
            processed_metadata = process_html_element(element, logger)
            if element.page_content.strip():
                new_elements.append(element)
            html_processing_output.append(processed_metadata)
        except Exception as e:
            logger.error(f"Error processing HTML for element {id(element)} in {element.metadata['filename']}: {e}")

    logger.info(f"Finished process_text_as_html with {len(new_elements)} elements and {len(html_processing_output)} GPT-4 responses")
    return new_elements, html_processing_output


def embed_text(text: str) -> np.ndarray:
    """
    Embed the given text using OpenAI's Ada model.

    :param text: Text to be embedded.
    :return: Numpy array containing the embedding.
    """
    return embeddings_client.embed_query(text)

def generate_embeddings_for_elements(elements: List[Any]) -> None:
    """
    Generate embeddings for all elements and store them in element.embeddings.

    :param elements: List of elements to generate embeddings for.
    """
    try:
        for element in elements:
            page_content = element.page_content
            text_as_html = element.metadata.get('text_as_html', '')

            if page_content.strip() or text_as_html.strip():
                element.embeddings = embed_text(f"{page_content}\n{text_as_html}")
    except Exception as e:       
        print(f"Failed to get embedding for element {id(element)} in {element.metadata['filename']}: {e}")
 

def categorize_content_with_embeddings(elements: List[Any], threshold: float = 0.85) -> None:
    """
    Categorize HTML content using embeddings and cosine similarity.

    :param elements: List of elements containing metadata and content.
    :param threshold: Cosine similarity threshold for categorization.
    """
    contents_elements = [el for el in elements if 'contents' in el.metadata.get('text_as_html', '').lower()]
    if not contents_elements:
        return

    embeddings = np.array([el.embeddings for el in contents_elements])
    centroid = np.mean(embeddings, axis=0)
    
    similarities = cosine_similarity(embeddings, centroid.reshape(1, -1))
    for el, sim in zip(contents_elements, similarities):
        if sim >= threshold:
            el.metadata['category'] = 2  # Tag as Table of Contents

def process_elements_based_on_keyword(elements: List[Any], file_path: str, category: str, keyword: str, 
                                      z_threshold: float = 2.0, iqr_multiplier: float = 1.5) -> None:
    """
    Process elements to find those containing a keyword and calculate similarity scores.

    :param elements: List of elements to process.
    :param file_path: Path to the .txt file containing the reference embedding.
    :param category: Category string to store in element.metadata['table_category'].
    :param keyword: Keyword or phrase to search for in elements.
    :param z_threshold: Z-score threshold to consider a value as an outlier.
    :param iqr_multiplier: Multiplier for the IQR method to consider a value as an outlier.
    """
    with open(file_path, 'r') as file:
        reference_embedding = np.fromstring(file.read().strip(), sep=' ')
    
    keyword_lower = keyword.lower()
    matching_elements = [
        el for el in elements 
        if (el.page_content and keyword_lower in el.page_content.lower()) 
        or (el.metadata.get('text_as_html') and keyword_lower in el.metadata['text_as_html'].lower())
    ]
    
    if not matching_elements:
        return
    
    matching_similarities = []
    for element in matching_elements:
        matching_similarity = cosine_similarity([element.embeddings], [reference_embedding])[0][0]
        matching_similarities.append(matching_similarity)

    similarities = []
    for element in elements:
        similarity = cosine_similarity([element.embeddings], [reference_embedding])[0][0]
        similarities.append(similarity)       
    
    highest_similarity = max(matching_similarities)
    best_element = matching_elements[matching_similarities.index(highest_similarity)]
    
    mean_score = np.mean(similarities)
    std_dev_score = np.std(similarities)
    
    if std_dev_score == 0:
        z_score = 0
    else:
        z_score = (highest_similarity - mean_score) / std_dev_score
    
    Q1 = np.percentile(similarities, 25)
    Q3 = np.percentile(similarities, 75)
    IQR = Q3 - Q1
    lower_bound = Q1 - iqr_multiplier * IQR
    upper_bound = Q3 + iqr_multiplier * IQR
    
    is_outlier_z = abs(z_score) > z_threshold
    is_outlier_iqr = highest_similarity < lower_bound or highest_similarity > upper_bound
    
    if is_outlier_iqr or is_outlier_z:
        best_element.metadata['table_category'] = category



def load_strings_from_json(file_path: str) -> List[str]:
    """
    Load strings to embed from a JSON file.

    :param file_path: Path to the JSON file.
    :return: List of strings to embed.
    """
    with open(file_path, 'r') as file:
        data = json.load(file)
    return data.get('strings', [])

def clean_text(text: str) -> str:
    """
    Clean the text by handling newlines, extra spaces, and other common text issues.

    :param text: Text to be cleaned.
    :return: Cleaned text.
    """
    # Replace multiple newlines with a single space
    text = text.replace('\r', ' ').replace('\n', ' ')
    # Replace tabs with a single space
    text = text.replace('\t', ' ')
    # Replace multiple spaces with a single space
    text = ' '.join(text.split())
    return text

def create_and_store_aggregated_embedding(file_path: str, output_path: str, method: str = 'average', weights: List[float] = None) -> None:
    """
    Create embeddings for a list of strings from a JSON file, aggregate them using the specified method, and store the vector in a text file.

    :param file_path: Path to the JSON file containing the strings to be embedded.
    :param output_path: Path to the text file where the aggregated embedding will be stored.
    :param method: Method to use for aggregation ('average', 'max_pooling', 'min_pooling', 'weighted_average').
    :param weights: Weights for weighted averaging (optional, required if method is 'weighted_average').
    """
    strings_to_embed = load_strings_from_json(file_path)
    cleaned_strings = [clean_text(string) for string in strings_to_embed]
    embeddings = np.array([embed_text(string) for string in cleaned_strings])
    
    if method == 'average':
        aggregated_embedding = np.mean(embeddings, axis=0)
    elif method == 'max_pooling':
        aggregated_embedding = np.max(embeddings, axis=0)
    elif method == 'min_pooling':
        aggregated_embedding = np.min(embeddings, axis=0)
    elif method == 'weighted_average':
        if weights is None:
            raise ValueError("Weights must be provided for weighted averaging.")
        aggregated_embedding = np.average(embeddings, axis=0, weights=weights)
    else:
        raise ValueError("Unsupported aggregation method.")

    with open(output_path, 'w') as file:
        file.write(' '.join(map(str, aggregated_embedding)))



def extract_title_from_text(text, logger=None):
    prompt = f"""\
A chunk of text that was extracted from the cover page of a document will be provided to you. \
Read the chunk of extracted text and identify the title of the document. \
The title should contain two parts, the document type and the object the document pertains to. 
Examples of document types: Acceptance Test Procedure, Interface Control Document, System Requirements Document, etc...
Examples of objects: Lowpass Filter Assembly, Multiple-object Tracking Radar, Regulated Power Supply, etc...
Respond with only the title and nothing else."""
    
    content_1shot = """\
Hardware Design Description\n\nTriple Synthesizer Circuit Card Assembly\n\nPart Number 22011110-1\n\nContract \
Number  (Purchase Order)  ZA015836\n\nDocument Number  HDD22011110\n\nPrepared for:\n\nDRS Internal\n\n2 December 2022\
"""
    response_1shot = """\
Hardware Design Description, Triple Synthesizer Circuit Card Assembly\
"""

    
    try:
        response = LLM.chat.completions.create(
            model=model_4,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Extracted text: {content_1shot}"},
                {"role": "assistant", "content": f"{response_1shot}"},
                {"role": "user", "content": f"Extracted text: {text}"}
            ]
        )
        title = response.choices[0].message.content.strip()
        return title
    except Exception as e:
        logger.error(f"Error extracting title with GPT-4: {e}")
        return "Unknown Title"

def llm_summarize_text_as_html(
        elements, 
        html_summaries=False,
        html_summary_prompt=default_html_summary_prompt, 
        html_summary_model=default_html_summary_model, 
        max_chunk_size = 8000,
        logger = None
        ):
    html_processing_output = []

    logger.info(f"Starting process_text_as_html for {elements[0].metadata['filename']} with {len(elements)} elements ")
    try:
        doc_title = None
        if html_summaries is True:
            doc_title = extract_title_from_text(elements[0].page_content)

            new_html_summary_prompt= f"""\
    Your task is to provide a detailed, semantically relevant description of the provided HTML. \
    This HTML represents content extracted from a .docx file titled {doc_title} using Unstructured-IO libraries. \
    Your description will be converted into a vector embedding for semantic search purposes.

    Ensure your description encapsulates unique terms, column/row names, categories, table data, titles, \
    labels, and other key information. Minimize common, generic characteristics and focus on details that \
    highlight the uniqueness of the content. 

    Your description shall be no more than 1000 words.

    If the HTML lacks semantic content (e.g., empty tags, whitespace, \
    purely structural or decorative elements), respond with 'None.' 

    Write descriptions as if viewing the original content, not the HTML. Speak directly to the content \
    without prefacing with phrases like 'The HTML content represents.' The reader should not be aware that \
    the text was extracted or converted to HTML.
    """

            new_html_content_1shot="""<table>
    <thead>
    <tr><th>Voltage  </th><th>Max Current  </th><th>Current Limit  </th></tr>
    </thead>
    <tbody>
    <tr><td>22 V ±10%</td><td>5 A          </td><td>7 A            </td></tr>
    </tbody>
    </table>"""

            new_html_summary_1shot="""\
    The table presents electrical specifications for a device, listing voltage, maximum current, \
    and current limit. The voltage is specified as 22 volts with a tolerance of plus or minus 10%. \
    The maximum current is 5 amperes, and the current limit is 7 amperes.\
    """



        for element in elements:
            text_as_html = element.metadata.get('text_as_html', None)
            page_content = element.page_content
            if not page_content:
                page_content = ''

            if text_as_html is not None:
                html_content = text_as_html
                soup = BeautifulSoup(html_content, 'html.parser')
                visible_texts = soup.stripped_strings  # Extract visible text
                visible_text = ' '.join(visible_texts)
                
                if visible_text.strip():
                    if html_summaries is True:
                        try:

                            # Use GPT-4 to generate a summary
                            response = LLM.chat.completions.create(
                                model=html_summary_model, 
                                messages=[
                                    {"role": "system", "content": f"{new_html_summary_prompt}"},
                                    {"role": "user", "content": f"{new_html_content_1shot}"},
                                    {"role": "assistant", "content": f"{new_html_summary_1shot}"},
                                    {"role": "user", "content": f"{page_content}\n{text_as_html}"},
                                ]
                            )
                            summary = response.choices[0].message.content.strip()
                            element.page_content = summary

                            # Store response for later use
                            html_processing_output.append({
                                "element_id": id(element),
                                "file_name": element.metadata['filename'],
                                "file_directory": element.metadata['file_directory'], 
                                "page_name": element.metadata['page_name'], 
                                "page_content": element.page_content,
                                "processed_html_used_for_logic": soup,
                                "html_content": html_content,
                                "summary": summary,
                                "document_title": doc_title
                            })
                            print(f"Generated summary for element {id(element)} in {element.metadata['filename']} \n\tSummary: {summary[:80]}...")
                            logger.info(f"Generated summary for element {id(element)} in {element.metadata['filename']} \n\tSummary: {summary[:80]}...")
                        except Exception as e:
                            logger.error(f"Error processing HTML with GPT-4 for element {id(element)} in {element.metadata['filename']}: {e}")
                            print(f"Error processing HTML with GPT-4 for element {id(element)} in {element.metadata['filename']}: {e}")
                    else:
                        html_processing_output.append({
                            "element_id": id(element),
                            "file_name": element.metadata['filename'],
                            "file_directory": element.metadata['file_directory'], 
                            "page_name": element.metadata['page_name'], 
                            "page_content": element.page_content,
                            "processed_html_used_for_logic": soup,
                            "html_content": html_content,
                            "summary": None,
                            "document_title": doc_title
                        })
                elif not page_content.strip():
                    print(f"page_content is empty and html contains no visible text in text_as_html metadata for element {id(element)} in {element.metadata['filename']}")
                    logger.warn(f"page_content is empty and html contains no visible text in text_as_html metadata for element {id(element)} in {element.metadata['filename']}")
                    # log_and_delete_element(element)
                    
            elif not page_content.strip():
                print(f"page_content is empty and no text_as_html metadata for element {id(element)} in {element.metadata['filename']} - Deleting element")
                logger.warn(f"page_content is empty and no text_as_html metadata for element {id(element)} in {element.metadata['filename']} - Deleting element")
                # log_and_delete_element(element)

            element.metadata['document_title'] = doc_title

        logger.info(f"Finished process_text_as_html with {len(elements)} elements and {len(html_processing_output)} GPT-4 responses")
        
        
        return elements

    except Exception as e:
        logger.error(f"Error in llm_summarize_text_as_html.")
        return
```

```python
# ExtendedSQLRecordManager4.py


import hashlib
import os
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, Float, create_engine, inspect, UniqueConstraint, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import logging

from langchain.indexes import SQLRecordManager, index
from langchain.indexes._sql_record_manager import UpsertionRecord  # Importing the UpsertionRecord class
import uuid  # Importing uuid module for UUID generation


Base = declarative_base()

class DocRecord(Base):
    """A SQLAlchemy model for storing document records."""
    __tablename__ = 'doc_records'
    uuid = Column(
        String,
        index=True,
        default=lambda: str(uuid.uuid4()),  # Ensuring UUID is generated as a string
        primary_key=True,
        nullable=False,
    )
    group_id = Column(String, index=True, nullable=False) # this is the file_path without the extension (.docx, .pdf, etc... are removed)
    namespace = Column(String, index=True, nullable=False)
    hash = Column(String)
    last_modified = Column(DateTime)
    ingestion_date = Column(DateTime)
    updated_at = Column(Float, index=True)
    text_key = Column(String, default='0')
    embedder_model = Column(String, default='0')
    html_summary_model = Column(String, default='0')
    html_summary_prompt = Column(String, default='0')
    max_chunk_size = Column(Integer, default=0)
    html_summaries = Column(Integer, default=0)

    __table_args__ = (
        UniqueConstraint("group_id", "namespace", name="uix_group_id_namespace"),
        Index("ix_group_id_namespace", "group_id", "namespace"),
    )

class ExtendedSQLRecordManager(SQLRecordManager):
    """A class that extends SQLRecordManager to manage document-level records."""

    def __init__(self, namespace, db_url=None, engine=None, engine_kwargs=None, async_mode=False, logger=None):
        """Initializes the ExtendedSQLRecordManager with a namespace and database URL.

        Args:
            namespace: The namespace for the vector store.
            db_url: The database URL for connecting to the SQL database.
            engine: An already existing SQL Alchemy engine.
            engine_kwargs: Additional keyword arguments for the engine.
            async_mode: Whether to create an async engine.
            logger: A logger object for logging messages.
        """
        super().__init__(namespace=namespace, db_url=db_url, engine=engine, engine_kwargs=engine_kwargs, async_mode=async_mode)
        if db_url:
            self.engine = create_engine(db_url, **(engine_kwargs or {}))
        elif engine:
            self.engine = engine
        else:
            raise ValueError("Must specify either db_url or engine")

        self.Session = sessionmaker(bind=self.engine)
        self.logger = logger if logger else logging.getLogger(__name__)
        self.record_manager = SQLRecordManager(namespace=namespace, db_url=db_url, engine=engine, engine_kwargs=engine_kwargs, async_mode=async_mode)
        self.namespace = namespace
        # self.record_manager.create_schema()
        self.ensure_schema_exists()
        # self.identify_and_add_missing_columns()  # Ensure all columns are present
   
    def create_schema(self):
        """Creates the necessary database schema if it doesn't exist."""
        # super().create_schema()
        if not inspect(self.engine).has_table('doc_records'):
            self._prompt_user_and_create_tables()

    def ensure_schema_exists(self):
        """Ensures the necessary database schema exists and matches the defined schema."""
        inspector = inspect(self.engine)
        # self.record_manager.create_schema()
        if not inspector.has_table("upsertion_record") or not inspector.has_table("doc_records") or not self._schema_matches():
            self._prompt_user_and_create_tables()
            self.logger.info("Schema created.")
        else:
            self.logger.info("Schema already exists and matches the defined schema.")
    
    def _prompt_user_and_create_tables(self):
        prompt_message = """\
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

The tables 'doc_records' and 'upsertion_record' do not exist or do not match the defined schema.
User must first run:
'Delete_doc_records_table_and_create_a_new_table.sql'
to create tables before documents can be ingested via the ExtendedSQLRecordManager.py

INGESTION ABORTED!
"""
        print(prompt_message)
        self.logger.info(prompt_message)
        exit()
    
        
    def _schema_matches(self):
        """Checks if the existing schema matches the defined schema for DocRecord and UpsertionRecord."""
        inspector = inspect(self.engine)

        # Check DocRecord table
        doc_record_columns = inspector.get_columns('doc_records')
        doc_record_expected_columns = {col.name: col.type for col in DocRecord.__table__.columns}
        for col in doc_record_columns:
            if col['name'] not in doc_record_expected_columns or not isinstance(col['type'], type(doc_record_expected_columns[col['name']])):
                return False

        # Check UpsertionRecord table
        upsertion_record_columns = inspector.get_columns('upsertion_record')
        upsertion_record_expected_columns = {col.name: col.type for col in UpsertionRecord.__table__.columns}
        for col in upsertion_record_columns:
            if col['name'] not in upsertion_record_expected_columns or not isinstance(col['type'], type(upsertion_record_expected_columns[col['name']])):
                return False

        return True

    def get_document_hash(self, file_path):
        """Generates an MD5 hash for the specified document.

        Args:
            file_path: The path to the document file.

        Returns:
            The MD5 hash of the document.
        """
        with open(file_path, 'rb') as f:
            file_hash = hashlib.md5(f.read()).hexdigest()
        return file_hash

    def get_document_status(self, file_path, group_id=None):
        """Checks the status of a document (new, modified, or current).

        Args:
            group_id: The group ID of the document.

        Returns:
            The status of the document ('new', 'modified', or 'current').
        """
        if not group_id:
            group_id = os.path.splitext(file_path)[0]
            

        group_id= str(group_id)
        session = self.Session()
        try:
            doc_record = session.query(DocRecord).filter_by(group_id=group_id, namespace=self.namespace).first()
            if doc_record:
                file_hash = self.get_document_hash(file_path)
                #last_modified = datetime.fromtimestamp(os.path.getmtime(group_id))
                if doc_record.hash == file_hash:# and doc_record.last_modified == last_modified:
                    return 'current'
                else:
                    return 'modified'
            else:
                return 'new'
        finally:
            session.close()

    def delete_document(
        self,
        vectorstore,
        namespace,
        group_ids
    ):
        """
        Delete documents from the vector store and the record manager based on the provided namespace and list of group_ids.

        Args:
            vectorstore: The vector store object.
            namespace: The namespace for the vector store.
            group_ids: A list of group IDs to be deleted.
        """

        # List all keys in the namespace that are also in the provided list of group_ids
        keys = self.record_manager.list_keys(group_ids=group_ids)

        if not keys:
             self.logger.info(f"No keys found in the namespace {namespace} for the provided group IDs.")
        else:
            # Delete keys using the record manager
            self.record_manager.delete_keys(keys)
            self.logger.info(f"All keys in the namespace '{namespace}' for the provided group IDs have been deleted from the record manager.")

        """
        ISSUE SUMMARY:

        The current implementation of the `delete_document` method does not properly delete old chunks from the Weaviate database when a document is updated. 
        While the method correctly identifies and deletes keys from the record manager based on `group_ids`, it fails to target and delete the corresponding 
        chunks from Weaviate. This results in both the old and new chunks coexisting in the database after an update.

        ROOT CAUSE:

        1. The deletion logic for Weaviate is flawed:
        - It retrieves all objects in the namespace using the Weaviate client query (`client.query.get(namespace)`).
        - It deletes these objects without filtering them based on the `group_ids` or the keys retrieved from the record manager.

        2. This indiscriminate deletion process:
        - Either deletes unrelated data in the namespace (if objects are present for other documents).
        - Or fails to delete the specific chunks associated with the `group_ids`, leaving old chunks in Weaviate.

        IMPACT:

        - Duplicate chunks: Old chunks remain in the Weaviate database alongside the newly inserted chunks.
        - Inefficiency: The script performs unnecessary operations by querying and deleting all objects in the namespace instead of targeting specific ones.
        - Inconsistency: The record manager accurately tracks the current state of the document, but Weaviate retains outdated data, causing a mismatch.

        RESOLUTION PLAN (TO BE IMPLEMENTED):

        1. Modify the `delete_document` method to use the `keys` (IDs) retrieved from `self.record_manager.list_keys(group_ids=group_ids)` 
        for deletions in Weaviate.
        2. Replace the direct interaction with the Weaviate client (`client.data_object.delete`) with the vector store's `delete` method:
        - Example: `vectorstore.delete(ids=keys)`
        3. Ensure the method deletes only the specific chunks associated with the `group_ids`, preventing duplication or unintended deletions.

        TEMPORARY WORKAROUND:

        Until this fix is implemented, manual cleanup of old chunks in the Weaviate database may be necessary to prevent duplication issues 
        when updating documents.

        """



        # Initialize Weaviate client to delete data from Weaviate
        client = vectorstore._client

        try:
            # Retrieve and delete all object IDs in the index in batches
            while True:
                response = client.query.get(namespace).with_additional("id").do()
                if 'data' in response and namespace in response['data']:
                    objects = response['data'][namespace]
                    if not objects:
                        break

                    for obj in objects:
                        object_id = obj['id']
                        client.data_object.delete(object_id)

                    self.logger.info(f"Batch of {len(objects)} objects deleted from Weaviate index '{namespace}'.")

                else:
                    self.logger.info(f"No more data found in Weaviate index '{namespace}'.")
                    break

        except Exception as e:
            self.logger.error(f"Error deleting objects from Weaviate index '{namespace}': {e}")


    def update_document_record(self, session, group_id, file_hash, last_modified, ingestion_date, **kwargs):
        """Updates or inserts a document record in the database.

        Args:
            session: The SQLAlchemy session.
            group_id: The group ID of the document.
            file_hash: The MD5 hash of the document.
            last_modified: The last modified timestamp of the document.
            ingestion_date: The ingestion date of the document.
            **kwargs: Additional columns for document processing information.
        """
        existing_doc = session.query(DocRecord).filter_by(group_id=group_id, namespace=self.namespace).first()
        if existing_doc:
            # Update the existing record
            existing_doc.hash = file_hash
            existing_doc.last_modified = last_modified
            existing_doc.ingestion_date = ingestion_date
            for key, value in kwargs.items():
                if hasattr(existing_doc, key):
                    setattr(existing_doc, key, value)
            self.logger.info(f"Updated existing document record for {group_id}")
        else:
            # Insert a new record
            new_doc_record = DocRecord(
                group_id=group_id,
                hash=file_hash,
                last_modified=last_modified,
                namespace=self.namespace,
                ingestion_date=ingestion_date,
                **{k: v for k, v in kwargs.items() if hasattr(DocRecord, k)}
            )
            session.add(new_doc_record)
            self.logger.info(f"Added new document record for {group_id}")

    def remove_document(self, vectorstore, namespace, file_paths, batch_size=10):
        """
        Removes document records from the database and deletes them from the vector store.

        Args:
            vectorstore: The vector store object.
            namespace: The namespace for the vector store.
            file_paths: A list of file paths to be removed.
            batch_size: The number of documents to process in each batch.
        """
        # Initialize a database session
        session = self.Session()
        
        try:
            # Lists to hold group IDs
            list_of_group_ids = file_paths

            self.logger.info(f"Total group IDs to remove: {len(list_of_group_ids)}")

            # Process documents in batches
            for i in range(0, len(list_of_group_ids), batch_size):
                self.logger.info(f"Processing batch starting at index {i}")
                batch_group_ids = list_of_group_ids[i:i + batch_size]
                self.logger.info(f"Batch group IDs: {batch_group_ids}")

                # Begin a nested transaction for batch processing
                with session.begin_nested():
                    try:
                        # Delete existing documents from upsertion_record
                        self.delete_document(
                            vectorstore=vectorstore,
                            namespace=namespace,
                            group_ids=batch_group_ids
                        )

                        # Delete existing documents from doc_records
                        session.query(DocRecord).filter(
                            DocRecord.group_id.in_(batch_group_ids),
                            DocRecord.namespace == namespace
                        ).delete(synchronize_session=False)

                        # Commit the nested transaction
                        session.commit()

                    except Exception as e:
                        # Rollback the nested transaction in case of an error
                        session.rollback()
                        self.logger.error(f"Error removing documents batch: {e}")
                        raise

        except Exception as e:
            # Rollback the outer transaction in case of an error
            session.rollback()
            self.logger.error(f"Error removing documents: {e}")
        finally:
            # Close the database session
            session.close()
        
        self.logger.info("Document removal process completed.")




    def add_document(self, elements, vectorstore, cleanup='incremental', force_update=False, batch_size=10, **kwargs):
        """
        Adds new document records to the database and indexes them in the vector store.

        Args:
            elements: List of elements to be indexed.
            vectorstore: The vector store object.
            cleanup: The cleanup mode for the indexing.
            force_update: Force update documents even if they are present in the record manager.
            batch_size: The number of documents to process in each batch.
            **kwargs: Additional columns for document processing information.
        """
        # Initialize a database session
        session = self.Session()
        
        # Dictionary to hold indexing statistics
        total_indexing_stats = {
            'num_added': 0,
            'num_updated': 0,
            'num_skipped': 0,
            'num_deleted': 0
        }
        
        try:
            # Mapping from group_id (without extension) to full file_path (with extension)
            group_id_to_file_path = {}
            up_to_date_group_ids = []

            # Populate group_id_to_file_path from elements
            for element in elements:
                file_path = element.metadata['file_path']  # Full file path with extension
                group_id = os.path.splitext(file_path)[0]  # Remove extension
                if group_id:
                    group_id_to_file_path[group_id] = file_path

            # List of unique group IDs
            list_of_group_ids = list(group_id_to_file_path.keys())

            # Check the status of each document
            for group_id in list_of_group_ids:
                file_path = group_id_to_file_path[group_id]
                file_hash = self.get_document_hash(file_path)
                last_modified = datetime.fromtimestamp(os.path.getmtime(file_path))
                existing_doc_status = self.get_document_status(group_id,file_path)
                
                if existing_doc_status == 'current':
                    self.logger.info(f"Document {group_id} is already up-to-date.")
                    up_to_date_group_ids.append(group_id)

            # Remove up-to-date group IDs from list_of_group_ids
            list_of_group_ids = [group_id for group_id in list_of_group_ids if group_id not in up_to_date_group_ids]

            self.logger.info(f"Total group IDs to process: {len(list_of_group_ids)}")

            # Process documents in batches
            for i in range(0, len(list_of_group_ids), batch_size):
                self.logger.info(f"Processing batch starting at index {i}")
                batch_group_ids = list_of_group_ids[i:i + batch_size]
                self.logger.info(f"Batch group IDs: {batch_group_ids}")
                batch_elements = [element for element in elements if os.path.splitext(element.metadata['file_path'])[0] in batch_group_ids]

                # Modify 'file_path' in metadata to remove the extension
                for element in batch_elements:
                    file_path_with_ext = element.metadata['file_path']
                    file_path_without_ext = os.path.splitext(file_path_with_ext)[0]
                    element.metadata['file_path'] = file_path_without_ext    # Update 'file_path' to be without extension

                # Begin a nested transaction for batch processing
                with session.begin_nested():
                    try:
                        # Delete existing documents before adding new ones
                        self.delete_document(
                            vectorstore=vectorstore,
                            namespace=self.namespace,
                            group_ids=batch_group_ids
                        )

                        # Index the entire batch of elements once
                        indexing_stats = index(
                            batch_elements,
                            self.record_manager,
                            vectorstore,
                            cleanup=cleanup,
                            source_id_key="file_path",
                            force_update=force_update,
                        )

                        # Accumulate indexing stats
                        for key in total_indexing_stats:
                            total_indexing_stats[key] += indexing_stats.get(key, 0)

                        # Update document records after successful indexing
                        for group_id in batch_group_ids:
                            file_path = group_id_to_file_path[group_id]
                            file_hash = self.get_document_hash(file_path)
                            last_modified = datetime.fromtimestamp(os.path.getmtime(file_path))
                            ingestion_date = datetime.now()

                            # Ensure html_summaries is stored as 1 or 0
                            if 'html_summaries' in kwargs:
                                kwargs['html_summaries'] = 1 if kwargs['html_summaries'] in [True, 1] else 0

                            # Update the document record in the database
                            self.update_document_record(session, group_id, file_hash, last_modified, ingestion_date, **kwargs)

                        # Commit the nested transaction
                        session.commit()

                    except Exception as e:
                        # Rollback the nested transaction in case of an error
                        session.rollback()
                        self.logger.error(f"Error adding documents batch: {e}")
                        raise

        except Exception as e:
            # Rollback the outer transaction in case of an error
            session.rollback()
            self.logger.error(f"Error adding documents: {e}")
        finally:
            # Close the database session
            session.close()
        
        # Return the accumulated indexing statistics
        return total_indexing_stats







    def get_documents_by_namespace(self):
        """Retrieves all documents stored in the specified namespace.

        Returns:
            A list of tuples containing file paths, last modified dates, hashes, 
            and additional columns that contain the parameters used during processing 
            such as max_chunk_size, embedder_model, etc...
        """
        session = self.Session()
        try:
            docs = session.query(DocRecord).filter_by(namespace=self.namespace).all()
            return [(doc.group_id, doc.last_modified, doc.hash, doc.text_key, doc.embedder_model, 
                     doc.html_summary_model, doc.html_summary_prompt, doc.max_chunk_size, doc.html_summaries, doc.ingestion_date) for doc in docs]
        finally:
            session.close()

    def get_default_columns_from_docrecord(self):
        """Retrieve columns with default values from the DocRecord class."""
        default_columns = {}
        for column in DocRecord.__table__.columns:
            if column.default is not None:
                default_columns[column.name] = column
        return default_columns

    def identify_and_add_missing_columns(self):
        """Identifies and adds missing columns with default values in the doc_records table."""
        session = self.Session()
        try:
            inspector = inspect(self.engine)
            # Inspect current columns in doc_records table
            current_doc_columns = {col['name'] for col in inspector.get_columns('doc_records')}

            # Get expected columns from DocRecord
            expected_doc_columns = self.get_default_columns_from_docrecord()

            # Find discrepancies
            missing_in_doc_records = {col_name: col_type for col_name, col_type in expected_doc_columns.items() if col_name not in current_doc_columns}

            # Log discrepancies
            if missing_in_doc_records:
                self.logger.warning(f"Missing columns in doc_records table: {list(missing_in_doc_records.keys())}")

                with self.engine.connect() as connection:
                    for column_name, column in missing_in_doc_records.items():
                        # SQL command to add a column to the table
                        col_type = str(column.type.compile(self.engine.dialect))
                        default_value = column.default.arg if column.default is not None else None
                        alter_table_command = f'ALTER TABLE doc_records ADD COLUMN {column_name} {col_type} DEFAULT {default_value}'
                        connection.execute(alter_table_command)
                        self.logger.info(f"Added missing column {column_name} to doc_records table.")
     
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error identifying and adding missing columns: {e}")
        finally:
            session.close()

```

```python
# Acronym_Tools.py

import re
import logging
from typing import List, Tuple, Any, Dict
from bs4 import BeautifulSoup



def test_acronym_extraction(acronym_dict: Dict[str, str], threshold: float = 0.55) -> Tuple[bool, str]:
    """
    Validate the extracted acronym dictionary based on a percentage threshold.

    :param acronym_dict: Dictionary of acronyms and their meanings.
    :param threshold: Percentage threshold for validation (default is 55%).
    :return: Tuple containing a boolean indicating validity and a validation message.
    """
    if not acronym_dict:
        return False, "The dictionary is empty."
    
    total_pairs = len(acronym_dict)
    valid_pairs = 0
    invalid_entries = []


    check_invalid_entries = []
    seen_keys = set()

    for key, value in acronym_dict.items():
        if not isinstance(key, str) or not isinstance(value, str):
            invalid_entries.append((key, value))
        
        # Check if the value is not empty or just whitespace
        if not bool(value.strip()):
            invalid_entries.append((key, value))
 
        # Extract capital letters from the definition
        capital_letters = ''.join(char for char in value if char.isupper())
        
        # Check if the acronym letters are in order within the capital letters
        it = iter(capital_letters)
        if not all(char in it for char in key):
            check_invalid_entries.append((key, value))

    if total_pairs == 0:
        return False, "The dictionary is empty."
    
    if total_pairs <= 2:
        return False, "Since the dictionary contains 2 or less potential acronyms, the acronym list will be treated as invalid."
    

    invalid_details = "; ".join([f"{k}: {v}" for k, v in invalid_entries])

    invalid_percentage = 0.65
    invalid_check = len(invalid_entries) / total_pairs
    valid_pairs = len(acronym_dict) - len(check_invalid_entries)
    valid_percentage = valid_pairs / total_pairs
   
    if (valid_percentage >= threshold) and (invalid_check <=invalid_percentage):
        return True, "The acronym list has been extracted correctly."
    else:
        return False, (
            f"The acronym list did not meet the {threshold * 100}% validity threshold. "
            f"Validity: {valid_percentage * 100:.2f}%. "
            f"Invalid entries: {invalid_details}"
        )
    
def process_acronym_table(html_content: str) -> Dict[str, str]:
    """
    Extract acronym list from HTML table content.

    :param html_content: HTML content containing the table.
    :return: Dictionary of acronyms and their meanings.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    table = soup.find('table')

    acronym_dict = {}
    if table:
        for row in table.find_all('tr')[1:]:  # Skip the header row
            cells = row.find_all('td')
            if len(cells) == 2:
                acronym = cells[0].get_text(strip=True)
                meaning = cells[1].get_text(strip=True)
                acronym_dict[acronym] = meaning
    return acronym_dict

def replace_acronyms(elements, logger: logging.Logger):
    """
    Replace acronyms in page_content of elements with their definitions, store used acronyms in metadata.
    If an acronym is defined (definition (acronym)), remove the acronym and parentheses.

    :param elements: List of elements containing metadata and content.
    :param logger: Logger for logging information and errors.
    :return: List of elements with acronyms replaced in page_content.
    """
    acronym_dicts = {}
    elements_to_process = []

    # Separate elements with acronym dictionaries and elements to process
    for element in elements:
        acronym_dict = element.metadata.get('acronym_list')
        if acronym_dict:
            acronym_dicts.update(acronym_dict)
        else:
            elements_to_process.append(element)

    if not acronym_dicts:
        logger.debug(f"'acronym_list' is empty for document '{element.metadata['filename']}'.")
        return


    # Compile the regex patterns once using all acronym keys and values
    ## NEED TO REFINE THIS REGEX PATTERN TO NOT REPLACE ACRONYMS NEXT TO HYPHENS '-' such as SEP-02-1
    pattern_acronym = re.compile(r'\b(' + '|'.join(map(re.escape, acronym_dicts.keys())) + r')\b')
    pattern_definition = re.compile(r'\b(' + '|'.join(map(lambda x: re.escape(x.replace(' and ', ' & ')), acronym_dicts.values())) + r')\s*\(\b([^)\s]+)\b\)')


    for element in elements_to_process:
        key_terms = []

        def replace_definition(match):
            definition = match.group(1)
            acronym = match.group(2)
            if acronym in acronym_dicts and acronym_dicts[acronym].replace(' and ', ' & ') == definition.replace(' and ', ' & '):
                key_terms.append(definition)
                logger.debug(f"Definition '{definition}' matched with acronym '{acronym}'.")
                return definition
            return match.group(0)

        def replace_acronym(match):
            acronym = match.group(0)
            replacement = acronym_dicts[acronym]
            key_terms.append(replacement)
            logger.debug(f"Acronym '{acronym}' replaced with '{replacement}'.")
            return replacement

        try:
            # First, replace definitions with acronyms
            element.page_content = pattern_definition.sub(replace_definition, element.page_content)
            # Then, replace standalone acronyms
            element.page_content = pattern_acronym.sub(replace_acronym, element.page_content)
            element.metadata['key_terms'] = list(set(key_terms))  # Store unique key terms
            logger.info(f"Acronyms replaced in element {id(element)} in {element.metadata['filename']}")
        except Exception as e:
            logger.error(f"Error replacing acronyms in element {id(element)} in {element.metadata['filename']}: {e}")

    return elements_to_process

def process_text_as_html_element(element: Any, logger: logging.Logger) -> Dict[str, Any]:
    """
    Process a single HTML element.

    :param element: Element containing metadata and content.
    :param logger: Logger for logging information and errors.
    :return: Processed element metadata and content.
    """
    html_content = element.metadata.get('text_as_html', None)
    page_content = element.page_content

    if html_content is not None:
        soup = BeautifulSoup(html_content, 'html.parser')
        visible_texts = soup.stripped_strings
        visible_text = ' '.join(visible_texts)
        
        if visible_text.strip():
            acronym_dict = process_acronym_table(html_content)
            is_valid, validation_message = test_acronym_extraction(acronym_dict)

            if is_valid:
                element.metadata['acronym_list'] = acronym_dict
                element.metadata['text_as_html'] = None

                logger.info(f"Valid acronym list found for element {id(element)} in {element.metadata['filename']}")
            else:
                logger.info(f"No valid acronym list found for {id(element)} in {element.metadata['filename']}")
                
        elif not page_content.strip():
            logger.warning(f"page_content is empty and html contains no visible text in text_as_html metadata for element {id(element)} in {element.metadata['filename']}")
            # log_and_delete_element(element, logger)
            
    elif not page_content.strip():
        logger.warning(f"page_content is empty and no text_as_html metadata for element {id(element)} in {element.metadata['filename']} - Deleting element")
        # log_and_delete_element(element, logger)

    return element.metadata

def process_acronym_text_as_html(
        elements: List[Any], 
        logger: logging.Logger = None
        ) -> Tuple[List[Any], List[Dict[str, Any]]]:
    
    logger = logger if logger else logging.getLogger(__name__)
    
    html_processing_output = []

    logger.info(f"Starting process_acronym_text_as_html for {elements[0].metadata['filename']} with {len(elements)} elements")

    try:
        for element in elements:
        
            processed_metadata = process_text_as_html_element(element, logger)
            html_processing_output.append(processed_metadata)

    except Exception as e:
        logger.error(f"Error processing acronym as HTML for element {id(element)} in {element.metadata['filename']}: {e}")

    try:
        replace_acronyms(elements, logger)

    except Exception as e:
        logger.error(f"Error processing replacing acronyms with acronym_list for element {id(element)} in {element.metadata['filename']}: {e}")

    logger.info(f"Finished process_acronym_text_as_html for {element.metadata['filename']}")
    
    return elements, html_processing_output

```

```YML
# docker-compose.ingest.yml

services:
  app:
    build:
      context: .
      dockerfile: Dockerfile.ingest
    container_name: Ingest
    env_file:
      - ./.env
    ports:
      - 8000:8000
    networks:
      - drsearch_docker_drsearch-net
    volumes:
      - "./docs:/app/docs"
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    develop:
      watch:
        - path: partition_pdf_and_docx_Final5.py
          action: sync+restart
          target: /app/partition_pdf_and_docx_Final5.py
        - path: run_ingest.py
          action: sync+restart
          target: /app/run_ingest.py
        - path: /static
          action: sync+restart
          target: /app/static
        - path: ingestion_utilities.py
          action: sync+restart
          target: /app/ingestion_utilities.py
        - path: main.py
          action: sync+restart
          target: /app/main.py
        - path: Format_HTML_Table.py
          action: sync+restart
          target: /app/Format_HTML_Table.py
        - path: ingest_docs.py
          action: sync+restart
          target: /app/ingest_docs.py
        - path: HTML_Processing.py
          action: sync+restart
          target: /app/HTML_Processing.py
        - path: document_filter.py
          action: sync+restart
          target: /app/document_filter.py
        - path: Get_Docs_From_EmPower_with_DocViewer.py
          action: sync+restart
          target: /app/Get_Docs_From_EmPower_with_DocViewer.py

networks:
  drsearch_docker_drsearch-net:
    external: true

```

```Dockerfile
#Dockerfile.ingest

##############################
# STAGE 1: Base Environment
##############################
FROM python:3.11-slim as python-base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    POETRY_VERSION=1.8.5 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1 \
    PYSETUP_PATH="/opt/pysetup" \
    VENV_PATH="/opt/pysetup/.venv"

# Add Poetry and venv to PATH
ENV PATH="$POETRY_HOME/bin:$VENV_PATH/bin:$PATH"

##############################
# STAGE 2: Builder
##############################
FROM python-base as builder


# 2. Install build tools and Poetry
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    build-essential gcc g++ curl unzip \
    libpq-dev unixodbc-dev \
    libtesseract-dev poppler-utils texlive-xetex pandoc \
    && rm -rf /var/lib/apt/lists/* 

# Register custom CA certificates
COPY CA_certificates/ /usr/local/share/ca-certificates/
RUN find /usr/local/share/ca-certificates/ -type f \( -iname "*.pem" -o -iname "*.cer" \) -exec sh -c 'mv "$0" "${0%.*}.crt"' {} \; \
 && update-ca-certificates    

RUN curl -sSL https://install.python-poetry.org | python3 - \
    && poetry --version 

# Set working directory
WORKDIR $PYSETUP_PATH

# Copy dependency definitions
COPY pyproject.toml poetry.lock* ./

# Install runtime dependencies only
RUN --mount=type=cache,target=/root/.cache \
    poetry install --only main --no-root

# Copy full application code
WORKDIR /app
COPY . .

# Extract cached resources if provided
COPY .cache.zip /root/.cache.zip
RUN unzip /root/.cache.zip -d /root && rm /root/.cache.zip

##############################
# STAGE 3: Runtime
##############################
FROM python-base as production

ENV FASTAPI_ENV=production \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
    EP_PATH_DOCKER=/app/docs

# Install minimal runtime deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr poppler-utils texlive-xetex pandoc \
    libgl1 libglib2.0-0 unixodbc unzip ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Register custom CA certificates
COPY CA_certificates/ /usr/local/share/ca-certificates/
RUN find /usr/local/share/ca-certificates/ -type f \( -iname "*.pem" -o -iname "*.cer" \) -exec sh -c 'mv "$0" "${0%.*}.crt"' {} \; \
 && update-ca-certificates

# Set app working directory
WORKDIR /app

# Copy virtualenv and installed deps from builder
COPY --from=builder /opt/pysetup /opt/pysetup

# Copy application code
COPY --from=builder /app /app
COPY --from=builder /root/.cache /root/.cache

# Include NLTK data
COPY nltk_data /usr/local/share/nltk_data

# Patch library files (not recommended long-term, but kept per request)
COPY Modified_Unstructured_Library_Files/file_download.py \
     /opt/pysetup/.venv/lib/python3.11/site-packages/huggingface_hub/file_download.py
COPY Modified_Unstructured_Library_Files/tables.py \
     /opt/pysetup/.venv/lib/python3.11/site-packages/unstructured_inference/models/tables.py

# Create writable log file
RUN touch /app/_RUN_INFO_WARNINGS_AND_ERRORS.txt && chmod 666 /app/_RUN_INFO_WARNINGS_AND_ERRORS.txt

# Default command: run FastAPI app with uvicorn
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```


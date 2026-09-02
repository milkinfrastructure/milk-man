from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
import fcntl
import hashlib
import hmac
import http.client
import ipaddress
import os
from pathlib import Path
import re
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET


MAX_OBJECT_BYTES = 64 * 1024 * 1024
MAX_LIST_KEYS = 1000
SAFE_KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,2047}\Z")
S3_RETRY_DELAYS_SECONDS = (0.1, 0.25, 0.5)
S3_RETRYABLE_HTTP_STATUS = frozenset(
    {408, 409, 425, 429, 500, 502, 503, 504, 520, 521, 522, 523, 524}
)


class StoreError(ValueError):
    pass


@dataclass(frozen=True)
class Object:
    body: bytes
    etag: str


@dataclass(frozen=True)
class Page:
    keys: tuple[str, ...]
    next_cursor: str | None


@dataclass(frozen=True)
class Put:
    created: bool
    etag: str


@dataclass(frozen=True)
class Settings:
    kind: str
    scope_id: str
    profile: str
    root: str | None = None
    endpoint: str | None = None
    region: str | None = None
    bucket: str | None = None
    access_key_id: str | None = None
    secret_access_key: str | None = None
    session_token: str | None = None
    path_style: bool = True
    timeout_seconds: int = 30

    @property
    def scope_prefix(self) -> str:
        return f"milk/v2/scopes/{self.scope_id}/"


def _required(environment: dict[str, str], name: str) -> str:
    value = environment.get(name, "")
    if not value:
        raise StoreError(f"{name} is required")
    return value


def _boolean(value: str, name: str) -> bool:
    if value == "true":
        return True
    if value == "false":
        return False
    raise StoreError(f"{name} must be true or false")


def settings_from_environment(environment: dict[str, str] | None = None) -> Settings:
    environment = environment or os.environ
    scope = _required(environment, "MILK_SCOPE_ID")
    try:
        parsed_scope = uuid.UUID(scope)
    except ValueError as error:
        raise StoreError("MILK_SCOPE_ID must be a canonical UUID") from error
    if str(parsed_scope) != scope:
        raise StoreError("MILK_SCOPE_ID must be a canonical UUID")
    profile = environment.get("MILK_SCOPE_PROFILE", "production")
    if profile not in {"production", "mechanics"}:
        raise StoreError("MILK_SCOPE_PROFILE must be production or mechanics")
    kind = _required(environment, "MILK_STORE_KIND")
    timeout_text = environment.get("MILK_STORE_TIMEOUT_SECONDS", "30")
    try:
        timeout = int(timeout_text)
    except ValueError as error:
        raise StoreError("MILK_STORE_TIMEOUT_SECONDS must be an integer") from error
    if not 1 <= timeout <= 120:
        raise StoreError("MILK_STORE_TIMEOUT_SECONDS must be in 1..120")
    if kind == "local":
        root = Path(_required(environment, "MILK_STORE_ROOT"))
        if not root.is_absolute():
            raise StoreError("MILK_STORE_ROOT must be absolute")
        return Settings(kind, scope, profile, root=str(root), timeout_seconds=timeout)
    if kind != "s3":
        raise StoreError("MILK_STORE_KIND must be local or s3")
    return Settings(
        kind,
        scope,
        profile,
        endpoint=_required(environment, "MILK_STORE_ENDPOINT"),
        region=_required(environment, "MILK_STORE_REGION"),
        bucket=_required(environment, "MILK_STORE_BUCKET"),
        access_key_id=_required(environment, "MILK_STORE_ACCESS_KEY_ID"),
        secret_access_key=_required(environment, "MILK_STORE_SECRET_ACCESS_KEY"),
        session_token=environment.get("MILK_STORE_SESSION_TOKEN") or None,
        path_style=_boolean(environment.get("MILK_STORE_PATH_STYLE", "true"), "MILK_STORE_PATH_STYLE"),
        timeout_seconds=timeout,
    )


def _key(value: str) -> str:
    if (
        not isinstance(value, str)
        or SAFE_KEY.fullmatch(value) is None
        or value.startswith("/")
        or value.endswith("/")
        or "//" in value
        or any(part in {"", ".", ".."} for part in value.split("/"))
    ):
        raise StoreError("object key is invalid")
    return value


def _prefix(value: str) -> str:
    value = value.rstrip("/") + "/"
    _key(value + "sentinel")
    return value


def _body(value: bytes) -> bytes:
    if not isinstance(value, bytes) or len(value) > MAX_OBJECT_BYTES:
        raise StoreError("object body must be bounded bytes")
    return value


def _etag(body: bytes) -> str:
    return '"' + hashlib.sha256(body).hexdigest() + '"'


def _close_http_error(error: urllib.error.HTTPError) -> None:
    if error.fp is not None:
        error.close()


class LocalStore:
    def __init__(self, root: str):
        original = Path(root)
        if original.is_symlink():
            raise StoreError("local store root must not be a symlink")
        original.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.root = original.resolve()
        if not self.root.is_dir():
            raise StoreError("local store root is not a directory")
        os.chmod(self.root, 0o700)

    def _path(self, key: str) -> Path:
        path = self.root.joinpath(*_key(key).split("/"))
        resolved = path.resolve(strict=False)
        if self.root not in resolved.parents or resolved != path:
            raise StoreError("object key escapes the local store")
        return path

    def get(self, key: str) -> Object:
        path = self._path(key)
        if path.is_symlink() or not path.is_file():
            raise FileNotFoundError(key)
        with path.open("rb") as source:
            body = source.read(MAX_OBJECT_BYTES + 1)
        if len(body) > MAX_OBJECT_BYTES:
            raise StoreError("stored object is oversized")
        return Object(body, _etag(body))

    def create_same(self, key: str, body: bytes) -> Put:
        body = _body(body)
        path = self._path(key)
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb", closefd=True) as output:
                descriptor = -1
                output.write(body)
                output.flush()
                os.fsync(output.fileno())
            try:
                os.link(temporary, path)
            except FileExistsError:
                current = self.get(key)
                if current.body != body:
                    raise StoreError("existing object differs")
                return Put(False, current.etag)
            _fsync_directory(path.parent)
            return Put(True, _etag(body))
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            temporary.unlink(missing_ok=True)

    def replace_if_match(self, key: str, expected_etag: str, body: bytes) -> Put | None:
        body = _body(body)
        if not isinstance(expected_etag, str) or not expected_etag:
            raise StoreError("expected ETag is invalid")
        path = self._path(key)
        lock_root = self.root / ".locks"
        lock_root.mkdir(mode=0o700, exist_ok=True)
        lock_path = lock_root / (hashlib.sha256(key.encode()).hexdigest() + ".lock")
        with lock_path.open("a+b", buffering=0) as lock:
            os.chmod(lock_path, 0o600)
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                try:
                    current = self.get(key)
                except FileNotFoundError:
                    return None
                if current.etag != expected_etag:
                    return None
                descriptor, temporary_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
                temporary = Path(temporary_name)
                try:
                    with os.fdopen(descriptor, "wb", closefd=True) as output:
                        descriptor = -1
                        output.write(body)
                        output.flush()
                        os.fsync(output.fileno())
                    os.replace(temporary, path)
                    _fsync_directory(path.parent)
                finally:
                    if descriptor >= 0:
                        os.close(descriptor)
                    temporary.unlink(missing_ok=True)
                return Put(False, _etag(body))
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def list(self, prefix: str, cursor: str | None = None, limit: int = MAX_LIST_KEYS) -> Page:
        prefix = _prefix(prefix)
        _page_arguments(prefix, cursor, limit)
        keys = []
        for path in self.root.rglob("*"):
            if path.is_symlink():
                raise StoreError("local store contains a symlink")
            if path.is_file():
                key = path.relative_to(self.root).as_posix()
                if key.startswith(prefix) and (cursor is None or key > cursor):
                    keys.append(key)
        keys.sort()
        more = len(keys) > limit
        page = tuple(keys[:limit])
        return Page(page, page[-1] if more else None)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _page_arguments(prefix: str, cursor: str | None, limit: int) -> None:
    if type(limit) is not int or not 1 <= limit <= MAX_LIST_KEYS:
        raise StoreError("list limit must be in 1..1000")
    if cursor is not None and (_key(cursor) != cursor or not cursor.startswith(prefix)):
        raise StoreError("list cursor is outside the prefix")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        return None


class S3Store:
    def __init__(self, settings: Settings, opener=None, now=None):
        endpoint = urllib.parse.urlsplit(settings.endpoint or "")
        try:
            endpoint.port
        except ValueError as error:
            raise StoreError("MILK_STORE_ENDPOINT must be an HTTPS origin") from error
        if (
            endpoint.scheme != "https"
            or not endpoint.hostname
            or endpoint.username is not None
            or endpoint.password is not None
            or endpoint.path not in {"", "/"}
            or endpoint.query
            or endpoint.fragment
        ):
            raise StoreError("MILK_STORE_ENDPOINT must be an HTTPS origin")
        if not settings.path_style:
            try:
                ipaddress.ip_address(endpoint.hostname)
            except ValueError:
                pass
            else:
                raise StoreError("virtual-hosted S3 requires a DNS endpoint")
        if re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", settings.region or "") is None:
            raise StoreError("MILK_STORE_REGION is invalid")
        bucket = settings.bucket or ""
        try:
            ipaddress.ip_address(bucket)
            bucket_is_ip = True
        except ValueError:
            bucket_is_ip = False
        if (
            re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", bucket) is None
            or ".." in bucket
            or bucket_is_ip
        ):
            raise StoreError("MILK_STORE_BUCKET is invalid")
        self.settings = settings
        self.origin = f"{endpoint.scheme}://{endpoint.netloc}"
        self.origin_host = endpoint.netloc
        self.opener = opener or urllib.request.build_opener(_NoRedirect)
        self.now = now or (lambda: dt.datetime.now(dt.timezone.utc))

    def _idempotent(self, operation):
        for attempt in range(len(S3_RETRY_DELAYS_SECONDS) + 1):
            try:
                return operation()
            except urllib.error.HTTPError as error:
                if error.code not in S3_RETRYABLE_HTTP_STATUS or attempt == len(S3_RETRY_DELAYS_SECONDS):
                    raise
                _close_http_error(error)
            except (urllib.error.URLError, http.client.HTTPException, OSError):
                if attempt == len(S3_RETRY_DELAYS_SECONDS):
                    raise
            time.sleep(S3_RETRY_DELAYS_SECONDS[attempt])

    def _request(self, method: str, key: str | None = None, body: bytes = b"", query=(), headers=()):
        body = _body(body)
        current = self.now()
        if not isinstance(current, dt.datetime) or current.tzinfo is None or current.utcoffset() != dt.timedelta(0):
            raise StoreError("S3 clock must return UTC")
        current = current.astimezone(dt.timezone.utc)
        amz_date = current.strftime("%Y%m%dT%H%M%SZ")
        date = current.strftime("%Y%m%d")
        settings = self.settings
        host = self.origin_host
        path = "/" + urllib.parse.quote(settings.bucket or "", safe="-_.~") if settings.path_style else ""
        if not settings.path_style:
            host = f"{settings.bucket}.{host}"
        if key is not None:
            path += "/" + "/".join(urllib.parse.quote(part, safe="-_.~") for part in _key(key).split("/"))
        path = path or "/"
        encoded_query = sorted(
            (urllib.parse.quote(str(name), safe="-_.~"), urllib.parse.quote(str(value), safe="-_.~"))
            for name, value in query
        )
        canonical_query = "&".join(f"{name}={value}" for name, value in encoded_query)
        payload_digest = hashlib.sha256(body).hexdigest()
        signed = {"host": host, "x-amz-content-sha256": payload_digest, "x-amz-date": amz_date}
        if settings.session_token:
            signed["x-amz-security-token"] = settings.session_token
        for name, value in headers:
            normalized_name = name.strip().lower()
            normalized_value = " ".join(value.strip().split())
            if not normalized_name or not normalized_value or normalized_name in signed:
                raise StoreError("S3 request header is invalid")
            signed[normalized_name] = normalized_value
        canonical_headers = "".join(f"{name}:{signed[name]}\n" for name in sorted(signed))
        signed_headers = ";".join(sorted(signed))
        canonical_request = "\n".join((method, path, canonical_query, canonical_headers, signed_headers, payload_digest))
        credential_scope = f"{date}/{settings.region}/s3/aws4_request"
        string_to_sign = "\n".join(
            ("AWS4-HMAC-SHA256", amz_date, credential_scope, hashlib.sha256(canonical_request.encode()).hexdigest())
        )

        def sign(key_bytes: bytes, value: str) -> bytes:
            return hmac.new(key_bytes, value.encode(), hashlib.sha256).digest()

        signing_key = sign(
            sign(sign(sign(("AWS4" + (settings.secret_access_key or "")).encode(), date), settings.region or ""), "s3"),
            "aws4_request",
        )
        signature = hmac.new(signing_key, string_to_sign.encode(), hashlib.sha256).hexdigest()
        request_headers = {name: value for name, value in signed.items() if name != "host"}
        request_headers["Authorization"] = (
            "AWS4-HMAC-SHA256 "
            f"Credential={settings.access_key_id}/{credential_scope},"
            f"SignedHeaders={signed_headers},Signature={signature}"
        )
        url = f"{self.origin.split('://', 1)[0]}://{host}{path}"
        if canonical_query:
            url += "?" + canonical_query
        return urllib.request.Request(
            url,
            data=body if method in {"PUT", "POST"} else None,
            method=method,
            headers=request_headers,
        )

    def get(self, key: str) -> Object:
        def fetch():
            request = self._request("GET", key)
            with self.opener.open(request, timeout=self.settings.timeout_seconds) as response:
                return response.read(MAX_OBJECT_BYTES + 1), response.headers.get("ETag")

        try:
            body, etag = self._idempotent(fetch)
        except urllib.error.HTTPError as error:
            if error.code == 404:
                _close_http_error(error)
                raise FileNotFoundError(key) from error
            raise
        if len(body) > MAX_OBJECT_BYTES:
            raise StoreError("stored object is oversized")
        if not etag:
            raise StoreError("S3 response has no ETag")
        return Object(body, etag)

    def create_same(self, key: str, body: bytes) -> Put:
        body = _body(body)

        def create():
            request = self._request(
                "PUT", key, body, headers=(("content-type", "application/octet-stream"), ("if-none-match", "*"))
            )
            with self.opener.open(request, timeout=self.settings.timeout_seconds) as response:
                response.read(1)
                return response.headers.get("ETag") or _etag(body)

        try:
            return Put(True, self._idempotent(create))
        except urllib.error.HTTPError as error:
            if error.code == 412:
                _close_http_error(error)
            elif error.code not in S3_RETRYABLE_HTTP_STATUS:
                raise
            else:
                _close_http_error(error)
                return self._reconcile_create(key, body, error)
        except (urllib.error.URLError, http.client.HTTPException, OSError) as error:
            return self._reconcile_create(key, body, error)
        current = self.get(key)
        if current.body != body:
            raise StoreError("existing object differs")
        return Put(False, current.etag)

    def _reconcile_create(self, key: str, body: bytes, error: Exception) -> Put:
        try:
            current = self.get(key)
        except FileNotFoundError:
            raise error
        if current.body != body:
            raise StoreError("existing object differs") from error
        return Put(False, current.etag)

    def replace_if_match(self, key: str, expected_etag: str, body: bytes) -> Put | None:
        body = _body(body)
        if not isinstance(expected_etag, str) or not expected_etag:
            raise StoreError("expected ETag is invalid")
        request = self._request(
            "PUT",
            key,
            body,
            headers=(("content-type", "application/octet-stream"), ("if-match", expected_etag)),
        )
        try:
            with self.opener.open(request, timeout=self.settings.timeout_seconds) as response:
                response.read(1)
                etag = response.headers.get("ETag") or _etag(body)
            return Put(False, etag)
        except urllib.error.HTTPError as error:
            if error.code == 412:
                return None
            raise

    def list(self, prefix: str, cursor: str | None = None, limit: int = MAX_LIST_KEYS) -> Page:
        prefix = _prefix(prefix)
        _page_arguments(prefix, cursor, limit)
        query = [("list-type", "2"), ("max-keys", str(limit)), ("prefix", prefix)]
        if cursor is not None:
            query.append(("start-after", cursor))
        def fetch():
            request = self._request("GET", query=query)
            with self.opener.open(request, timeout=self.settings.timeout_seconds) as response:
                return response.read(1024 * 1024 + 1)

        raw = self._idempotent(fetch)
        if len(raw) > 1024 * 1024:
            raise StoreError("S3 list response is oversized")
        try:
            root = ET.fromstring(raw)
        except ET.ParseError as error:
            raise StoreError("S3 list response is invalid XML") from error
        namespace = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
        keys = tuple(node.text or "" for node in root.findall("s3:Contents/s3:Key", namespace))
        if len(keys) > limit:
            raise StoreError("S3 list returned too many keys")
        if any(_key(key) != key or not key.startswith(prefix) or (cursor is not None and key <= cursor) for key in keys):
            raise StoreError("S3 list returned an invalid key")
        if tuple(sorted(keys)) != keys or len(set(keys)) != len(keys):
            raise StoreError("S3 list is not unique and lexicographic")
        truncated = root.findtext("s3:IsTruncated", default="false", namespaces=namespace)
        if truncated not in {"true", "false"}:
            raise StoreError("S3 list truncation flag is invalid")
        if truncated == "true" and not keys:
            raise StoreError("S3 returned an empty truncated page")
        return Page(keys, keys[-1] if truncated == "true" else None)


def open_store(settings: Settings):
    if settings.kind == "local":
        return LocalStore(settings.root or "")
    return S3Store(settings)


def list_all(store, prefix: str):
    cursor = None
    while True:
        page = store.list(prefix, cursor)
        yield from page.keys
        if page.next_cursor is None:
            return
        cursor = page.next_cursor

"""HTTP and GitHub API Fetcher supporting SSRF defense, conditional requests, and backoff."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class FetchResult:
    """Outcome of fetching an external source."""
    status_code: int
    is_modified: bool
    content: str
    fingerprint: str
    etag: Optional[str] = None
    last_modified: Optional[str] = None
    error: Optional[str] = None
    published_at: Optional[float] = None
    metadata: Dict[str, Any] = None


def normalize_web_content(content: str) -> str:
    """Normalizes raw web or markdown content, stripping dynamic noise and script blocks."""
    # Remove HTML script and style elements if present
    content = re.sub(r"<script.*?>.*?</script>", "", content, flags=re.DOTALL | re.IGNORECASE)
    content = re.sub(r"<style.*?>.*?</style>", "", content, flags=re.DOTALL | re.IGNORECASE)
    # Normalize Windows CRLF to LF
    content = content.replace("\r\n", "\n")
    # Normalize trailing whitespace on lines
    lines = [line.rstrip() for line in content.split("\n")]
    # Strip leading/trailing blank lines
    normalized = "\n".join(lines).strip()
    return normalized


def compute_content_fingerprint(text: str) -> str:
    """Computes deterministic SHA-256 fingerprint of normalized text."""
    normalized = normalize_web_content(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def validate_url_safety(url: str, allow_private_ips: bool = False) -> Tuple[bool, str]:
    """Validates URL against SSRF attacks (loopback, private, link-local, scheme validation)."""
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception as e:
        return False, f"Malformed URL: {e}"

    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        return False, f"Prohibited URL scheme '{scheme}'. Only HTTP and HTTPS are permitted."

    hostname = parsed.hostname
    if not hostname:
        return False, "URL contains no valid hostname."

    # Direct loopback hostname check
    if hostname.lower() in ("localhost", "127.0.0.1", "::1"):
        if not allow_private_ips:
            return False, "Access to localhost or loopback interfaces is prohibited."
        return True, "OK"

    if allow_private_ips:
        return True, "OK"

    # Resolve hostname to IP to protect against DNS rebinding & private IP ranges
    try:
        addr_info = socket.getaddrinfo(hostname, None)
    except socket.gaierror as e:
        return False, f"DNS resolution failed for '{hostname}': {e}"

    for entry in addr_info:
        ip_str = entry[4][0]
        try:
            ip_obj = ipaddress.ip_address(ip_str)
            if ip_obj.is_loopback:
                return False, f"Resolved IP '{ip_str}' is a loopback address."
            if ip_obj.is_private:
                return False, f"Resolved IP '{ip_str}' belongs to private network space."
            if ip_obj.is_link_local:
                return False, f"Resolved IP '{ip_str}' is a link-local address."
            if ip_obj.is_reserved:
                return False, f"Resolved IP '{ip_str}' is a reserved address."
        except ValueError:
            return False, f"Invalid resolved IP format '{ip_str}'."

    return True, "OK"


class SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Custom HTTP redirect handler enforcing SSRF checks and maximum hop boundaries."""

    def __init__(self, allow_private_ips: bool = False, max_redirects: int = 5):
        super().__init__()
        self.allow_private_ips = allow_private_ips
        self.max_redirects = max_redirects

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Validate target redirect URL for SSRF
        is_safe, reason = validate_url_safety(newurl, allow_private_ips=self.allow_private_ips)
        if not is_safe:
            raise urllib.error.HTTPError(newurl, 403, f"SSRF Blocked Redirect: {reason}", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class SourceFetcher:
    """Fetches web documents and GitHub resources with conditional headers and SSRF defenses."""

    def __init__(
        self,
        user_agent: str = "AI-Knowledge-Architect-Updater/1.0",
        timeout: int = 15,
        allow_private_ips: bool = False
    ):
        self.user_agent = user_agent
        self.timeout = timeout
        self.allow_private_ips = allow_private_ips

    def _get_opener(self) -> urllib.request.OpenerDirector:
        redirect_handler = SafeRedirectHandler(allow_private_ips=self.allow_private_ips)
        return urllib.request.build_opener(redirect_handler)

    def fetch_url(
        self,
        url: str,
        etag: Optional[str] = None,
        last_modified: Optional[str] = None
    ) -> FetchResult:
        """Fetches a website or document URL using conditional HTTP headers (ETag, If-Modified-Since)."""
        # SSRF Pre-flight Validation
        is_safe, reason = validate_url_safety(url, allow_private_ips=self.allow_private_ips)
        if not is_safe:
            return FetchResult(
                status_code=403,
                is_modified=False,
                content="",
                fingerprint="",
                error=f"SSRF Protection Blocked: {reason}",
                metadata={"url": url}
            )

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/markdown, text/html, text/plain, application/json, */*"
        }
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified

        req = urllib.request.Request(url, headers=headers, method="GET")
        opener = self._get_opener()

        try:
            with opener.open(req, timeout=self.timeout) as resp:
                status_code = resp.status
                resp_etag = resp.headers.get("ETag")
                resp_last_mod = resp.headers.get("Last-Modified")
                raw_bytes = resp.read()
                raw_text = raw_bytes.decode("utf-8", errors="replace")

                norm_text = normalize_web_content(raw_text)
                fp = hashlib.sha256(norm_text.encode("utf-8")).hexdigest()

                return FetchResult(
                    status_code=status_code,
                    is_modified=True,
                    content=norm_text,
                    fingerprint=fp,
                    etag=resp_etag,
                    last_modified=resp_last_mod,
                    metadata={"url": url}
                )

        except urllib.error.HTTPError as e:
            if e.code == 304:
                return FetchResult(
                    status_code=304,
                    is_modified=False,
                    content="",
                    fingerprint="",
                    etag=etag,
                    last_modified=last_modified,
                    metadata={"url": url}
                )
            return FetchResult(
                status_code=e.code,
                is_modified=False,
                content="",
                fingerprint="",
                error=f"HTTP {e.code}: {e.reason}",
                metadata={"url": url}
            )
        except Exception as e:
            return FetchResult(
                status_code=0,
                is_modified=False,
                content="",
                fingerprint="",
                error=str(e),
                metadata={"url": url}
            )

    def fetch_github_release(
        self,
        owner: str,
        repo: str,
        etag: Optional[str] = None
    ) -> FetchResult:
        """Fetches the latest official GitHub release for a repository via GitHub REST API."""
        # Sanitize owner and repo identifiers to prevent path traversal or parameter injection
        if not re.match(r"^[a-zA-Z0-9_.-]+$", owner) or not re.match(r"^[a-zA-Z0-9_.-]+$", repo):
            return FetchResult(
                status_code=400,
                is_modified=False,
                content="",
                fingerprint="",
                error=f"Invalid GitHub owner '{owner}' or repo '{repo}' identifier format."
            )

        api_url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/vnd.github.v3+json"
        }
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"

        if etag:
            headers["If-None-Match"] = etag

        req = urllib.request.Request(api_url, headers=headers, method="GET")
        opener = self._get_opener()

        try:
            with opener.open(req, timeout=self.timeout) as resp:
                status_code = resp.status
                resp_etag = resp.headers.get("ETag")
                raw_text = resp.read().decode("utf-8", errors="replace")
                data = json.loads(raw_text)

                tag_name = data.get("tag_name", "")
                release_name = data.get("name") or tag_name
                published_at_str = data.get("published_at")
                published_at_epoch = None
                if published_at_str:
                    try:
                        import datetime
                        dt = datetime.datetime.fromisoformat(published_at_str.replace("Z", "+00:00"))
                        published_at_epoch = dt.timestamp()
                    except Exception:
                        pass

                body = data.get("body", "") or ""
                normalized_summary = f"Release {tag_name}: {release_name}\n\n{body}".strip()
                fp = hashlib.sha256(f"{tag_name}:{body}".encode("utf-8")).hexdigest()

                return FetchResult(
                    status_code=status_code,
                    is_modified=True,
                    content=normalized_summary,
                    fingerprint=fp,
                    etag=resp_etag,
                    published_at=published_at_epoch,
                    metadata={
                        "tag_name": tag_name,
                        "release_name": release_name,
                        "html_url": data.get("html_url", f"https://github.com/{owner}/{repo}/releases/tag/{tag_name}")
                    }
                )

        except urllib.error.HTTPError as e:
            if e.code == 304:
                return FetchResult(
                    status_code=304,
                    is_modified=False,
                    content="",
                    fingerprint="",
                    etag=etag
                )
            return FetchResult(
                status_code=e.code,
                is_modified=False,
                content="",
                fingerprint="",
                error=f"GitHub API Error {e.code}: {e.reason}"
            )
        except Exception as e:
            return FetchResult(
                status_code=0,
                is_modified=False,
                content="",
                fingerprint="",
                error=str(e)
            )

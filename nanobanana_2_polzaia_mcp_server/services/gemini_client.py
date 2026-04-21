import base64
from dataclasses import dataclass
import json
import logging
import mimetypes
import os
from pathlib import Path
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen
import uuid

from ..config.settings import (
    BaseModelConfig,
    FlashImageConfig,
    GeminiConfig,
    ProImageConfig,
    ServerConfig,
)
from ..core.exceptions import AuthenticationError


@dataclass
class UploadedFileObject:
    """Normalized storage file object."""

    name: str
    uri: str
    mime_type: str | None = None
    size_bytes: int | None = None
    display_name: str | None = None
    state: str | None = None
    create_time: str | None = None
    update_time: str | None = None
    expires_at: str | None = None


@dataclass
class GeneratedContentResponse:
    """Minimal image response compatible with the existing services."""

    generated_images: list[bytes]
    raw: dict[str, Any]


class GeminiClient:
    """Wrapper for Polza media/storage APIs with the legacy GeminiClient interface."""

    def __init__(
        self,
        config: ServerConfig,
        gemini_config: GeminiConfig | BaseModelConfig | FlashImageConfig | ProImageConfig,
    ):
        self.config = config
        self.gemini_config = gemini_config
        self.logger = logging.getLogger(__name__)
        self.base_url = (self.config.gemini_base_url or "https://polza.ai/api").rstrip("/")

        safe_url = self._get_safe_base_url_for_log(self.base_url)
        self._log_auth_method("API Key (Polza API)")
        self.logger.info(f"Using API base URL: {safe_url}")

    @staticmethod
    def _get_safe_base_url_for_log(raw_url: str) -> str:
        """Return a sanitized base URL for logs."""
        parsed = urlsplit(raw_url.strip())
        if parsed.scheme and parsed.hostname:
            host = parsed.hostname
            if parsed.port:
                host = f"{host}:{parsed.port}"
            return f"{parsed.scheme}://{host}"
        return "[invalid-base-url]"

    def _log_auth_method(self, method: str):
        """Log the authentication method in use."""
        self.logger.info(f"Authentication method: {method}")

    def validate_auth(self) -> bool:
        """Validate credentials with a lightweight Polza request."""
        try:
            self._request_json("GET", "/v1/balance")
            return True
        except Exception as e:
            self.logger.error(f"Authentication validation failed: {e}")
            return False

    def create_image_parts(self, images_b64: list[str], mime_types: list[str]) -> list[dict[str, str]]:
        """Convert base64 images to normalized Polza image inputs."""
        if not images_b64 or not mime_types:
            return []

        if len(images_b64) != len(mime_types):
            raise ValueError(
                f"Images and MIME types count mismatch: {len(images_b64)} vs {len(mime_types)}"
            )

        parts = []
        for i, (b64, mime_type) in enumerate(zip(images_b64, mime_types, strict=False)):
            if not b64 or not mime_type:
                self.logger.warning(f"Skipping empty image or MIME type at index {i}")
                continue

            try:
                raw_data = base64.b64decode(b64)
                if len(raw_data) == 0:
                    self.logger.warning(f"Skipping empty image data at index {i}")
                    continue

                normalized_b64 = b64
                if not normalized_b64.startswith("data:"):
                    normalized_b64 = (
                        f"data:{mime_type};base64,{base64.b64encode(raw_data).decode('utf-8')}"
                    )
                parts.append({"type": "base64", "mime_type": mime_type, "data": normalized_b64})
            except Exception as e:
                self.logger.error(f"Failed to process image at index {i}: {e}")
                raise ValueError(f"Invalid image data at index {i}: {e}") from e
        return parts

    def generate_content(
        self,
        contents: list,
        config: dict[str, Any] | None = None,
        aspect_ratio: str | None = None,
        **kwargs,
    ) -> GeneratedContentResponse:
        """Generate content through Polza and return normalized image bytes."""
        try:
            kwargs.pop("request_options", None)
            filtered_config = self._filter_parameters(config or {})
            prompt, images = self._normalize_contents(contents)

            payload: dict[str, Any] = {
                "model": self.gemini_config.model_name,
                "input": {
                    "prompt": prompt,
                    "output_format": getattr(self.gemini_config, "default_image_format", "png"),
                },
                "async": False,
            }

            if images:
                payload["input"]["images"] = images
            if aspect_ratio:
                payload["input"]["aspect_ratio"] = aspect_ratio

            image_resolution = self._map_resolution_to_polza(filtered_config.get("resolution"))
            if image_resolution:
                payload["input"]["image_resolution"] = image_resolution

            if self.config.polza_external_user_id:
                payload["user"] = self.config.polza_external_user_id

            response = self._request_json("POST", "/v1/media", payload)
            if not isinstance(response, dict):
                raise RuntimeError(f"Unexpected media response type: {type(response).__name__}")

            final_response = self._resolve_media_response(response)
            image_urls = self._extract_output_urls(final_response)
            generated_images = [self._download_bytes(url) for url in image_urls]

            return GeneratedContentResponse(generated_images=generated_images, raw=final_response)

        except Exception as e:
            self.logger.error(f"Polza API error: {e}")
            raise

    def _filter_parameters(self, config: dict[str, Any]) -> dict[str, Any]:
        """Keep only parameters still relevant after the Polza migration."""
        if not config:
            return {}

        filtered = {}
        for param in ["temperature", "top_p", "top_k", "max_output_tokens", "resolution"]:
            if param in config:
                filtered[param] = config[param]
        return filtered

    def extract_images(self, response: GeneratedContentResponse) -> list[bytes]:
        """Extract image bytes from the normalized response object."""
        return list(getattr(response, "generated_images", []))

    def upload_file(self, file_path: str, _display_name: str | None = None) -> UploadedFileObject:
        """Upload file to Polza Storage API."""
        mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
        response = self._request_multipart_upload(
            "/v1/storage/upload",
            file_path=file_path,
            fields={"storagePolicy": "TEMP_UPLOAD"},
        )
        return self._to_uploaded_file(
            response,
            fallback_name=os.path.basename(file_path),
            mime_type=mime_type,
        )

    def get_file_metadata(self, file_name: str) -> UploadedFileObject:
        """Get file metadata from Polza Storage API."""
        normalized_id = self._normalize_file_id(file_name)
        response = self._request_json("GET", f"/v1/storage/files/{normalized_id}")
        if not isinstance(response, dict):
            raise RuntimeError(f"Unexpected storage response type: {type(response).__name__}")
        return self._to_uploaded_file(response)

    def list_files(self) -> list[UploadedFileObject]:
        """List files from Polza Storage API."""
        response = self._request_json("GET", "/v1/storage/files?limit=100")
        if not isinstance(response, list):
            return []
        return [self._to_uploaded_file(item) for item in response if isinstance(item, dict)]

    def delete_file(self, file_name: str) -> dict[str, Any]:
        """Delete file from Polza Storage API."""
        normalized_id = self._normalize_file_id(file_name)
        response = self._request_json("DELETE", f"/v1/storage/files/{normalized_id}")
        if isinstance(response, dict):
            return response
        return {"success": True}

    def _normalize_contents(self, contents: list[Any]) -> tuple[str, list[dict[str, str]]]:
        text_parts: list[str] = []
        images: list[dict[str, str]] = []

        for item in contents:
            if isinstance(item, str):
                stripped = item.strip()
                if stripped:
                    text_parts.append(stripped)
                continue

            if not isinstance(item, dict):
                continue

            if "file_data" in item:
                file_data = item["file_data"] or {}
                uri = file_data.get("uri")
                if uri:
                    images.append({"type": "url", "data": uri})
                continue

            item_type = item.get("type")
            data = item.get("data")
            if item_type in {"url", "base64"} and data:
                images.append({"type": item_type, "data": data})

        prompt = "\n\n".join(text_parts).strip()
        if not prompt:
            raise ValueError("Prompt cannot be empty")
        return prompt, images

    def _map_resolution_to_polza(self, resolution: str | None) -> str | None:
        if not resolution:
            return None

        resolution_map = {
            "4k": "4K",
            "2k": "2K",
            "1k": "1K",
        }
        normalized = resolution.strip().lower()
        if normalized in resolution_map:
            return resolution_map[normalized]
        if normalized == "high":
            if isinstance(self.gemini_config, FlashImageConfig):
                return "1K"
            return "2K"
        return None

    def _request_json(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any] | list[Any]:
        if not self.config.gemini_api_key:
            raise AuthenticationError("POLZA_AI_API_KEY is required")

        url = self._build_url(path)
        headers = {"Authorization": f"Bearer {self.config.gemini_api_key}"}
        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = Request(url=url, data=data, headers=headers, method=method)

        try:
            with urlopen(request, timeout=self.gemini_config.request_timeout) as response:
                body = response.read()
        except HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {exc.code} for {url}: {details}") from exc
        except URLError as exc:
            raise RuntimeError(f"Network error for {url}: {exc}") from exc

        if not body:
            return {}
        return json.loads(body.decode("utf-8"))

    def _request_multipart_upload(
        self, path: str, *, file_path: str, fields: dict[str, str] | None = None
    ) -> dict[str, Any]:
        if not self.config.gemini_api_key:
            raise AuthenticationError("POLZA_AI_API_KEY is required")

        fields = fields or {}
        boundary = f"----nanobanana-{uuid.uuid4().hex}"
        file_name = Path(file_path).name
        mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
        file_bytes = Path(file_path).read_bytes()
        parts: list[bytes] = []

        for key, value in fields.items():
            parts.extend(
                [
                    f"--{boundary}\r\n".encode("utf-8"),
                    f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8"),
                    f"{value}\r\n".encode("utf-8"),
                ]
            )

        parts.extend(
            [
                f"--{boundary}\r\n".encode("utf-8"),
                (
                    f'Content-Disposition: form-data; name="file"; filename="{file_name}"\r\n'
                ).encode("utf-8"),
                f"Content-Type: {mime_type}\r\n\r\n".encode("utf-8"),
                file_bytes,
                b"\r\n",
                f"--{boundary}--\r\n".encode("utf-8"),
            ]
        )

        request = Request(
            url=self._build_url(path),
            data=b"".join(parts),
            headers={
                "Authorization": f"Bearer {self.config.gemini_api_key}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.gemini_config.request_timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {exc.code} for upload: {details}") from exc
        except URLError as exc:
            raise RuntimeError(f"Network error during upload: {exc}") from exc

    def _resolve_media_response(self, response: dict[str, Any]) -> dict[str, Any]:
        status = (response.get("status") or "").lower()
        if status == "completed":
            return response
        if status == "failed":
            error = response.get("error") or {}
            raise RuntimeError(error.get("message") or "Media generation failed")

        media_id = response.get("id")
        if not media_id:
            return response
        return self._poll_media_status(media_id)

    def _poll_media_status(self, media_id: str) -> dict[str, Any]:
        deadline = time.time() + self.config.polza_poll_timeout_seconds
        last_response: dict[str, Any] | None = None

        while time.time() < deadline:
            response = self._request_json("GET", f"/v1/media/{media_id}")
            if not isinstance(response, dict):
                raise RuntimeError(f"Unexpected polling response for media {media_id}")

            last_response = response
            status = (response.get("status") or "").lower()
            if status == "completed":
                return response
            if status == "failed":
                error = response.get("error") or {}
                raise RuntimeError(
                    error.get("message") or f"Media generation failed for {media_id}"
                )

            time.sleep(self.config.polza_poll_interval_seconds)

        raise TimeoutError(f"Timed out waiting for media generation {media_id}: {last_response}")

    def _extract_output_urls(self, response: dict[str, Any]) -> list[str]:
        data = response.get("data")
        urls: list[str] = []

        if isinstance(data, dict):
            if isinstance(data.get("url"), str):
                urls.append(data["url"])

            for key in ("urls", "files"):
                value = data.get(key)
                if isinstance(value, list):
                    urls.extend([item for item in value if isinstance(item, str)])

            for key in ("images", "results", "items"):
                value = data.get(key)
                if isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict) and isinstance(item.get("url"), str):
                            urls.append(item["url"])

        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and isinstance(item.get("url"), str):
                    urls.append(item["url"])
                elif isinstance(item, str):
                    urls.append(item)

        if not urls:
            raise RuntimeError(f"No output URLs found in response: {response}")
        return urls

    def _download_bytes(self, url: str) -> bytes:
        request = Request(url=url, method="GET")
        try:
            with urlopen(request, timeout=self.gemini_config.request_timeout) as response:
                return response.read()
        except HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Failed to download generated file {url}: HTTP {exc.code} {details}"
            ) from exc
        except URLError as exc:
            raise RuntimeError(f"Failed to download generated file {url}: {exc}") from exc

    def _build_url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        return urljoin(self.base_url + "/", path.lstrip("/"))

    def _normalize_file_id(self, file_name: str) -> str:
        return file_name.split("/", 1)[1] if file_name.startswith("files/") else file_name

    def _to_uploaded_file(
        self,
        payload: dict[str, Any],
        *,
        fallback_name: str | None = None,
        mime_type: str | None = None,
    ) -> UploadedFileObject:
        file_id = payload.get("id") or fallback_name or ""
        if not file_id:
            raise RuntimeError(f"Unexpected storage payload: {payload}")

        return UploadedFileObject(
            name=file_id,
            uri=payload.get("url") or "",
            mime_type=payload.get("mimeType") or mime_type,
            size_bytes=payload.get("size"),
            display_name=fallback_name,
            state="ACTIVE",
            create_time=payload.get("createdAt"),
            update_time=payload.get("updatedAt"),
            expires_at=payload.get("expiresAt"),
        )

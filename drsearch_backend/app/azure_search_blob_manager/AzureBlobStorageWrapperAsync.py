
import logging

from azure.storage.blob.aio import BlobServiceClient
from azure.storage.blob import RetentionPolicy, ContentSettings
from azure.core.exceptions import (
    ResourceExistsError,
    ResourceNotFoundError,
    HttpResponseError,
)
from app.models.blob_storage import Element
import base64
from typing import List
from pathlib import Path



logger = logging.getLogger("app.blob")  # a dedicated channel for your blob wrapper




class AzureBlobStorageAsync:
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.account_name = self.get_value_from_connection_string("AccountName")
        self.endpoint_suffix = self.get_value_from_connection_string("EndpointSuffix")
        self.blob_service_client = BlobServiceClient.from_connection_string(
            connection_string
        )

    def get_value_from_connection_string(self, key: str) -> str:
        for component in self.connection_string.split(";"):
            if component.startswith(f"{key}="):
                return component.split("=")[1]
        raise ValueError(f"{key} not found in connection string")

    async def close(self) -> None:
        await self.blob_service_client.close()

    async def authenticate_using_connection_string(self) -> None:
        pass

    async def upload_blob(self, container_name: str, blob_name: str, file_path: str):
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=container_name, blob=blob_name
            )
            with open(file_path, "rb") as data:
                await blob_client.upload_blob(data, overwrite=True)
        except (ResourceNotFoundError, HttpResponseError) as e:
            logger.error("Failed to upload blob", extra={"blob": blob_name, "container": container_name, "error": str(e)})

    async def download_blob(
        self, container_name: str, blob_name: str, download_path: str
    ):
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=container_name, blob=blob_name
            )
            stream = await blob_client.download_blob()
            data = await stream.readall()
            with open(download_path, "wb") as file:
                file.write(data)
        except ResourceNotFoundError:
            logger.warning("Blob not found", extra={"blob": blob_name, "container": container_name})
        except HttpResponseError as e:
            logger.error("Failed to download blob", extra={"blob": blob_name, "container": container_name, "error": str(e)})

    async def delete_blob(self, container_name: str, blob_name: str):
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=container_name, blob=blob_name
            )
            await blob_client.delete_blob(delete_snapshots="include")
        except (ResourceNotFoundError, HttpResponseError) as e:
            logger.error("Failed to delete blob", extra={"blob": blob_name, "container": container_name, "error": str(e)})

    async def list_blobs_in_container(self, container_name: str):
        try:
            container_client = self.blob_service_client.get_container_client(
                container_name
            )
            blob_list = []
            async for blob in container_client.list_blobs():
                blob_list.append(blob)
            return blob_list
        except (ResourceNotFoundError, HttpResponseError) as e:
            logger.error("Failed to list blobs", extra={"container": container_name, "error": str(e)})
            return []

    async def create_container(self, container_name: str):
        try:
            container_client = self.blob_service_client.get_container_client(
                container_name
            )
            await container_client.create_container()
        except ResourceExistsError:
            logger.info("Container already exists", extra={"container": container_name})
        except HttpResponseError as e:
            logger.error("Failed to create container", extra={"container": container_name, "error": str(e)})

    async def delete_container(self, container_name: str):
        try:
            container_client = self.blob_service_client.get_container_client(
                container_name
            )
            await container_client.delete_container()
        except ResourceNotFoundError:
            logger.warning("Container does not exist", extra={"container": container_name})
        except HttpResponseError as e:
            logger.error("Failed to delete container", extra={"container": container_name, "error": str(e)})

    async def set_container_metadata(self, container_name: str, metadata: dict):
        try:
            container_client = self.blob_service_client.get_container_client(
                container_name
            )
            await container_client.set_container_metadata(metadata=metadata)
        except (ResourceNotFoundError, HttpResponseError) as e:
            logger.error("Failed to set container metadata", extra={"container": container_name, "error": str(e)})

    async def get_container_metadata(self, container_name: str):
        try:
            container_client = self.blob_service_client.get_container_client(
                container_name
            )
            properties = await container_client.get_container_properties()
            return properties.metadata
        except (ResourceNotFoundError, HttpResponseError) as e:
            logger.error("Failed to retrieve container metadata", extra={"container": container_name, "error": str(e)})
            return {}

    async def create_blob_snapshot(self, container_name: str, blob_name: str):
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=container_name, blob=blob_name
            )
            snapshot = await blob_client.create_snapshot()
            return snapshot.get("snapshot")
        except (ResourceNotFoundError, HttpResponseError) as e:
            logger.error("Failed to create blob snapshot", extra={"blob": blob_name, "error": str(e)})
            return None

    async def soft_delete_and_undelete_blob(self, container_name: str, blob_name: str):
        try:
            delete_retention_policy = RetentionPolicy(enabled=True, days=1)
            await self.blob_service_client.set_service_properties(
                delete_retention_policy=delete_retention_policy
            )
            blob_client = self.blob_service_client.get_blob_client(
                container=container_name, blob=blob_name
            )
            await blob_client.delete_blob()
            await blob_client.undelete_blob()
        except (ResourceNotFoundError, HttpResponseError) as e:
            logger.error("Failed to soft delete and undelete blob", extra={"blob": blob_name, "error": str(e)})

    async def start_and_abort_blob_copy(
        self, source_url: str, container_name: str, blob_name: str
    ):
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=container_name, blob=blob_name
            )
            copy = await blob_client.start_copy_from_url(source_url)
            props = await blob_client.get_blob_properties()
            if props.copy.status != "success" and props.copy.id:
                await blob_client.abort_copy(props.copy.id)
        except (ResourceNotFoundError, HttpResponseError) as e:
            logger.error("Failed to start/abort blob copy", extra={"blob": blob_name, "error": str(e)})

    async def acquire_and_manage_leases(
        self, container_name: str, blob_name: str | None = None
    ):
        try:
            if blob_name:
                blob_client = self.blob_service_client.get_blob_client(
                    container=container_name, blob=blob_name
                )
                lease = await blob_client.acquire_lease()
                await blob_client.delete_blob(lease=lease)
            else:
                container_client = self.blob_service_client.get_container_client(
                    container_name
                )
                lease = await container_client.acquire_lease()
                await container_client.delete_container(lease=lease)
        except (ResourceNotFoundError, HttpResponseError) as e:
            logger.error("Failed to acquire/manage lease", extra={"container": container_name, "error": str(e)})

    async def get_blob_service_properties_and_stats(self):
        try:
            properties = await self.blob_service_client.get_service_properties()
            stats = await self.blob_service_client.get_service_stats()
            return {"properties": properties, "stats": stats}
        except HttpResponseError as e:
            logger.error("Failed to retrieve blob service properties or stats", extra={"error": str(e)})
            return {}

    async def list_all_containers(self):
        try:
            containers = []
            async for container in self.blob_service_client.list_containers():
                containers.append(container.name)
            return containers
        except HttpResponseError as e:
            logger.error("Failed to list all containers", extra={"error": str(e)})
            return []

    async def delete_all_containers(self, skip_verification: bool = False):
        try:
            containers = await self.list_all_containers()
            if not containers:
                logger.info("No containers found. Nothing to delete.")
                return
            if not skip_verification:
                return
            for c_name in containers:
                await self.delete_container(c_name)
        except Exception as e:
            logger.error("Failed to delete all containers", extra={"error": str(e)})

    async def delete_containers_with_prefix(self, prefix: str):
        try:
            async for container in self.blob_service_client.list_containers(
                name_starts_with=prefix
            ):
                await self.delete_container(container.name)
        except Exception as e:
            logger.error("Failed to delete containers with prefix", extra={"prefix": prefix, "error": str(e)})

    async def upload_blob_from_base64(
        self,
        container_name: str,
        blob_name: str,
        base64_content: str,
        overwrite: bool = True,
    ) -> None:
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=container_name, blob=blob_name
            )
            data = base64.b64decode(base64_content)
            await blob_client.upload_blob(data, overwrite=overwrite)
        except HttpResponseError as e:
            logger.error("Failed to upload base64 blob", extra={"blob": blob_name, "error": str(e)})

    async def download_blob_as_base64(self, container_name: str, blob_name: str) -> str:
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=container_name, blob=blob_name
            )
            stream = await blob_client.download_blob()
            data = await stream.readall()
            return base64.b64encode(data).decode("utf-8")
        except ResourceNotFoundError:
            logger.warning("Blob not found", extra={"blob": blob_name, "container": container_name})
            return ""
        except HttpResponseError as e:
            logger.error("Failed to download blob as base64", extra={"blob": blob_name, "container": container_name, "error": str(e)})
            return ""

    async def download_blob_text(
        self, container_name: str, blob_name: str, encoding: str = "utf-8"
    ) -> str:
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=container_name, blob=blob_name
            )
            stream = await blob_client.download_blob()
            data = await stream.readall()
            return data.decode(encoding)
        except ResourceNotFoundError:
            logger.warning("Blob not found", extra={"blob": blob_name, "container": container_name})
            return ""
        except HttpResponseError as e:
            logger.error("Failed to download blob", extra={"blob": blob_name, "container": container_name, "error": str(e)})
            return ""

    async def upload_blob_bytes(
        self,
        container_name: str,
        blob_name: str,
        data: bytes,
        overwrite: bool = True,
    ) -> None:
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=container_name, blob=blob_name
            )
            await blob_client.upload_blob(data, overwrite=overwrite)
        except HttpResponseError as e:
            logger.error("Failed to upload blob", extra={"blob": blob_name, "error": str(e)})

    # -------------------- Append Blob helpers --------------------
    async def ensure_container(self, container_name: str) -> None:
        """Create container if it doesn't exist (idempotent)."""
        try:
            container_client = self.blob_service_client.get_container_client(container_name)
            await container_client.create_container()
        except ResourceExistsError:
            pass
        except HttpResponseError as e:
            logger.error("Failed to ensure container", extra={"container": container_name, "error": str(e)})

    async def ensure_append_blob(
        self,
        container_name: str,
        blob_name: str,
        content_type: str | None = "application/json",
    ) -> None:
        """
        Ensure an Append Blob exists at container/blob. No-op if it already exists.
        """
        await self.ensure_container(container_name)
        blob_client = self.blob_service_client.get_blob_client(
            container=container_name, blob=blob_name
        )
        try:
            await blob_client.get_blob_properties()  # exists → OK
        except ResourceNotFoundError:
            try:
                cs = ContentSettings(content_type=content_type) if content_type else None
                await blob_client.create_append_blob(content_settings=cs)
            except HttpResponseError as e:
                logger.error(
                    "Failed to create append blob",
                    extra={"blob": blob_name, "container": container_name, "error": str(e)},
                )

    async def get_blob_length(self, container_name: str, blob_name: str) -> int:
        """Return current length of blob (0 if missing)."""
        blob_client = self.blob_service_client.get_blob_client(container=container_name, blob=blob_name)
        try:
            props = await blob_client.get_blob_properties()
            return int(props.size or 0)
        except ResourceNotFoundError:
            return 0
        except HttpResponseError as e:
            logger.error("Failed to get blob properties", extra={"blob": blob_name, "container": container_name, "error": str(e)})
            return 0

    async def append_blob_bytes(self, container_name: str, blob_name: str, data: bytes) -> None:
        """Append bytes as a single block to an Append Blob (must exist)."""
        if not data:
            return
        blob_client = self.blob_service_client.get_blob_client(container=container_name, blob=blob_name)
        try:
            await blob_client.append_block(data)
        except HttpResponseError as e:
            logger.error("Failed to append to blob", extra={"blob": blob_name, "container": container_name, "error": str(e)})

    async def export_elements_images_to_html(
        self,
        elements: List[Element],
        container_name: str,
        output_dir: str | Path = "./blob_base64_download",
        html_filename: str = "index.html",
        max_images: int = 10000,
    ) -> Path:
        output_dir = Path(output_dir)
        html_path = output_dir / html_filename
        output_dir.mkdir(parents=True, exist_ok=True)
        seen = set()
        image_names = []
        for el in elements:
            try:
                imgs = getattr(el.metadata, "images", []) or []
                for img in imgs:
                    if img not in seen:
                        seen.add(img)
                        image_names.append(img)
            except Exception as exc:
                logger.warning("Skipping element during image collection", extra={"error": str(exc)})
        if max_images:
            image_names = image_names[:max_images]
        try:
            with open(html_path, "w", encoding="utf-8") as html:
                html.write("<html><body>\n")
                for img_name in image_names:
                    local_path = output_dir / img_name
                    local_path.parent.mkdir(parents=True, exist_ok=True)
                    try:
                        await self.download_blob(
                            container_name, img_name, str(local_path)
                        )
                        html.write(
                            f'<img src="{img_name}" loading="lazy" style="max-width:100%;margin-bottom:20px;" />\n'
                        )
                    except ResourceNotFoundError:
                        logger.warning("Blob not found", extra={"blob": img_name})
                    except HttpResponseError as e:
                        logger.error("Failed to download blob", extra={"blob": img_name, "error": str(e)})
                    except Exception as exc:
                        logger.error("Unexpected error during image collection", extra={"blob": img_name, "error": str(exc)})
                html.write("</body></html>")
        except OSError as exc:
            raise RuntimeError(f"Failed writing HTML file {html_path}: {exc}") from exc
        return html_path.resolve()

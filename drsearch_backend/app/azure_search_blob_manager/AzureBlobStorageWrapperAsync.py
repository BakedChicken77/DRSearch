import os
import asyncio
from datetime import datetime, timedelta, timezone
from azure.storage.blob.aio import BlobServiceClient  # type: ignore
from azure.storage.blob import RetentionPolicy, ContainerSasPermissions  # type: ignore
from azure.core.exceptions import (
    ResourceExistsError,
    ResourceNotFoundError,
    HttpResponseError,
)
import base64
from typing import Union, List, Optional
from pathlib import Path

from pydantic import BaseModel


class ElementMetadata(BaseModel):
    filepath: Optional[str] = None
    image_base64: Optional[List[str]] = None
    category: Optional[str] = None
    document_title: Optional[str] = None
    filename: Optional[str] = None
    text_as_html: Optional[str] = None
    url: Optional[str] = None
    embedding: Optional[List[float]] = None
    images: Optional[List[str]] = None

    class Config:
        extra = "allow"


class Element(BaseModel):
    page_content: str | None = None
    metadata: ElementMetadata

    class Config:
        extra = "allow"


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
            print(
                f"Failed to upload blob '{blob_name}' to container '{container_name}': {e}"
            )

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
            print(f"Blob '{blob_name}' not found in container '{container_name}'.")
        except HttpResponseError as e:
            print(
                f"Failed to download blob '{blob_name}' from container '{container_name}': {e}"
            )

    async def delete_blob(self, container_name: str, blob_name: str):
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=container_name, blob=blob_name
            )
            await blob_client.delete_blob(delete_snapshots="include")
        except (ResourceNotFoundError, HttpResponseError) as e:
            print(
                f"Failed to delete blob '{blob_name}' from container '{container_name}': {e}"
            )

    async def list_blobs_in_container(self, container_name: str):  # pragma: no cover – Azure SDK I/O
        try:
            container_client = self.blob_service_client.get_container_client(
                container_name
            )
            blob_list = []
            async for blob in container_client.list_blobs():
                blob_list.append(blob)
            return blob_list
        except (ResourceNotFoundError, HttpResponseError) as e:
            print(f"Failed to list blobs in container '{container_name}': {e}")
            return []

    async def create_container(self, container_name: str):  # pragma: no cover – Azure SDK I/O
        try:
            container_client = self.blob_service_client.get_container_client(
                container_name
            )
            await container_client.create_container()
        except ResourceExistsError:
            print(f"Container '{container_name}' already exists.")
        except HttpResponseError as e:
            print(f"Failed to create container '{container_name}': {e}")

    async def delete_container(self, container_name: str):  # pragma: no cover – Azure SDK I/O
        try:
            container_client = self.blob_service_client.get_container_client(
                container_name
            )
            await container_client.delete_container()
        except ResourceNotFoundError:
            print(f"Container '{container_name}' does not exist.")
        except HttpResponseError as e:
            print(f"Failed to delete container '{container_name}': {e}")

    async def set_container_metadata(self, container_name: str, metadata: dict):  # pragma: no cover
        try:
            container_client = self.blob_service_client.get_container_client(
                container_name
            )
            await container_client.set_container_metadata(metadata=metadata)
        except (ResourceNotFoundError, HttpResponseError) as e:
            print(f"Failed to set metadata for container '{container_name}': {e}")

    async def get_container_metadata(self, container_name: str):  # pragma: no cover
        try:
            container_client = self.blob_service_client.get_container_client(
                container_name
            )
            properties = await container_client.get_container_properties()
            return properties.metadata
        except (ResourceNotFoundError, HttpResponseError) as e:
            print(f"Failed to retrieve metadata for container '{container_name}': {e}")
            return {}

    async def create_blob_snapshot(self, container_name: str, blob_name: str):  # pragma: no cover
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=container_name, blob=blob_name
            )
            snapshot = await blob_client.create_snapshot()
            return snapshot.get("snapshot")
        except (ResourceNotFoundError, HttpResponseError) as e:
            print(f"Failed to create snapshot for blob '{blob_name}': {e}")
            return None

    async def soft_delete_and_undelete_blob(self, container_name: str, blob_name: str):  # pragma: no cover
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
            print(f"Failed to soft delete and undelete blob '{blob_name}': {e}")

    async def start_and_abort_blob_copy(
        self, source_url: str, container_name: str, blob_name: str
    ):  # pragma: no cover – rarely used
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=container_name, blob=blob_name
            )
            copy = await blob_client.start_copy_from_url(source_url)
            props = await blob_client.get_blob_properties()
            if props.copy.status != "success" and props.copy.id:
                await blob_client.abort_copy(props.copy.id)
        except (ResourceNotFoundError, HttpResponseError) as e:
            print(f"Failed to start/abort blob copy for '{blob_name}': {e}")

    async def acquire_and_manage_leases(
        self, container_name: str, blob_name: str | None = None
    ):  # pragma: no cover
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
            print(f"Failed to acquire/manage lease: {e}")

    async def get_blob_service_properties_and_stats(self):  # pragma: no cover
        try:
            properties = await self.blob_service_client.get_service_properties()
            stats = await self.blob_service_client.get_service_stats()
            return {"properties": properties, "stats": stats}
        except HttpResponseError as e:
            print(f"Failed to retrieve blob service properties or stats: {e}")
            return {}

    async def list_all_containers(self):  # pragma: no cover
        try:
            containers = []
            async for container in self.blob_service_client.list_containers():
                containers.append(container.name)
            return containers
        except HttpResponseError as e:
            print(f"Failed to list all containers: {e}")
            return []

    async def delete_all_containers(self, skip_verification: bool = False):  # pragma: no cover
        try:
            containers = await self.list_all_containers()
            if not containers:
                print("No containers found. Nothing to delete.")
                return
            if not skip_verification:
                return
            for c_name in containers:
                await self.delete_container(c_name)
        except Exception as e:
            print(f"Failed to delete all containers: {e}")

    async def delete_containers_with_prefix(self, prefix: str):  # pragma: no cover
        try:
            async for container in self.blob_service_client.list_containers(
                name_starts_with=prefix
            ):
                await self.delete_container(container.name)
        except Exception as e:
            print(f"Failed to delete containers with prefix '{prefix}': {e}")

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
            print(f"Failed to upload base64 blob '{blob_name}': {e}")

    async def download_blob_as_base64(self, container_name: str, blob_name: str) -> str:
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=container_name, blob=blob_name
            )
            stream = await blob_client.download_blob()
            data = await stream.readall()
            return base64.b64encode(data).decode("utf-8")
        except ResourceNotFoundError:
            print(f"Blob '{blob_name}' not found in container '{container_name}'.")
            return ""
        except HttpResponseError as e:
            print(f"Failed to download blob '{blob_name}' as base64: {e}")
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
            print(f"Blob '{blob_name}' not found in container '{container_name}'.")
            return ""
        except HttpResponseError as e:
            print(
                f"Failed to download blob '{blob_name}' from container '{container_name}': {e}"
            )
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
            print(f"Failed to upload blob '{blob_name}': {e}")

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
                print(f"[WARN] Skipping element during image collection: {exc}")
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
                        print(f"[WARN] Blob not found: {img_name}")
                    except HttpResponseError as e:
                        print(f"[ERROR] Failed to download {img_name}: {e}")
                    except Exception as exc:
                        print(f"[ERROR] Unexpected error for {img_name}: {exc}")
                html.write("</body></html>")
        except OSError as exc:
            raise RuntimeError(f"Failed writing HTML file {html_path}: {exc}") from exc
        return html_path.resolve()

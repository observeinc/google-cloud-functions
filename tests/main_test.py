# -*- coding: utf-8 -*-
import unittest
import json
import gzip
import os
from unittest.mock import ANY, patch, MagicMock
from main import export_assets, check_export_operation_status, process_gcs_directory
from google.cloud import storage
from google.cloud import tasks_v2


class BaseTest(unittest.TestCase):
    def setUp(self):
        """Setup mock objects before each test."""
        self.mock_request = MagicMock()
        self.mock_bucket = MagicMock()
        self.mock_blob = MagicMock()
        self.mock_asset_service = MagicMock()
        self.mock_operations = MagicMock()
        self.mock_get_operation = MagicMock()


class TestExportAssets(BaseTest):
    @patch("main.create_cloud_task")
    @patch("main.storage")
    @patch("main.asset_v1")
    @patch("main.asset_v1.OutputConfig")
    @patch("main.asset_v1.ExportAssetsRequest")
    def test_export_assets(
        self, _, __, mock_asset_v1, mock_storage, mock_create_cloud_task
    ):
        mock_client = mock_asset_v1.AssetServiceClient.return_value
        mock_operation = self.mock_operations
        mock_operation.operation.name = "mocked_operation_name"
        mock_client.export_assets.return_value = mock_operation

        self.mock_request.get_json.return_value = {
            "asset_types": ["storage.googleapis.com.*"],
            "content_types": ["RESOURCE"],
        }

        mock_storage.Client.return_value.bucket.return_value = self.mock_bucket
        self.mock_bucket.blob.return_value = self.mock_blob

        response = export_assets(self.mock_request)

        # Assertions
        self.assertEqual(response, ("Asset export triggered", 200))
        mock_client.export_assets.assert_called()
        self.assertEqual(mock_create_cloud_task.call_count, 2)
        args, _ = mock_create_cloud_task.call_args
        self.assertTrue(args[0].startswith("bucket_placeholder/asset_export_v2_"))
        self.assertTrue(args[0].endswith("/operation_name.txt"))

    # Test case for when request doesn't contain "asset_types" and/or "content_type"
    @patch("main.create_cloud_task")
    @patch("main.storage")
    @patch("main.asset_v1")
    @patch("main.asset_v1.OutputConfig")
    @patch("main.asset_v1.ExportAssetsRequest")
    def test_export_assets_no_asset_or_content_types(
        self, _, __, mock_asset_v1, mock_storage, mock_create_cloud_task
    ):
        mock_client = mock_asset_v1.AssetServiceClient.return_value
        mock_operation = self.mock_operations
        mock_operation.operation.name = "mocked_operation_name"
        mock_client.export_assets.return_value = mock_operation

        self.mock_request.get_json.return_value = {}

        mock_storage.Client.return_value.bucket.return_value = self.mock_bucket
        self.mock_bucket.blob.return_value = self.mock_blob

        response = export_assets(self.mock_request)

        # Assertions
        self.assertEqual(response, ("Asset export triggered", 200))
        mock_client.export_assets.assert_called()
        self.assertEqual(mock_create_cloud_task.call_count, 2)
        args, _ = mock_create_cloud_task.call_args
        self.assertTrue(args[0].startswith("bucket_placeholder/asset_export_v2_"))
        self.assertTrue(args[0].endswith("/operation_name.txt"))

    # Test case for when an invalid content type is provided
    @patch("main.asset_v1")
    @patch("main.asset_v1.OutputConfig")
    @patch("main.asset_v1.ExportAssetsRequest")
    def test_export_assets_invalid_content_type(self, _, __, ___):
        mock_client = self.mock_asset_service.AssetServiceClient.return_value

        self.mock_request.get_json.return_value = {
            "asset_types": ["storage.googleapis.com.*"],
            "content_type": ["INVALID"],
        }

        with self.assertRaises(ValueError):
            export_assets(self.mock_request)

    # Test case for when `export_assets` in the Google Cloud SDK throws an exception
    @patch("main.asset_v1")
    @patch("main.asset_v1.OutputConfig")
    @patch("main.asset_v1.ExportAssetsRequest")
    @patch("main.storage.Client")
    @patch("main.tasks_v2.CloudTasksClient")
    def test_export_assets_sdk_exception(
        self,
        mock_cloud_tasks_client,
        mock_storage_client,
        mock_request,
        mock_output_config,
        mock_asset_v1,
    ):
        # Mock for AssetServiceClient
        mock_client = MagicMock()
        mock_client.export_assets.side_effect = Exception("SDK error")
        mock_asset_v1.AssetServiceClient.return_value = mock_client

        # Mock for storage client
        mock_storage_client_instance = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_storage_client_instance.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_storage_client.return_value = mock_storage_client_instance

        # Mock for CloudTasksClient
        mock_client_tasks = MagicMock()
        mock_cloud_tasks_client.return_value = mock_client_tasks

        # Mock request object
        mock_request_instance = MagicMock()
        request_data = {
            "asset_types": ["storage.googleapis.com.*"],
            "content_type": ["RESOURCE"],
        }
        mock_request_instance.get_json.return_value = request_data
        mock_request.return_value = mock_request_instance

        response = export_assets(mock_request_instance)

        self.assertEqual(
            response, ("Failed to export content type RESOURCE. Error: SDK error", 500)
        )


class TestCheckExportOperationStatus(BaseTest):
    def _setup_gcs_mocks(
        self,
        mock_storage_client,
        bucket_name="test_bucket_name",
        blob_text="test_operation_name",
    ):
        """Helper method to set up Google Cloud Storage mocks."""
        self.mock_blob.download_as_text.return_value = blob_text
        mock_storage_client.return_value.bucket.return_value = self.mock_bucket
        self.mock_bucket.blob.return_value = self.mock_blob

    def _setup_asset_api_mocks(self, mock_discovery_build, operation_done=True):
        """Helper method to set up Google Cloud Asset API mocks."""
        self.mock_operations.get.return_value = self.mock_get_operation
        self.mock_get_operation.execute.return_value = {"done": operation_done}
        mock_discovery_build.return_value = self.mock_asset_service

    @patch("main.process_gcs_directory")
    @patch("main.discovery.build")
    @patch("main.storage.Client")
    def test_check_export_operation_status_success(
        self, mock_storage_client, mock_discovery_build, mock_process_gcs_directory
    ):
        """Test successful check of export operation status."""
        # Mock the request object
        self.mock_request.data.decode.return_value = (
            "test_bucket_name/test_path/operation_name.txt"
        )

        # Set up mocks
        self._setup_gcs_mocks(mock_storage_client)
        self._setup_asset_api_mocks(mock_discovery_build, operation_done=True)

        # Call the function
        response = check_export_operation_status(self.mock_request)

        # Assertions
        mock_process_gcs_directory.assert_called_once_with(
            "test_bucket_name", "test_path/"
        )

    @patch("main.discovery.build")
    @patch("main.storage.Client")
    def test_check_export_operation_status_operation_not_done(
        self, mock_storage_client, mock_discovery_build
    ):
        # Mock the request object
        mock_request = MagicMock()
        mock_request.data.decode.return_value = (
            "test_bucket_name/test_path/operation_name.txt"
        )

        # Mock Google Cloud Storage client
        mock_client_instance = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.download_as_text.return_value = "test_operation_name"

        mock_client_instance.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_storage_client.return_value = mock_client_instance

        # Mock discovery.build for Asset API client
        mock_asset_service = MagicMock()
        mock_operations = MagicMock()
        mock_get_operation = MagicMock()
        mock_operations.get.return_value = mock_get_operation
        mock_get_operation.execute.return_value = {
            "done": False
        }  # operation is not done

        mock_asset_service.operations.return_value = mock_operations
        mock_discovery_build.return_value = mock_asset_service

        # Call the function and expect an exception
        with self.assertRaises(Exception) as context:
            check_export_operation_status(mock_request)

        self.assertIn(
            "Asset export operation not yet completed", str(context.exception)
        )


class TestProcessGCSDirectory(BaseTest):
    @patch("main.pubsub_v1.PublisherClient")
    @patch("main.storage.Client")
    def test_process_gcs_directory_success(
        self, mock_storage_client, mock_pubsub_client
    ):
        # Mock GCS methods
        mock_bucket = self.mock_bucket
        mock_blob = self.mock_blob

        # Mocking list_blobs
        blob1 = MagicMock()
        blob1.name = "some_prefix/test_path/operation_name.txt"
        blob2 = MagicMock()
        blob2.name = "some_prefix/test_path/RESOURCE/google.compute.Disk/my_blob.txt"
        blob2.download_as_bytes.return_value = (
            b'{"asset_type": "google.compute.Disk", "name": "asset1"}'
        )

        mock_bucket.list_blobs.return_value = [blob1, blob2]

        # Mock blob exists check
        mock_blob.exists.return_value = True

        # Setup storage client
        mock_storage_client.return_value.get_bucket.return_value = mock_bucket

        # Setup PubSub client
        mock_publisher = mock_pubsub_client.return_value

        # Call the function
        response = process_gcs_directory("test_bucket_name", "some_prefix/test_path/")

        # Assertions
        self.assertEqual(
            response,
            ("Asset export operation complete. Files processed successfully.", 200),
        )

        # Assert publish was called
        expected_message = json.dumps(
            {"asset_type": "google.compute.Disk", "name": "asset1"}
        )
        mock_publisher.publish.assert_called_once_with(
            ANY,
            data=ANY,
            observe_content_encoding="gzip",
            observe_original_length=str(len(expected_message)),
            observe_gcp_kind="https://cloud.google.com/asset-inventory/docs/reference/rest/v1/TopLevel/exportAssets",
            observe_gcp_asset_type="google.compute.Disk",
            observe_gcp_content_type="RESOURCE",
        )

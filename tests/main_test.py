# -*- coding: utf-8 -*-
import unittest
from unittest.mock import patch, MagicMock
from main import export_assets, check_export_operation_status
from google.cloud import storage
from google.cloud import tasks_v2


class TestExportAssets(unittest.TestCase):
    def setUp(self):
        # This method runs before every test
        self.mock_request = MagicMock()

        self.mock_client_instance = MagicMock()
        self.mock_bucket = MagicMock()
        self.mock_blob = MagicMock()

        self.mock_asset_service = MagicMock()
        self.mock_operations = MagicMock()
        self.mock_get_operation = MagicMock()

    def _setup_gcs_mocks(
        self,
        mock_storage_client,
        bucket_name="test_bucket_name",
        blob_text="test_operation_name",
    ):
        self.mock_blob.download_as_text.return_value = blob_text
        self.mock_client_instance.bucket.return_value = self.mock_bucket
        self.mock_bucket.blob.return_value = self.mock_blob
        mock_storage_client.return_value = self.mock_client_instance

    def _setup_asset_api_mocks(self, mock_discovery_build, operation_done=True):
        self.mock_operations.get.return_value = self.mock_get_operation
        self.mock_get_operation.execute.return_value = {"done": operation_done}
        self.mock_asset_service.operations.return_value = self.mock_operations
        mock_discovery_build.return_value = self.mock_asset_service

    @patch("main.create_cloud_task")
    @patch("main.storage")
    @patch("main.asset_v1")
    @patch("main.asset_v1.OutputConfig")
    @patch("main.asset_v1.ExportAssetsRequest")
    def test_export_assets(
        self,
        mock_request,
        mock_output_config,
        mock_asset_v1,
        mock_storage,
        mock_create_cloud_task,
    ):
        mock_client = MagicMock()
        mock_asset_v1.AssetServiceClient.return_value = mock_client

        mock_operation = MagicMock()
        mock_operation.operation.name = "mocked_operation_name"
        mock_client.export_assets.return_value = mock_operation

        mock_request = MagicMock()
        request_data = {
            "asset_types": ["storage.googleapis.com.*"],
            "content_types": ["RESOURCE"],
        }
        mock_request.get_json.return_value = request_data

        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_storage.Client.return_value.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob

        response = export_assets(mock_request)

        # Asserting the function behavior
        self.assertEqual(response, ("Asset export triggered", 200))
        mock_client.export_assets.assert_called()

        # Check if create_cloud_task was called
        self.assertEqual(mock_create_cloud_task.call_count, 2)

        # Get the first set of arguments passed to create_cloud_task
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
        self,
        mock_request,
        mock_output_config,
        mock_asset_v1,
        mock_storage,
        mock_create_cloud_task,
    ):
        mock_client = MagicMock()
        mock_asset_v1.AssetServiceClient.return_value = mock_client

        mock_operation = MagicMock()
        mock_operation.operation.name = "mocked_operation_name"
        mock_client.export_assets.return_value = mock_operation

        mock_request = MagicMock()
        request_data = {}
        mock_request.get_json.return_value = request_data

        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_storage.Client.return_value.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob

        response = export_assets(mock_request)

        # Asserting the function behavior
        self.assertEqual(response, ("Asset export triggered", 200))
        mock_client.export_assets.assert_called()

        # Check if create_cloud_task was called
        self.assertEqual(mock_create_cloud_task.call_count, 2)

        # Get the first set of arguments passed to create_cloud_task
        args, _ = mock_create_cloud_task.call_args
        self.assertTrue(args[0].startswith("bucket_placeholder/asset_export_v2_"))
        self.assertTrue(args[0].endswith("/operation_name.txt"))

    # Test case for when an invalid content type is provided
    @patch("main.asset_v1")
    @patch("main.asset_v1.OutputConfig")
    @patch("main.asset_v1.ExportAssetsRequest")
    def test_export_assets_invalid_content_type(
        self, mock_request, mock_output_config, mock_asset_v1
    ):
        mock_client = MagicMock()
        mock_asset_v1.AssetServiceClient.return_value = mock_client

        mock_request = MagicMock()
        request_data = {
            "asset_types": ["storage.googleapis.com.*"],
            "content_type": ["INVALID"],
        }
        mock_request.get_json.return_value = request_data

        with self.assertRaises(ValueError):
            export_assets(mock_request)

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

    @patch("main.process_gcs_directory")
    @patch("main.discovery.build")
    @patch("main.storage.Client")
    def test_check_export_operation_status_success(
        self, mock_storage_client, mock_discovery_build, mock_process_gcs_directory
    ):
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
        self.mock_request.data.decode.return_value = (
            "test_bucket_name/test_path/operation_name.txt"
        )

        # Set up mocks
        self._setup_gcs_mocks(mock_storage_client)
        self._setup_asset_api_mocks(mock_discovery_build, operation_done=False)

        # Call the function and expect an exception
        with self.assertRaises(Exception) as context:
            check_export_operation_status(self.mock_request)

        self.assertIn(
            "Asset export operation not yet completed", str(context.exception)
        )

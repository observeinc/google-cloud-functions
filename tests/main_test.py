# -*- coding: utf-8 -*-
import unittest
from unittest.mock import patch, MagicMock
from main import export_assets


class TestExportAssets(unittest.TestCase):
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
    @patch("main.asset_v1")
    @patch("main.asset_v1.OutputConfig")
    @patch("main.asset_v1.ExportAssetsRequest")
    def test_export_assets_no_asset_or_content_types(
        self, mock_request, mock_output_config, mock_asset_v1
    ):
        mock_client = MagicMock()
        mock_asset_v1.AssetServiceClient.return_value = mock_client

        mock_request = MagicMock()
        request_data = {"some_other_field": "some_value"}
        mock_request.get_json.return_value = request_data

        response = export_assets(mock_request)

        self.assertEqual(response, ("Asset export triggered", 200))
        mock_client.export_assets.assert_called()

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
    def test_export_assets_sdk_exception(
        self, mock_request, mock_output_config, mock_asset_v1
    ):
        mock_client = MagicMock()
        mock_client.export_assets.side_effect = Exception("SDK error")
        mock_asset_v1.AssetServiceClient.return_value = mock_client

        mock_request = MagicMock()
        request_data = {
            "asset_types": ["storage.googleapis.com.*"],
            "content_type": ["RESOURCE"],
        }
        mock_request.get_json.return_value = request_data

        response = export_assets(mock_request)

        self.assertEqual(
            response, ("Failed to export content type RESOURCE. Error: SDK error", 500)
        )

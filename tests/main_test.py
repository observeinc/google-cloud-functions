# -*- coding: utf-8 -*-
import unittest
from unittest.mock import patch, MagicMock
from main import export_assets


class TestExportAssets(unittest.TestCase):
    @patch("main.setup_logging")
    @patch("main.asset_v1")
    @patch("main.asset_v1.OutputConfig")
    @patch("main.asset_v1.ExportAssetsRequest")
    def test_export_assets(
        self, mock_request, mock_output_config, mock_asset_v1, mock_setup_logging
    ):

        mock_logging_client = MagicMock()
        mock_setup_logging.return_value = mock_logging_client

        mock_client = MagicMock()
        mock_asset_v1.AssetServiceClient.return_value = mock_client

        mock_request = MagicMock()
        request_data = {
            "asset_types": ["storage.googleapis.com.*"],
            "content_types": ["RESOURCE"],
        }
        mock_request.get_json.return_value = request_data

        response = export_assets(mock_request)

        self.assertEqual(response, ("Asset export triggered", 200))
        mock_client.export_assets.assert_called()

    # Test case for when request doesn't contain "asset_types" and/or "content_type"
    @patch("main.setup_logging")
    @patch("main.asset_v1")
    @patch("main.asset_v1.OutputConfig")
    @patch("main.asset_v1.ExportAssetsRequest")
    def test_export_assets_no_asset_or_content_types(
        self, mock_request, mock_output_config, mock_asset_v1, mock_setup_logging
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
    @patch("main.setup_logging")
    @patch("main.asset_v1")
    @patch("main.asset_v1.OutputConfig")
    @patch("main.asset_v1.ExportAssetsRequest")
    def test_export_assets_invalid_content_type(
        self, mock_request, mock_output_config, mock_asset_v1, mock_setup_logging
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
    @patch("main.setup_logging")
    @patch("main.asset_v1")
    @patch("main.asset_v1.OutputConfig")
    @patch("main.asset_v1.ExportAssetsRequest")
    def test_export_assets_sdk_exception(
        self, mock_request, mock_output_config, mock_asset_v1, mock_setup_logging
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

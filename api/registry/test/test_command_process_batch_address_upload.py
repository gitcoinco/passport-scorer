import asyncio
from io import StringIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from django.core.management import call_command
from django.test import TransactionTestCase, override_settings

from registry.models import BatchModelScoringRequest, BatchRequestStatus


class TestProcessBatchModelAddressUploads(TransactionTestCase):
    def test_process_pending_requests(self):
        mock_s3_client = MagicMock()
        mock_s3_client.get_object.return_value = {
            "ContentLength": 100,
            "Body": MagicMock(
                read=lambda: StringIO("address1\naddress2\naddress3")
                .getvalue()
                .encode()
            ),
        }

        # Create a mock for handle_get_analysis
        mock_handle_get_analysis = AsyncMock(return_value={"score": 75})

        with patch(
            "registry.management.commands.process_batch_model_address_upload.get_s3_client",
            return_value=mock_s3_client,
        ):
            with patch(
                "registry.management.commands.process_batch_model_address_upload.handle_get_analysis",
                mock_handle_get_analysis,
            ):
                for i in range(2):
                    BatchModelScoringRequest.objects.create(
                        status=BatchRequestStatus.PENDING.value,
                        s3_filename=f"test_file_{i}.csv",
                        model_list=["model1", "model2"],
                    )

                all_requests = BatchModelScoringRequest.objects.all()
                self.assertEqual(
                    len(all_requests),
                    2,
                    f"Expected 2 requests, but found {len(all_requests)}",
                )

                call_command("process_batch_model_address_upload")

                for request in BatchModelScoringRequest.objects.all():
                    self.assertEqual(
                        request.status,
                        BatchRequestStatus.DONE.value,
                        f"Expected status DONE, but got {request.status}",
                    )
                    self.assertEqual(
                        request.progress,
                        100,
                        f"Expected progress 100, but got {request.progress}",
                    )

                expected_calls = 6  # 2 files * 3 addresses each
                self.assertEqual(
                    mock_handle_get_analysis.call_count,
                    expected_calls,
                    f"Expected {expected_calls} calls to handle_get_analysis, but got {mock_handle_get_analysis.call_count}",
                )

        self.assertEqual(
            mock_s3_client.get_object.call_count, 2, "Expected 2 calls to S3 get_object"
        )
        self.assertEqual(
            mock_s3_client.put_object.call_count, 2, "Expected 2 calls to S3 put_object"
        )

    # If you comment out the following test, the first test will fail :()
    def test_handle_error_during_processing(self):
        with patch(
            "registry.management.commands.process_batch_model_address_upload.get_s3_client"
        ) as mock_get_s3_client:
            mock_get_s3_client.return_value.get_object.side_effect = Exception(
                "Test error"
            )

            # Create a pending request
            BatchModelScoringRequest.objects.create(
                status=BatchRequestStatus.PENDING.value,
                s3_filename="test_file.csv",
                model_list=["model1", "model2"],
            )

            # Call the command
            call_command("process_batch_model_address_upload")

            # Refresh the request from the database
            request = BatchModelScoringRequest.objects.first()
            self.assertEqual(
                request.status,
                BatchRequestStatus.ERROR.value,
                f"Expected status ERROR, but got {request.status}",
            )

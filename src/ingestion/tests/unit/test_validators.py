"""Unit tests for validation pipeline."""

from unittest.mock import Mock

import pytest

from lambda_handler.exceptions import FileTooLargeError, ProcessingError
from lambda_handler.models import Limits
from lambda_handler.processing.validators import (
    FileSizeValidator,
    ValidationPipeline,
    default_validation_pipeline,
)


class TestFileSizeValidator:
    """Tests for FileSizeValidator."""

    def test_valid_file_size(self):
        """Test file within size limit."""
        mock_s3 = Mock()
        mock_s3.head_object.return_value = {"ContentLength": "1024"}
        validator = FileSizeValidator()
        assert validator.validate(bucket="bucket", key="key", s3_client=mock_s3) == 1024
        mock_s3.head_object.assert_called_once_with(Bucket="bucket", Key="key")

    def test_file_too_large_default_limit(self):
        """Test file exceeding default size limit."""
        mock_s3 = Mock()
        mock_s3.head_object.return_value = {
            "ContentLength": str((Limits.MAX_FILE_MB + 1) * Limits.BYTES_PER_MB)
        }
        validator = FileSizeValidator()
        with pytest.raises(FileTooLargeError, match="exceeds limit"):
            validator.validate(bucket="bucket", key="key", s3_client=mock_s3)

    def test_file_too_large_custom_limit(self):
        """Test file exceeding custom size limit."""
        mock_s3 = Mock()
        mock_s3.head_object.return_value = {"ContentLength": str(10 * Limits.BYTES_PER_MB)}
        validator = FileSizeValidator(max_size_mb=5)
        with pytest.raises(FileTooLargeError, match="exceeds limit"):
            validator.validate(bucket="bucket", key="key", s3_client=mock_s3)

    def test_s3_client_error(self):
        """Test S3 client error."""
        mock_s3 = Mock()
        mock_s3.head_object.side_effect = Exception("S3 error")
        validator = FileSizeValidator()
        with pytest.raises(ProcessingError, match="Failed to access S3 object"):
            validator.validate(bucket="bucket", key="key", s3_client=mock_s3)

    def test_accepts_kwargs(self):
        """Test validator accepts additional kwargs (for pipeline context)."""
        mock_s3 = Mock()
        mock_s3.head_object.return_value = {"ContentLength": "1024"}
        validator = FileSizeValidator()
        assert (
            validator.validate(
                bucket="bucket", key="key", s3_client=mock_s3, extra_context="ignored"
            )
            == 1024
        )


class TestValidationPipeline:
    """Tests for ValidationPipeline."""

    def test_single_validator(self):
        """Test pipeline with single validator."""
        mock_s3 = Mock()
        mock_s3.head_object.return_value = {"ContentLength": "1024"}
        pipeline = ValidationPipeline([FileSizeValidator()])
        assert pipeline.run(bucket="bucket", key="key", s3_client=mock_s3) == 1024

    def test_multiple_validators(self):
        """Test pipeline with multiple validators."""
        mock_s3 = Mock()
        mock_s3.head_object.return_value = {"ContentLength": "1024"}
        pipeline = ValidationPipeline(
            [
                FileSizeValidator(max_size_mb=100),
                FileSizeValidator(max_size_mb=50),
            ]
        )
        assert pipeline.run(bucket="bucket", key="key", s3_client=mock_s3) == 1024
        assert mock_s3.head_object.call_count == 2

    def test_pipeline_stops_on_first_error(self):
        """Test pipeline stops on first validator error."""
        mock_s3 = Mock()
        mock_s3.head_object.return_value = {"ContentLength": str(60 * Limits.BYTES_PER_MB)}
        mock_validator2 = Mock()
        pipeline = ValidationPipeline([FileSizeValidator(max_size_mb=50), mock_validator2])
        with pytest.raises(FileTooLargeError):
            pipeline.run(bucket="bucket", key="key", s3_client=mock_s3)
        mock_validator2.validate.assert_not_called()

    def test_empty_pipeline(self):
        """Test pipeline with no validators."""
        mock_s3 = Mock()
        assert ValidationPipeline([]).run(bucket="bucket", key="key", s3_client=mock_s3) == 0

    def test_context_passed_between_validators(self):
        """Test context (size_bytes) is passed between validators."""
        mock_s3 = Mock()
        mock_s3.head_object.return_value = {"ContentLength": "2048"}
        mock_validator2 = Mock()
        mock_validator2.validate.return_value = 2048
        pipeline = ValidationPipeline([FileSizeValidator(), mock_validator2])
        pipeline.run(bucket="bucket", key="key", s3_client=mock_s3)
        call_kwargs = mock_validator2.validate.call_args[1]
        assert call_kwargs["size_bytes"] == 2048


class TestDefaultValidationPipeline:
    """Tests for default_validation_pipeline factory."""

    def test_default_pipeline_has_file_size_validator(self):
        """Test default pipeline includes FileSizeValidator."""
        pipeline = default_validation_pipeline()
        assert isinstance(pipeline, ValidationPipeline)
        assert len(pipeline.validators) == 1
        assert isinstance(pipeline.validators[0], FileSizeValidator)

    def test_default_pipeline_works(self):
        """Test default pipeline validates files correctly."""
        mock_s3 = Mock()
        mock_s3.head_object.return_value = {"ContentLength": "1024"}
        pipeline = default_validation_pipeline()
        assert pipeline.run(bucket="bucket", key="key", s3_client=mock_s3) == 1024

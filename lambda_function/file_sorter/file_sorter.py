"""
FileSorter class that will sort the files into the appropriate
HERMES instrument folder.
"""
import os

from pathlib import Path

from sdc_aws_utils.logging import log
from sdc_aws_utils.aws import (
    create_s3_client_session,
    create_timestream_client_session,
    log_to_timestream,
    object_exists,
    create_s3_file_key,
)
from sdc_aws_utils.slack import get_slack_client, send_slack_notification
from sdc_aws_utils.config import parser, INSTR_TO_BUCKET_NAME


class FileSorter:
    """
    The FileSorter class initializes an object with the data file and the
    bucket event that triggered the lambda function call.
    """

    def __init__(
        self,
        s3_bucket: str,
        file_key: str,
        environment: str,
        dry_run=False,
        s3_client: type = None,
        timestream_client: type = None,
        slack_token: str = None,
        slack_channel: str = None,
        slack_retries: int = 3,
        slack_retry_delay: int = 5,
    ):
        """
        Initialize the FileSorter object.
        """
        self.slack_token = slack_token or os.getenv("SDC_AWS_SLACK_TOKEN")
        self.slack_channel = slack_channel or os.getenv("SDC_AWS_SLACK_CHANNEL")

        log.error(f"slack_token: {self.slack_token}")
        self.slack_client = (
            get_slack_client(self.slack_token)
            if self.slack_token and self.slack_channel
            else None
        )

        self.slack_retries = slack_retries
        self.slack_retry_delay = slack_retry_delay

        self.file_key = file_key
        self.instrument_bucket_name = s3_bucket

        self.timestream_client = timestream_client or create_timestream_client_session()
        self.s3_client = s3_client or create_s3_client_session()

        self.science_file = parser(self.file_key)
        self.incoming_bucket_name = s3_bucket
        self.destination_bucket = INSTR_TO_BUCKET_NAME[self.science_file["instrument"]]

        self.dry_run = dry_run
        if self.dry_run:
            log.warning("Performing Dry Run - Files will not be copied/removed")

        self.environment = environment
        self._sort_file()

    def _sort_file(self):
        """
        Determine the correct sorting function based on the file key name.
        """
        if (
            object_exists(
                s3_client=self.s3_client,
                bucket=self.incoming_bucket_name,
                file_key=self.file_key,
            )
            or self.dry_run
        ):
            # Get file name from file key
            path_file = Path(self.file_key)
            new_file_key = create_s3_file_key(parser, path_file.name)

            self._copy_from_source_to_destination(
                source_bucket=self.incoming_bucket_name,
                file_key=self.file_key,
                new_file_key=new_file_key,
                destination_bucket=self.destination_bucket,
            )

        else:
            raise ValueError("File does not exist in bucket")

    def _copy_from_source_to_destination(
        self,
        source_bucket=None,
        destination_bucket=None,
        file_key=None,
        new_file_key=None,
    ):
        """
        Copy a file from the S3 incoming bucket using the bucket key
        to the destination bucket.
        """
        log.info(f"Copying {file_key} from {source_bucket} to {destination_bucket}")

        copy_source = {"Bucket": source_bucket, "Key": file_key}

        if not self.dry_run:
            # Copy file from source bucket to destination bucket
            self.s3_client.copy_object(
                CopySource=copy_source,
                Bucket=destination_bucket,
                Key=new_file_key,
            )

            try:
                # If Slack is enabled, send a slack notification
                if self.slack_client:
                    send_slack_notification(
                        slack_client=self.slack_client,
                        slack_channel=self.slack_channel,
                        slack_message=(
                            f"File ({file_key}) Successfully Sorted to {destination_bucket}"
                        ),
                        slack_max_retries=self.slack_retries,
                        slack_retry_delay=self.slack_retry_delay,
                    )
                # If Timestream is enabled, log the file
                if self.timestream_client:
                    log_to_timestream(
                        timesteam_client=self.timestream_client,
                        action_type="PUT",
                        file_key=file_key,
                        new_file_key=new_file_key,
                        source_bucket=source_bucket,
                        destination_bucket=destination_bucket,
                    )

            except Exception as e:
                log.error(f"Error Occurred: {e}")

        log.info(f"File {file_key} Successfully Moved to {destination_bucket}")

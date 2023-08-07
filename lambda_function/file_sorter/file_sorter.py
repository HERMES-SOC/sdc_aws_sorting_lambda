"""
FileSorter class that will sort the files into the appropriate
HERMES instrument folder.
"""
import os
import json
from pathlib import Path

from sdc_aws_utils.logging import log
from sdc_aws_utils.aws import (
    create_s3_client_session,
    create_timestream_client_session,
    copy_file_in_s3,
    log_to_timestream,
    object_exists,
    create_s3_file_key,
)
from sdc_aws_utils.slack import get_slack_client, send_slack_notification
from sdc_aws_utils.config import parser, INSTR_TO_BUCKET_NAME


def sort_file(event, context):
    """
    Initialize the FileSorter class
    in the appropriate environment.

    :param environment: The current environment (e.g., 'DEVELOPMENT', 'PRODUCTION')
    :type environment: str
    :param s3_bucket: The S3 bucket where the file is stored
    :type s3_bucket: str, optional
    :param file_key: The S3 object key of the file
    :type file_key: str, optional
    :return: The response object with status code and message
    :rtype: dict
    """

    environment = os.getenv("LAMBDA_ENVIRONMENT", "DEVELOPMENT")

    for s3_event in event["Records"]:
        s3_bucket = s3_event["s3"]["bucket"]["name"]
        file_key = s3_event["s3"]["object"]["key"]

        log.info(f"Bucket: {s3_bucket}")
        log.info(f"File Key: {file_key}")

        response = FileSorter(
            s3_bucket=s3_bucket, file_key=file_key, environment=environment
        )

        return response
    try:
        FileSorter(s3_bucket=s3_bucket, file_key=file_key, environment=environment)

        return {"statusCode": 200, "body": json.dumps("File Sorted Successfully")}

    except Exception as e:
        log.error({"status": "ERROR", "message": e})

        return {"statusCode": 500, "body": json.dumps("Error Sorting File")}


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

        try:
            self.timestream_client = (
                timestream_client or create_timestream_client_session()
            )
            self.timestream_database = "sdc_aws_logs"
            self.timestream_table = "sdc_aws_s3_bucket_log_table"
        except Exception as e:
            log.error(f"Error creating Timestream client: {e}")
            self.timestream_client = None

        self.s3_client = s3_client or create_s3_client_session()

        self.science_file = parser(self.file_key)
        self.incoming_bucket_name = s3_bucket
        self.destination_bucket = (
            f'dev-{INSTR_TO_BUCKET_NAME[self.science_file["instrument"]]}'
            if environment == "DEVELOPMENT"
            else INSTR_TO_BUCKET_NAME[self.science_file["instrument"]]
        )

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

        if not self.dry_run:
            # Copy file from source to destination
            copy_file_in_s3(
                s3_client=self.s3_client,
                source_bucket=source_bucket,
                destination_bucket=destination_bucket,
                file_key=file_key,
                new_file_key=new_file_key,
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
                        database_name=self.timestream_database,
                        table_name=self.timestream_table,
                        action_type="PUT",
                        file_key=file_key,
                        new_file_key=new_file_key,
                        source_bucket=source_bucket,
                        destination_bucket=destination_bucket,
                        environment=self.environment,
                    )

            except Exception as e:
                log.error(f"Error Occurred: {e}")

        log.info(f"File {file_key} Successfully Moved to {destination_bucket}")

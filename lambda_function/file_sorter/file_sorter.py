"""
This Module contains the FileSorter class that will sort the files into the appropriate
HERMES instrument folder.
"""
import os
import boto3
import botocore
import datetime
import time
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# The below flake exceptions are to avoid the hermes.log writing
# issue the above line solves
from hermes_core import log  # noqa: E402
from hermes_core.util import util  # noqa: E402

# Starts boto3 session so it gets access to needed credentials
session = boto3.Session()

# Dict with instrument bucket names
INSTRUMENT_BUCKET_NAMES = {
    "eea": "hermes-eea",
    "nemisis": "hermes-nemisis",
    "merit": "hermes-merit",
    "spani": "hermes-spani",
}

UNSORTED_BUCKET_NAME = "swsoc-unsorted"


class FileSorter:
    """
    Main FileSorter class which initializes an object with the data file and the
    bucket event which triggered the lambda function to be called.
    """

    def __init__(self, s3_bucket, s3_object, environment, dry_run=False):
        """
        FileSorter Constructorlogger
        """

        # Initialize Class Variables
        try:
            self.incoming_bucket_name = s3_bucket
            log.info(
                f"Incoming Bucket Name Parsed Successfully: {self.incoming_bucket_name}"
            )

        except KeyError:
            error_message = "KeyError when extracting S3 Bucket Name/ARN from dict"
            log.error({"status": "ERROR", "message": error_message})
            raise KeyError(error_message)

        try:
            self.file_key = s3_object

            log.info(
                {
                    "status": "INFO",
                    "message": "Incoming Object Name"
                    f"Parsed Successfully: {self.file_key}",
                }
            )

        except KeyError:
            error_message = "KeyError when extracting S3 Object Name/eTag from dict"
            log.error({"status": "ERROR", "message": error_message})
            raise KeyError(error_message)

        # Variable that determines environment
        self.environment = environment

        # Variable that determines if FileSorter performs a Dry Run
        self.dry_run = dry_run
        if self.dry_run:
            log.warning("Performing Dry Run - Files will not be copied/removed")

        # Log added file to Incoming Bucket in Timestream
        if not self.dry_run:
            self._log_to_timestream(
                action_type="PUT",
                file_key=self.file_key,
                destination_bucket=s3_bucket,
            )

        try:
            # Initialize the slack client
            self.slack_client = WebClient(token=os.getenv("SLACK_TOKEN"))

            # Initialize the slack channel
            self.slack_channel = os.getenv("SLACK_CHANNEL")

        except SlackApiError as e:
            error_code = int(e.response["Error"]["Code"])
            if error_code == 404:
                log.error(
                    {
                        "status": "ERROR",
                        "message": "Slack Token is invalid",
                    }
                )

        except Exception as e:
            log.error(
                {
                    "status": "ERROR",
                    "message": f"Error when initializing slack client: {e}",
                }
            )

        # Call sort function
        self._sort_file()

    def _sort_file(self):
        """
        Function that chooses calls correct sorting function
        based off file key name.
        """
        # Verify object exists in incoming bucket
        if (
            self._does_object_exists(
                bucket=self.incoming_bucket_name, file_key=self.file_key
            )
            or self.dry_run
        ):
            # Dict of parsed science file
            destination_bucket = self._get_destination_bucket(file_key=self.file_key)
            current_year = datetime.date.today().year
            current_month = datetime.date.today().month
            if current_month < 10:
                current_month = f"0{current_month}"
            file_key_array = self.file_key.split("/")
            parsed_file_key = file_key_array[-1]

            new_file_key = (
                f"{util.VALID_DATA_LEVELS[0]}/"
                f"{current_year}/{current_month}/"
                f"{parsed_file_key}"
            )
            # Verify object does not exist in destination bucket
            if not self._does_object_exists(
                bucket=destination_bucket, file_key=new_file_key
            ):
                # Copy file to destination bucket
                self._copy_from_source_to_destination(
                    source_bucket=self.incoming_bucket_name,
                    file_key=self.file_key,
                    new_file_key=new_file_key,
                    destination_bucket=destination_bucket,
                )

            else:
                # Add to unsorted if object already exists in destination bucket
                new_file_key = (
                    f"duplicate_file_with_attempted_timestamps/{self.file_key}_"
                    f"{datetime.datetime.utcnow().strftime('%Y-%m-%d-%H%MZ')}"
                )

                log.error(
                    {
                        "status": "ERROR",
                        "message": f"File {self.file_key}"
                        f" already exists in {destination_bucket}",
                    }
                )

        else:
            raise ValueError("File does not exist in bucket")

    def _get_destination_bucket(self, file_key):
        """
        Returns bucket in which the file will be sorted to
        """
        try:
            file_key_array = file_key.split("/")
            parsed_file_key = file_key_array[-1]

            science_file = util.parse_science_filename(parsed_file_key)
            destination_bucket = INSTRUMENT_BUCKET_NAMES[science_file["instrument"]]
            log.info(f"Destination Bucket Parsed Successfully: {destination_bucket}")

            return destination_bucket

        except ValueError as e:
            log.error({"status": "ERROR", "message": e})

            raise ValueError(e)

    def _does_object_exists(self, bucket, file_key):
        """
        Returns wether or not the file exists in the specified bucket
        """
        s3 = boto3.resource("s3")

        try:
            s3.Object(bucket, file_key).load()
        except botocore.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "404":
                log.info(f"File {file_key} does not exist in Bucket {bucket}")
                # The object does not exist.
                return False
            else:
                # Something else has gone wrong.
                raise
        else:
            log.info(f"File {file_key} already exists in Bucket {bucket}")
            return True

    def _copy_from_source_to_destination(
        self,
        source_bucket=None,
        destination_bucket=None,
        file_key=None,
        new_file_key=None,
    ):
        """
        Function to copy file from S3 incoming bucket using bucket key
        to destination bucket
        """
        log.info(f"Copying {file_key} From {source_bucket} to {destination_bucket}")

        try:
            # Initialize S3 Client and Copy Source Dict
            s3 = boto3.resource("s3")
            copy_source = {"Bucket": source_bucket, "Key": file_key}

            # Copy S3 file from incoming bucket to destination bucket
            if not self.dry_run:
                bucket = s3.Bucket(destination_bucket)
                if new_file_key:
                    bucket.copy(copy_source, new_file_key)
                    if self.slack_client:
                        self._send_slack_notification(
                            self.slack_client,
                            self.slack_channel,
                            (
                                f"File ({file_key}) "
                                "Successfully Sorted to "
                                "{destination_bucket}"
                            ),
                        )

                else:
                    bucket.copy(copy_source, file_key)

            # Log added file to Incoming Bucket in Timestream
            if not self.dry_run:
                self._log_to_timestream(
                    action_type="PUT",
                    file_key=file_key,
                    new_file_key=new_file_key,
                    source_bucket=source_bucket,
                    destination_bucket=destination_bucket,
                )

            log.info(f"File {file_key} Successfully Moved to {destination_bucket}")

        except botocore.exceptions.ClientError as e:
            log.error({"status": "ERROR", "message": e})

            raise e

    @staticmethod
    def _send_slack_notification(
        slack_client,
        slack_channel: str,
        slack_message: str,
        alert_type: str = "success",
    ) -> None:
        """
        Function to send a Slack Notification
        """
        log.info(f"Sending Slack Notification to {slack_channel}")
        try:
            color = {
                "success": "#9b59b6",
                "error": "#ff0000",
            }
            ct = datetime.datetime.now()
            ts = ct.strftime("%y-%m-%d %H:%M:%S")
            slack_client.chat_postMessage(
                channel=slack_channel,
                text=f"{ts} - {slack_message}",
                attachments=[
                    {
                        "color": color[alert_type],
                        "blocks": [
                            {
                                "type": "section",
                                "text": {
                                    "type": "plain_text",
                                    "text": f"{ts} - {slack_message}",
                                },
                            }
                        ],
                    }
                ],
            )

        except SlackApiError as e:
            log.error(
                {
                    "status": "ERROR",
                    "message": f"Error sending Slack Notification: {e}",
                }
            )

    def _log_to_timestream(
        self,
        action_type,
        file_key,
        new_file_key=None,
        source_bucket=None,
        destination_bucket=None,
    ):
        """
        Function to log to Timestream
        """
        log.info("Logging to Timestream")
        CURRENT_TIME = str(int(time.time() * 1000))
        try:
            # Initialize Timestream Client
            timestream = boto3.client("timestream-write")

            if not source_bucket and not destination_bucket:
                raise ValueError("A Source or Destination Buckets is required")

            # connect to s3 - assuming your creds are all
            # set up and you have boto3 installed
            s3 = boto3.resource("s3")

            # get the bucket

            bucket = s3.Bucket(destination_bucket)
            if action_type == "DELETE":
                bucket = s3.Bucket(source_bucket)

            # use loop and count increment
            count_obj = 0
            for i in bucket.objects.all():
                print(i.key)
                count_obj = count_obj + 1

            # Write to Timestream
            if not self.dry_run:
                timestream.write_records(
                    DatabaseName="sdc_aws_logs",
                    TableName="sdc_aws_s3_bucket_log_table",
                    Records=[
                        {
                            "Time": CURRENT_TIME,
                            "Dimensions": [
                                {"Name": "action_type", "Value": action_type},
                                {
                                    "Name": "source_bucket",
                                    "Value": source_bucket or "N/A",
                                },
                                {
                                    "Name": "destination_bucket",
                                    "Value": destination_bucket or "N/A",
                                },
                                {"Name": "file_key", "Value": file_key},
                                {
                                    "Name": "new_file_key",
                                    "Value": new_file_key or "N/A",
                                },
                                {
                                    "Name": "current file count",
                                    "Value": str(count_obj) or "N/A",
                                },
                            ],
                            "MeasureName": "timestamp",
                            "MeasureValue": str(datetime.datetime.utcnow().timestamp()),
                            "MeasureValueType": "DOUBLE",
                        },
                    ],
                )

            log.info((f"File {file_key} Successfully Logged to Timestream"))

        except botocore.exceptions.ClientError as e:
            log.error({"status": "ERROR", "message": e})

            raise e

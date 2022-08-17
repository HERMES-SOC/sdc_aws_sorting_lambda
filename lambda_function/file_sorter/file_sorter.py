"""
This Module contains the FileSorter class that will sort the files into the appropriate
HERMES instrument folder.

TODO: Skeleton Code for initial repo, class still needs to be implemented including
logging to DynamoDB + S3 log file and docstrings expanded
"""
import boto3
import botocore
import datetime

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

    def __init__(self, s3_bucket, s3_object, dry_run=False):
        """
        FileSorter Constructorlogger
        """

        # Initialize Class Variables
        try:
            self.incoming_bucket_name = s3_bucket["name"]
            log.info(
                f"Incoming Bucket Name Parsed Successfully: {self.incoming_bucket_name}"
            )

        except KeyError:
            error_message = "KeyError when extracting S3 Bucket Name/ARN from dict"
            log.error(error_message)
            raise KeyError(error_message)

        try:
            self.file_key = s3_object["key"]
            self.file_etag = f'"{s3_object["eTag"]}"'

            log.info(f"Incoming Object Name Parsed Successfully: {self.file_key}")
            log.info(f"Incoming Object eTag Parsed Successfully: {self.file_etag}")

        except KeyError:
            error_message = "KeyError when extracting S3 Object Name/eTag from dict"
            log.error(error_message)
            raise KeyError(error_message)

        # Variable that determines if FileSorter performs a Dry Run
        self.dry_run = dry_run
        if self.dry_run:
            log.warning("Performing Dry Run - Files will not be copied/removed")
        # Call sort function
        self._sort_file()

    def _sort_file(self):
        """
        Function that chooses calls correct sorting function
        based off file key name.
        """
        # Verify object exists in incoming bucket
        if (
            self._verify_object_exists(
                bucket=self.incoming_bucket_name,
                file_key=self.file_key,
                etag=self.file_etag,
            )
            or self.dry_run
        ):

            # Dict of parsed science file
            self.destination_bucket = self._get_destination_bucket(
                file_key=self.file_key
            )

            # Verify object does not exist in destination bucket
            if not self._verify_object_exists(
                bucket=self.destination_bucket, file_key=self.file_key
            ):
                # Copy file to destination bucket
                self._copy_from_source_to_destination(
                    source_bucket=self.incoming_bucket_name,
                    file_key=self.file_key,
                    destination_bucket=self.destination_bucket,
                )
            else:
                # Add to unsorted if object already exists in destination bucket
                self.file_key = (
                    f"{self.file_key}_"
                    f"{datetime.datetime.utcnow().strftime('%Y-%m-%d-%H%MZ')}"
                )
                log.error(
                    "File already exists in destination bucket,"
                    "moving to unsorted bucket"
                )
                # Copy file to unsorted bucket
                self._copy_from_source_to_destination(
                    source_bucket=self.incoming_bucket_name,
                    file_key=self.file_key,
                    destination_bucket=UNSORTED_BUCKET_NAME,
                )

                # remove file from incoming bucket
                self._remove_object_from_bucket(
                    bucket=self.incoming_bucket_name, file_key=self.file_key
                )

            # Verify object exists in destination bucket
            # before removing it from incoming (Unless Dry Run)
            if (
                self._verify_object_exists(
                    bucket=self.destination_bucket,
                    file_key=self.file_key,
                    etag=self.file_etag,
                )
                or self.dry_run
            ):

                # Remove object from incoming bucket
                self._remove_object_from_bucket(
                    bucket=self.incoming_bucket_name, file_key=self.file_key
                )

        else:
            raise ValueError("File does not exist in bucket")

    def _get_destination_bucket(self, file_key):
        """
        Returns bucket in which the file will be sorted to
        """
        try:

            science_file = util.parse_science_filename(file_key)

            destination_bucket = INSTRUMENT_BUCKET_NAMES[science_file["instrument"]]
            log.info(f"Destination Bucket Parsed Successfully: {destination_bucket}")

            return destination_bucket

        except ValueError as e:
            log.error(e)

            raise ValueError(e)

    def _verify_object_exists(self, bucket, file_key, etag=None):
        """
        Returns wether or not the file exists in the specified bucket
        """
        try:
            s3 = boto3.resource("s3")
            s3_bucket_object = s3.ObjectSummary(bucket, file_key)

            # Checks to see that both the file key the same
            if s3_bucket_object.key == file_key:
                # Checks to see if the file eTag is the same if check_etag is True
                if etag:
                    if s3_bucket_object.e_tag == etag:
                        log.info(f"File {file_key} exists in Bucket {bucket}")
                        return True
                    else:
                        return False
                else:
                    return True
            else:
                log.info(f"File {file_key} does not exist in Bucket {bucket}")

                return False

        except botocore.exceptions.ClientError:
            log.info(f"File {file_key} does not exist in Bucket {bucket}")

            return False

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
                else:
                    bucket.copy(copy_source, file_key)
            log.info(f"File {file_key} Successfully Moved to {destination_bucket}")

        except botocore.exceptions.ClientError as e:
            log.error(e)

            raise e

    def _remove_object_from_bucket(self, bucket, file_key):
        """
        Function to copy file from S3 incoming bucket using bucket key
        to destination bucket
        """
        log.info(f"Removing From {file_key} from {bucket}")

        try:
            # Initialize S3 Client and Copy Source Dict
            s3 = boto3.resource("s3")

            # Copy S3 file from incoming bucket to destination bucket
            if not self.dry_run:
                s3.Object(bucket, file_key).delete()

            log.info((f"File {file_key} Successfully Removed from" f" {bucket}"))

        except botocore.exceptions.ClientError as e:
            log.error(e)

            raise e

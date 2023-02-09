"""
This module contains the handler function and the main function which contains the logic
that initializes the FileSorter class in it's correct environment.

TODO: Skeleton Code for initial repo, logic still needs to be implemented
and docstrings expanded
"""

import json
import os
import boto3

# The below flake exceptions are to avoid the hermes.log writing
# issue the above line solves
from hermes_core import log  # noqa: E402
from file_sorter.file_sorter import FileSorter  # noqa: E402

# This is so the hermes.log file writes to the correct location


def handler(event, context):
    """
    This is the lambda handler function that passes variables to the function that
    handles the logic that initializes the FileProcessor class in it's correct
    environment.
    """
    # Extract needed information from event
    try:
        log.info("Event: {}".format(event))
        environment = os.getenv("LAMBDA_ENVIRONMENT")
        if environment is None:
            environment = "DEVELOPMENT"

        for s3_event in event["Records"]:
            s3_bucket = s3_event["s3"]["bucket"]["name"]
            file_key = s3_event["s3"]["object"]["key"]

            log.info(f"Bucket: {s3_bucket}")
            log.info(f"File Key: {file_key}")

            # Pass required variables to sort function and returns a 200 (Successful)
            # / 500 (Error) HTTP response
            response = sort_file(environment, s3_bucket, file_key)

            return response

    except KeyError:
        # Pass required variables to sort function and returns a 200 (Successful)
        # / 500 (Error) HTTP response
        response = sort_file(environment)
        return {
            "statusCode": 500,
            "body": json.dumps("Key Error Extracting Variables from Event"),
        }


def sort_file(environment, s3_bucket=None, file_key=None):
    """
    This is the main function that handles logic that initializes the
    FileProcessor class in it's correct environment.
    """

    # Production (Official Release) Environment / Local Development
    try:
        log.info(f"Initializing FileSorter - Environment: {environment}")

        if not s3_bucket or not file_key:
            log.info("No S3 Bucket or File Key Provided")
            s3 = boto3.resource("s3")
            bucket = s3.Bucket("swsoc-incoming")
            for s3_object in bucket.objects.all():
                FileSorter(
                    s3_bucket=s3_bucket,
                    s3_object=s3_object.key,
                    environment=environment,
                )
            log.info("File Sorted Successfully")

        else:
            FileSorter(s3_bucket=s3_bucket, s3_object=file_key, environment=environment)
            log.info("File Sorted Successfully")

        return {"statusCode": 200, "body": json.dumps("File Sorted Successfully")}

    except BaseException as e:
        log.error({"status": "ERROR", "message": e})

        return {"statusCode": 500, "body": json.dumps("Error Sorting File")}

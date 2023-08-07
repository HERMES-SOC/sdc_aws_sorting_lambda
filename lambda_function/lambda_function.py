"""
Handler function and the main function for the AWS Lambda,
which initializes the FileSorter class in the appropriate environment.
"""

import json
import os

from .file_sorter import file_sorter


def handler(event, context):
    """
    Initialize the FileSorter class in the appropriate environment.

    :param event: The event object containing the S3 bucket and file key
    :type event: dict
    :param context: The context object containing the AWS Lambda runtime information
    :type context: dict
    :return: The response object with status code and message
    :rtype: dict
    """
    file_sorter.log.info("Event: {}".format(event))
    environment = os.getenv("LAMBDA_ENVIRONMENT", "DEVELOPMENT")

    for s3_event in event["Records"]:
        s3_bucket = s3_event["s3"]["bucket"]["name"]
        file_key = s3_event["s3"]["object"]["key"]

        file_sorter.log.info(f"Bucket: {s3_bucket}")
        file_sorter.log.info(f"File Key: {file_key}")

        response = sort_file(environment, s3_bucket, file_key)

        return response


def sort_file(environment, s3_bucket=None, file_key=None):
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

    try:
        file_sorter.FileSorter(
            s3_bucket=s3_bucket, file_key=file_key, environment=environment
        )

        return {"statusCode": 200, "body": json.dumps("File Sorted Successfully")}

    except Exception as e:
        file_sorter.log.error({"status": "ERROR", "message": e})

        return {"statusCode": 500, "body": json.dumps("Error Sorting File")}

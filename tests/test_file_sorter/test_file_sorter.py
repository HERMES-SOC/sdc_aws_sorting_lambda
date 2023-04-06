import boto3
import pytest
from moto import mock_s3, mock_timestreamwrite
from lambda_function.file_sorter import file_sorter
from sdc_aws_utils.config import parser
from sdc_aws_utils.aws import create_s3_file_key
from pathlib import Path
from slack_sdk.errors import SlackApiError
import os


INCOMING_BUCKET = "swsoc-incoming"
TEST_BUCKET = "hermes-spani"
TEST_BAD_FILE = "./tests/test_files/test-file-key.txt"
TEST_L0_FILE = "./tests/test_files/hermes_SPANI_l0_2023040-000018_v01.bin"
TEST_QL_FILE = "./tests/test_files/hermes_spn_ql_20230210_000018_v1.0.01.cdf"
TEST_L1_FILE = "./tests/test_files/hermes_spn_l1_20230210_000018_v1.0.01.cdf"
TEST_REGION = "us-east-1"


@pytest.fixture(scope="function")
def aws_credentials():
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"


@pytest.fixture(scope="function")
def s3_client(aws_credentials):
    with mock_s3():
        conn = boto3.client("s3", region_name=TEST_REGION)
        conn.create_bucket(
            Bucket=TEST_BUCKET,
        )
        yield conn


@pytest.fixture(scope="function")
def timestream_client(aws_credentials):
    with mock_timestreamwrite():
        conn = boto3.client("timestream-write", region_name=TEST_REGION)

        yield conn


@mock_s3
def test_file_sorter(s3_client, timestream_client):
    s3_client.create_bucket(Bucket=TEST_BUCKET)
    s3_client.create_bucket(Bucket=INCOMING_BUCKET)
    s3_client.put_object(Bucket=INCOMING_BUCKET, Key=TEST_L0_FILE, Body=b"test file")

    # Set up the database and table
    try:
        timestream_client.create_database(DatabaseName="sdc_aws_logs")
    except timestream_client.exceptions.ConflictException:
        pass
    try:
        timestream_client.create_table(
            DatabaseName="sdc_aws_logs", TableName="sdc_aws_s3_bucket_log_table"
        )
    except timestream_client.exceptions.ConflictException:
        pass

    file_sorter.FileSorter(
        s3_bucket=INCOMING_BUCKET,
        file_key=TEST_L0_FILE,
        environment="test-environment",
        dry_run=True,
        s3_client=s3_client,
        timestream_client=timestream_client,
    )

    # Check that the file was not copied during a dry run
    assert not s3_client.list_objects(Bucket=TEST_BUCKET).get("Contents")

    try:
        file_sorter.FileSorter(
            INCOMING_BUCKET,
            TEST_L0_FILE,
            "test-environment",
            dry_run=False,
            s3_client=s3_client,
            timestream_client=timestream_client,
        )
    except FileNotFoundError as e:
        assert e is not None

    path_file = Path(TEST_L0_FILE).name

    # Check that the file was copied to the correct HERMES folder
    assert s3_client.list_objects(
        Bucket=TEST_BUCKET,
    ).get(
        "Contents"
    )[0].get(
        "Key"
    ) == create_s3_file_key(parser, path_file)


@mock_s3
def test_file_sorter_with_slack(s3_client, timestream_client):
    s3_client.create_bucket(Bucket=TEST_BUCKET)
    s3_client.create_bucket(Bucket=INCOMING_BUCKET)
    s3_client.put_object(Bucket=INCOMING_BUCKET, Key=TEST_L0_FILE, Body=b"test file")
    # Set slack token (SDC_AWS_SLACK_TOKEN) and channel (SDC_AWS_SLACK_CHANNEL) environment variables

    # Set up the database and table
    try:
        timestream_client.create_database(DatabaseName="sdc_aws_logs")
    except timestream_client.exceptions.ConflictException:
        pass
    try:
        timestream_client.create_table(
            DatabaseName="sdc_aws_logs", TableName="sdc_aws_s3_bucket_log_table"
        )
    except timestream_client.exceptions.ConflictException:
        pass

    file_sorter.FileSorter(
        s3_bucket=INCOMING_BUCKET,
        file_key=TEST_L0_FILE,
        environment="test-environment",
        dry_run=True,
        s3_client=s3_client,
        timestream_client=timestream_client,
        slack_token="test-token",
        slack_channel="test-channel",
        slack_retries=0,
        slack_retry_delay=0,
    )

    # Check that the file was not copied during a dry run
    assert not s3_client.list_objects(Bucket=TEST_BUCKET).get("Contents")

    try:
        file_sorter.FileSorter(
            INCOMING_BUCKET,
            TEST_L0_FILE,
            "test-environment",
            dry_run=False,
            s3_client=s3_client,
            timestream_client=timestream_client,
            slack_token="test-token",
            slack_channel="test-channel",
            slack_retries=2,
            slack_retry_delay=2,
        )
    except SlackApiError as e:
        assert e is not None
    path_file = Path(TEST_L0_FILE).name

    # Check that the file was copied to the correct HERMES folder
    assert s3_client.list_objects(
        Bucket=TEST_BUCKET,
    ).get(
        "Contents"
    )[0].get(
        "Key"
    ) == create_s3_file_key(parser, path_file)


@mock_s3
def test_file_sorter_bad_file(s3_client, timestream_client):
    s3_client.create_bucket(Bucket=TEST_BUCKET)
    s3_client.create_bucket(Bucket=INCOMING_BUCKET)
    s3_client.put_object(Bucket=INCOMING_BUCKET, Key=TEST_BAD_FILE, Body=b"test file")

    # Set up the database and table
    try:
        timestream_client.create_database(DatabaseName="sdc_aws_logs")
    except timestream_client.exceptions.ConflictException:
        pass
    try:
        timestream_client.create_table(
            DatabaseName="sdc_aws_logs", TableName="sdc_aws_s3_bucket_log_table"
        )
    except timestream_client.exceptions.ConflictException:
        pass

    try:
        file_sorter.FileSorter(
            INCOMING_BUCKET,
            TEST_BAD_FILE,
            "test-environment",
            dry_run=True,
        )

    except ValueError as e:
        assert e is not None

    # Check that the file was not copied during a dry run
    assert not s3_client.list_objects(Bucket=TEST_BUCKET).get("Contents")


@mock_s3
def test_file_sorter_missing_file(s3_client, timestream_client):
    s3_client.create_bucket(Bucket=TEST_BUCKET)
    s3_client.create_bucket(Bucket=INCOMING_BUCKET)

    # Set up the database and table
    try:
        timestream_client.create_database(DatabaseName="sdc_aws_logs")
    except timestream_client.exceptions.ConflictException:
        pass
    try:
        timestream_client.create_table(
            DatabaseName="sdc_aws_logs", TableName="sdc_aws_s3_bucket_log_table"
        )
    except timestream_client.exceptions.ConflictException:
        pass

    try:
        file_sorter.FileSorter(
            INCOMING_BUCKET,
            TEST_L0_FILE,
            "test-environment",
            dry_run=False,
            s3_client=s3_client,
            timestream_client=timestream_client,
        )
    except ValueError as e:
        assert e is not None

    # Check that the file was not copied during a dry run
    assert not s3_client.list_objects(Bucket=TEST_BUCKET).get("Contents")

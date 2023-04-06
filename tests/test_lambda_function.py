import json
import pytest
import boto3
from moto import mock_s3
from lambda_function import lambda_function

TEST_BUCKET = "hermes-spani"
TEST_BAD_FILE = "./tests/test_files/test-file-key.txt"
TEST_L0_FILE = "./tests/test_files/hermes_SPANI_l0_2023040-000018_v01.bin"
# Mock event data
mock_event = {
    "Records": [
        {"s3": {"bucket": {"name": TEST_BUCKET}, "object": {"key": TEST_L0_FILE}}}
    ]
}
mock_empty_event = {}


@pytest.fixture
def s3_setup():
    with mock_s3():
        boto3.client("s3").create_bucket(Bucket=TEST_BUCKET)
        boto3.client("s3").put_object(
            Bucket=TEST_BUCKET, Key=TEST_L0_FILE, Body="Test content"
        )
        yield


def test_handler(s3_setup):
    response = lambda_function.handler(mock_event, None)

    assert response is not None


def test_handler_key_error(s3_setup):
    try:
        response = lambda_function.handler(mock_empty_event, None)
    except KeyError as e:
        assert e is not None


def test_sort_file_no_bucket_key(s3_setup):
    response = lambda_function.sort_file("DEVELOPMENT")
    assert response["statusCode"] == 500
    assert json.loads(response["body"]) == "Error Sorting File"

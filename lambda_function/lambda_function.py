"""
Handler function and the main function for the AWS Lambda,
which initializes the FileSorter class in the appropriate environment.
"""


from file_sorter import file_sorter


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

    return file_sorter.handle_event(event, context)

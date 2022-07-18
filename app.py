#!/usr/bin/env python3
import os

import aws_cdk as cdk

from cdk_deployment.sdc_aws_processing_lambda import SDCAWSSortingLambdaStack


app = cdk.App()
SDCAWSSortingLambdaStack(
    app,
    "SDCAWSSortingLambdaStack",
    env=cdk.Environment(account=os.getenv("CDK_DEFAULT_ACCOUNT"), region="us-east-2"),
)

app.synth()

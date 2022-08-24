#!/usr/bin/env python3
import aws_cdk as cdk

from abr.abr_stack import AbrStack
from abr.abr_stuff import AbrStuff

app = cdk.App()
s1 = AbrStuff(app, "AbrStuff")

AbrStack(app, "AbrStack",
    # If you don't specify 'env', this stack will be environment-agnostic.
    # Account/Region-dependent features and context lookups will not work,
    # but a single synthesized template can be deployed anywhere.

    # Uncomment the next line to specialize this stack for the AWS Account
    # and Region that are implied by the current CLI configuration.

    #env=cdk.Environment(account=os.getenv('CDK_DEFAULT_ACCOUNT'), region=os.getenv('CDK_DEFAULT_REGION')),

    # Uncomment the next line if you know exactly what Account and Region you
    # want to deploy the stack to. */

    #env=cdk.Environment(account='123456789012', region='us-east-1'),
    # env=cdk.Environment(account='616204075224', region='us-east-1'),
    myvpc=s1.myvpc,
    elastic_ip=s1.elastic_ip,
    application=s1.application,
    bucket=s1.bucket
    # For more information, see https://docs.aws.amazon.com/cdk/latest/guide/environments.html
    )

app.synth()

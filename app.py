#!/usr/bin/env python3
import aws_cdk as cdk

from abr.abr_stuff import AbrScaffolding
from abr.abr_stack import AbrStack
from abr.abr_stack import LTProps
from abr.abr_stack import AbrStackProps

app = cdk.App()

stage_stuff = AbrScaffolding(app, "stage-stuff", cidr="172.16.24.0/21")
stage_cms_lt_props = LTProps(
    machine_image=cdk.aws_ec2.MachineImage.latest_amazon_linux(
        generation=cdk.aws_ec2.AmazonLinuxGeneration.AMAZON_LINUX_2
    ),
    instance_type=cdk.aws_ec2.InstanceType.of(
        cdk.aws_ec2.InstanceClass.BURSTABLE3_AMD, 
        cdk.aws_ec2.InstanceSize.SMALL
    ),
    block_devices=[cdk.aws_ec2.BlockDevice(
        device_name="/dev/xvda",
        volume=cdk.aws_ec2.BlockDeviceVolume.ebs(15)
    )]
)
stage_stack_props = AbrStackProps(
    vpc=stage_stuff.myvpc,
    elastic_ip=stage_stuff.elastic_ip,
    application=stage_stuff.application,
    cms_lt=stage_cms_lt_props
)
stage_stack = AbrStack(app, "stage",
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
    props=stage_stack_props
    # For more information, see https://docs.aws.amazon.com/cdk/latest/guide/environments.html
    )

prod_stuff = AbrScaffolding(app, "prod-stuff", cidr="172.16.0.0/21")

prod_cms_lt_props = LTProps(
    machine_image=cdk.aws_ec2.MachineImage.latest_amazon_linux(
        generation=cdk.aws_ec2.AmazonLinuxGeneration.AMAZON_LINUX_2
    ),
    instance_type=cdk.aws_ec2.InstanceType.of(
        cdk.aws_ec2.InstanceClass.BURSTABLE3_AMD, 
        cdk.aws_ec2.InstanceSize.MEDIUM
    ),
    block_devices=[cdk.aws_ec2.BlockDevice(
        device_name="/dev/xvda",
        volume=cdk.aws_ec2.BlockDeviceVolume.ebs(20)
    )]
)
prod_web_lt_props = LTProps(
    machine_image=cdk.aws_ec2.MachineImage.latest_amazon_linux(
        generation=cdk.aws_ec2.AmazonLinuxGeneration.AMAZON_LINUX_2
    ),
    instance_type=cdk.aws_ec2.InstanceType.of(
        cdk.aws_ec2.InstanceClass.BURSTABLE3_AMD, 
        cdk.aws_ec2.InstanceSize.MICRO
    )
)
prod_stack_props = AbrStackProps(
    vpc=prod_stuff.myvpc,
    elastic_ip=prod_stuff.elastic_ip,
    application=prod_stuff.application,
    cms_lt=prod_cms_lt_props,
    web_lt=prod_web_lt_props
)

prod_stack = AbrStack(app, "prod",
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
    props=prod_stack_props
    # bucket=s1.bucket
    # For more information, see https://docs.aws.amazon.com/cdk/latest/guide/environments.html
    )

app.synth()

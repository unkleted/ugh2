from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_codedeploy as codedeploy,
    aws_logs as logs,
    aws_ssm as ssm,
    aws_s3 as s3
)

from constructs import Construct

class AbrScaffolding(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # The code that defines your stack goes here

        self.bucket = s3.Bucket(self, "abr-conf-bucket")

        self.myvpc = ec2.Vpc(self, "abr-prod",
            cidr="172.16.0.0/21",
            max_azs=2,
            nat_gateways=1,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    map_public_ip_on_launch=True,
                    cidr_mask=24
                ),
                ec2.SubnetConfiguration(
                    name="midtier",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_NAT,
                    cidr_mask=24
                ),
                ec2.SubnetConfiguration(
                    name="backend",
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                    cidr_mask=24
                ),               
            ]
        )

        self.log_group = logs.LogGroup(self, "Log Group",
            log_group_name="ABR"
        )

        self.application = codedeploy.ServerApplication(self, "CodeDeployApplication",
            application_name="ABR"
        )

        self.elastic_ip = ec2.CfnEIP(self, "EIP",
            domain="vpc"
        )

        with open('files/cwagent_copy') as f:
            lines = f.read()
        param = ssm.StringParameter(self, "cwssm",
            description="CloudWatch agent configuration",
            parameter_name="ABR-Log-Group",
            string_value=lines
        )
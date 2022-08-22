from re import A
from aws_cdk import (
    Duration,
    Stack,
    aws_autoscaling as autoscaling,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_codedeploy as codedeploy,
    aws_elasticloadbalancingv2 as elbv2,
    aws_logs as logs,
    aws_ssm as ssm
)
from constructs import Construct

class AbrStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # The code that defines your stack goes here

        # myvpc = ec2.Vpc.from_lookup(self, "external-vpc",
        #     vpc_id="vpc-0fb74506db0089b58"
        # )

        # Scaffolding for test env.
        myvpc = ec2.Vpc(self, "abr-prod",
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

        log_group = logs.LogGroup(self, "Log Group",
            log_group_name="ABR"
        )

        application = codedeploy.ServerApplication(self, "CodeDeployApplication",
            application_name="MyApplication"
        )

        bastion_sg = ec2.SecurityGroup(self, "bastionsg",
            vpc=myvpc,
            description="let me in"
        )

        bastion_sg.add_ingress_rule(
            peer=ec2.Peer.ipv4("217.180.201.183/32"),
            connection=ec2.Port.tcp(22)
        )

        bastion_sg.add_ingress_rule(
            peer=ec2.Peer.ipv4("0.0.0.0/0"),
            connection=ec2.Port.tcp(80)
        )

        bastion_sg.add_ingress_rule(
            peer=ec2.Peer.ipv4("0.0.0.0/0"),
            connection=ec2.Port.tcp(443)
        )

        my_baseimg = ec2.AmazonLinuxImage(
            generation=ec2.AmazonLinuxGeneration.AMAZON_LINUX_2
        )

        elastic_ip = ec2.CfnEIP(self, "EIP",
            domain="vpc"
        )

        with open('files/cwagent_copy') as f:
            lines = f.read()
        param = ssm.StringParameter(self, "cwssm",
            description="CloudWatch agent configuration",
            parameter_name="/ABR/AmazonCloudWatch-linux",
            string_value=lines
        )

        # template = ec2.LaunchTemplate(self, "LaunchTemplate",
        #     machine_image=my_baseimg,
        # )

        abr_asg = autoscaling.AutoScalingGroup(self, "ABR",
            # vpc=ec2.Vpc(self, "VPC"),
            vpc=myvpc,
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.BURSTABLE3_AMD, 
                ec2.InstanceSize.MICRO
            ),
            machine_image=my_baseimg,
            min_capacity=2,
            max_capacity=10,
            health_check=autoscaling.HealthCheck.elb(
                grace=Duration.minutes(2)
            ),
            # launch_template=template,
        )

        abr_asg.scale_on_cpu_utilization("KeepSpareCPU",
            target_utilization_percent=50
        )

        cms_asg =autoscaling.AutoScalingGroup(self, "ABR-CMS",
            vpc=myvpc,
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.BURSTABLE3_AMD, 
                ec2.InstanceSize.MICRO
            ),
            machine_image=my_baseimg,
            min_capacity=1,
            max_capacity=1,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PUBLIC
            ),
            key_name="my-key"
        )

        aws_managed_policies = [
            "CloudwatchAgentServerPolicy",
            "AmazonSSMManagedInstanceCore"
        ]
        my_asgs = [abr_asg, cms_asg]
        for amp in aws_managed_policies:
            for asg in my_asgs:
                asg.role.add_managed_policy(
                    iam.ManagedPolicy.from_aws_managed_policy_name(amp)
                )
        cms_asg.add_to_role_policy(iam.PolicyStatement(
            actions=["ec2:AssociateAddress"],
            resources=["*"]
        ))

        cms_asg.add_security_group(bastion_sg)
        
        cms_asg.add_user_data(f"aws ec2 associate-address --instance-id $(curl -s http://169.254.169.254/latest/meta-data/instance-id) --allocation-id {elastic_ip.attr_allocation_id} --allow-reassociation --region us-east-1")
        with open('files/userdata.sh') as f:
            lines = f.read()
        for asg in my_asgs:
            asg.add_user_data(lines)

        with open('files/certbot') as f:
            lines = f.read()
        cms_asg.add_user_data(lines)
        lb = elbv2.ApplicationLoadBalancer(self, "LB",
            vpc=myvpc,
            internet_facing=True
        )

        listener = lb.add_listener("Listener", port=80, open=True)

        listener.add_targets("ApplicationFleet", 
            port=80, 
            targets=[abr_asg]
        )

        cms_group = codedeploy.ServerDeploymentGroup(self, "CodeDeployDeploymentGroup",
            application=application,
            deployment_group_name="CMSDeploymentGroup",
            auto_scaling_groups=[cms_asg],
            install_agent=True
        )

        abr_group = codedeploy.ServerDeploymentGroup(self, "ABRCodeDeployDeploymentGroup",
            application=application,
            deployment_group_name="ABRDeploymentGroup",
            auto_scaling_groups=[abr_asg],
            install_agent=True
        )

        # https://bobbyhadz.com/blog/import-existing-vpc-aws-cdk

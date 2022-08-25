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

    def __init__(self, scope: Construct, construct_id: str, myvpc, elastic_ip, application, bucket, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # The code that defines your stack goes here

        # myvpc = ec2.Vpc.from_lookup(self, "external-vpc",
        #     vpc_id="vpc-0fb74506db0089b58"
        # )

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

        web_asg = autoscaling.AutoScalingGroup(self, "abr-web",
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
            )
        )

        web_asg.scale_on_cpu_utilization("KeepSpareCPU",
            target_utilization_percent=50
        )

        cms_asg =autoscaling.AutoScalingGroup(self, "abr-cms",
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
            "AmazonSSMManagedInstanceCore",
            "AmazonS3ReadOnlyAccess"
        ]
        my_asgs = [web_asg, cms_asg]
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
        with open('files/userdata.1') as f:
            lines1 = f.read()
        with open('files/userdata.2') as f:
            lines2 = f.read()
        for asg in my_asgs:
            asg.add_user_data(lines1)
            asg.add_user_data(f"aws s3 sync s3://{bucket.bucket_name}/etc/ /etc/")
            asg.add_user_data(lines2)
            

        with open('files/cms-stuff') as f:
            lines = f.read()
        cms_asg.add_user_data(lines)
        
        lb = elbv2.ApplicationLoadBalancer(self, "abr-web-alb",
            vpc=myvpc,
            internet_facing=True
        )

        listener = lb.add_listener("Listener", port=80, open=True)

        listener.add_targets("ApplicationFleet", 
            port=80, 
            targets=[web_asg]
        )

        cms_group = codedeploy.ServerDeploymentGroup(self, "ABR-CMSCodeDeployDeploymentGroup",
            application=application,
            deployment_group_name="CMSDeploymentGroup",
            auto_scaling_groups=[cms_asg],
            install_agent=True
        )

        abr_group = codedeploy.ServerDeploymentGroup(self, "ABR-WEBCodeDeployDeploymentGroup",
            application=application,
            deployment_group_name="WEBDeploymentGroup",
            auto_scaling_groups=[web_asg],
            install_agent=True
        )

        # https://bobbyhadz.com/blog/import-existing-vpc-aws-cdk

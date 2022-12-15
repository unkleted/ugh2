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
from dataclasses import dataclass

@dataclass
class LTProps:
    machine_image: ec2.IMachineImage 
    instance_type: ec2.InstanceType 
    block_devices: list[ec2.BlockDevice] | None = None

@dataclass
class AbrStackProps:
    vpc: ec2.IVpc
    elastic_ip: ec2.CfnEIP
    application: codedeploy.ServerApplication
    cms_lt: LTProps
    web_lt: LTProps | None = None

class AbrStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, props: AbrStackProps , **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # The code that defines your stack goes here

        bastion_sg = ec2.SecurityGroup(self, "bastionsg",
            vpc=props.vpc,
            description="let me in"
        )

        bastion_sg.add_ingress_rule(
            peer=ec2.Peer.ipv4("217.180.201.39/32"),
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

        cms_role = iam.Role(self, "cms-role",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com")
        )
        
        cms_props = props.cms_lt
        
        cms_lt = ec2.LaunchTemplate(self, "abr-cms",
            machine_image=cms_props.machine_image,
            instance_type=cms_props.instance_type,
            block_devices=cms_props.block_devices,
            security_group=bastion_sg,
            key_name="my-key",
            role=cms_role,
            user_data=ec2.UserData.for_linux(),
            # launch_template_name="abr-cms"
        )

        cms_asg = autoscaling.AutoScalingGroup(self, "cms-asg",
            vpc=props.vpc,
            launch_template=cms_lt, 
            min_capacity=1,
            max_capacity=1,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PUBLIC
            ),
        )

        cms_asg.add_to_role_policy(iam.PolicyStatement(
            actions=["ec2:AssociateAddress"],
            resources=["*"]
        ))
        self.__add_managed_policies(cms_asg)

        cms_asg.add_user_data(f"aws ec2 associate-address --instance-id $(curl -s http://169.254.169.254/latest/meta-data/instance-id) --allocation-id {props.elastic_ip.attr_allocation_id} --allow-reassociation --region us-east-1")
        self.__add_user_data(cms_lt)

        cms_group = codedeploy.ServerDeploymentGroup(self, "ABR-CMSCodeDeployDeploymentGroup",
            application=props.application,
            deployment_group_name="ABR-CMS",
            auto_scaling_groups=[cms_asg],
            install_agent=True
        )

        if construct_id == "prod":
            web_sg = ec2.SecurityGroup(self, "websg",
                vpc=props.vpc
            )
            web_role = iam.Role(self, "web-role",
                assumed_by=iam.ServicePrincipal("ec2.amazonaws.com")
            )
            web_props = props.web_lt
            web_lt = ec2.LaunchTemplate(self, "abr-web",
                machine_image=web_props.machine_image,
                instance_type=web_props.instance_type,
                block_devices=web_props.block_devices,
                security_group=web_sg,
                key_name="my-key",
                role=web_role,
                user_data=ec2.UserData.for_linux(),
            )
            web_asg = autoscaling.AutoScalingGroup(self, "web-asg",
                vpc=props.vpc,
                launch_template=web_lt,
                min_capacity=2,
                max_capacity=10,
                vpc_subnets=ec2.SubnetSelection(
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_NAT
                ),
                health_check=autoscaling.HealthCheck.elb(
                    grace=Duration.minutes(2)
                ),
            )

            web_asg.scale_on_cpu_utilization("KeepSpareCPU",
                target_utilization_percent=50
            )

            web_asg.connections.allow_from(cms_asg.connections, ec2.Port.tcp(22))

            lb = elbv2.ApplicationLoadBalancer(self, "abr-web-alb",
                vpc=props.vpc,
                internet_facing=True
            )

            listener = lb.add_listener("Listener", port=80, open=True)

            listener.add_targets("ApplicationFleet", 
                port=80, 
                targets=[web_asg]
            )

            abr_group = codedeploy.ServerDeploymentGroup(self, "ABR-WEBCodeDeployDeploymentGroup",
                application=props.application,
                deployment_group_name="ABR-WEB",
                auto_scaling_groups=[web_asg],
                install_agent=True
            )
            self.__add_managed_policies(web_asg)
            self.__add_user_data(web_lt)



        # https://bobbyhadz.com/blog/import-existing-vpc-aws-cdk

    def __add_managed_policies(self, asg: autoscaling.AutoScalingGroup) -> None:
        aws_managed_policies = [
            "CloudwatchAgentServerPolicy",
            "AmazonSSMManagedInstanceCore",
            "AmazonS3ReadOnlyAccess",
            "AmazonEC2ReadOnlyAccess"
        ]
        for amp in aws_managed_policies:
            asg.role.add_managed_policy(
                iam.ManagedPolicy.from_aws_managed_policy_name(amp)
            )

    def __add_user_data(self, launch_template: ec2.LaunchTemplate) -> None:
            launch_template.user_data.add_commands(
                "amazon-linux-extras install epel nginx1 -y",
                "yum install python2-pip git ansible -y",
                "pip install boto3 git-remote-codecommit",
                "git clone https://github.com/unkleted/an-pu-tst.git /tmp/ansible-config",
                "cd /tmp/ansible-config && ansible-playbook -c local -l $(curl -s http://169.254.169.254/latest/meta-data/local-hostname) playbook.yml"
            )
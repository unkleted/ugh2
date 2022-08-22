yum update --security -y

amazon-linux-extras enable nginx1 php7.4

yum install amazon-cloudwatch-agent nginx php-cli php-pdo php-fpm php-json php-mysqlnd -y

systemctl enable --now nginx
systemctl enable --now php-fpm

/opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -a fetch-config -m ec2 -s -c ssm:/ABR/AmazonCloudWatch-linux
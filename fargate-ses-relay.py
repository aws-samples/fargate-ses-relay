#!/usr/bin/env python3

# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

from constructs import Construct
from aws_cdk import (
	App,
	CfnOutput,
	Duration,
	Environment,
	Stack,
	RemovalPolicy,
	aws_ec2 as ec2,
	#aws_s3 as s3,
	aws_ecr as ecr,
	aws_iam as iam,
	aws_secretsmanager as sm,
	aws_ecr_assets as ecrassets,
	aws_ecs as ecs,
	aws_elasticloadbalancingv2 as elbv2,
	aws_ecs_patterns as ecs_patterns
)
import os

import cfg

class FargateSESStack(Stack):

	def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
		super().__init__(scope, construct_id, **kwargs)
		
		region = self.region
		account = self.account
		
		# VPC
		if cfg.EXISTING_VPC :
			# Import existing VPC into the stack
			vpc = ec2.Vpc.from_lookup(scope=self, id='VPC', vpc_id = cfg.VPC_ID)
		else :
			# Create a new VPC
			vpc = ec2.Vpc(
				scope=self,
				id='VPC',
				max_azs=3,
				ip_addresses=ec2.IpAddresses.cidr(cfg.VPC_CIDR),
				subnet_configuration=[
					# modify here to change the types of subnets provisioned as part of the VPC
					ec2.SubnetConfiguration(
						subnet_type=ec2.SubnetType.PUBLIC, 
						name="Public", 
						cidr_mask=24
					),
					ec2.SubnetConfiguration(
						subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
						name="PrivateWithEgress",
						cidr_mask=24,
					),
					#ec2.SubnetConfiguration(
					#	subnet_type=ec2.SubnetType.PRIVATE_ISOLATED, 
					#	name="PrivateIsolated",
					#	cidr_mask=24,
					#),
				],
				nat_gateway_provider=ec2.NatProvider.gateway(),
				nat_gateways=1,  # Only provision 1 NAT GW - default is one per one per AZ
			)

		# VPC Endpoint for ECR API
		#ecr_api_if_vpce = vpc.vpc.add_interface_endpoint("EcrApiEndpoint",service=ec2.InterfaceVpcEndpointAwsService.ECR)
		#ecr_api_if_vpce = ec2.InterfaceVpcEndpoint(
		#	scope=self, 
		#	id='EcrIfVpce',
		#	service=ec2.InterfaceVpcEndpointAwsService.ECR,
		#	vpc=vpc,
			#private_dns_enabled=True,
			#security_groups=[security_group],
			#subnets=ec2.SubnetSelection(
			#    subnet_type=ec2.SubnetType.PRIVATE_WITH_NAT
			#)
		#)

		# VPC Endpoint for ECR Docker
		#ecr_dkr_if_vpce = vpc.vpc.add_interface_endpoint("EcrDockerEndpoint",service=ec2.InterfaceVpcEndpointAwsService.ECR_DOCKER)
		#ecr_dkr_if_vpce = ec2.InterfaceVpcEndpoint(
		#	scope=self, 
		#	id='EcrDkrIfVpce',
		#	service=ec2.InterfaceVpcEndpointAwsService.ECR_DOCKER,
		#	vpc=vpc,
			#private_dns_enabled=True,
			#security_groups=[security_group],
			#subnets=ec2.SubnetSelection(
			#    subnet_type=ec2.SubnetType.PRIVATE
			#)
		#)

		# create ECS cluster
		cluster = ecs.Cluster(
			scope=self,
			id='ECSCluster',
			#
			vpc=vpc
		)
		
		# Build Docker asset
		asset = ecrassets.DockerImageAsset(
			scope=self,
			id='DockerAsset',
			directory='container',
			build_args={
            	"POSTFIX_SMTP_PORT": str(cfg.POSTFIX_SMTP_PORT),
            	"BUILD_PLATFORM": str(cfg.BUILD_PLATFORM)
			}
		)	
		
		# import existing SSM secret into the stack
		ses_smtp_secret = sm.Secret.from_secret_attributes(self, "ses_smtp_secret", secret_complete_arn=cfg.SES_SMTP_SECRET_ARN)

		# Fargate Task Options
		# https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_ecs/ContainerImage.html
		task_image_options=ecs_patterns.NetworkLoadBalancedTaskImageOptions(
			image=ecs.ContainerImage.from_docker_image_asset(asset),
			container_name="postfix-relay",
			container_port=cfg.POSTFIX_SMTP_PORT,
			secrets={
                "SES_SMTP_USERNAME": ecs.Secret.from_secrets_manager(ses_smtp_secret, field=cfg.SES_SMTP_SECRET_USERNAME_KEY),
                "SES_SMTP_PASSWORD": ecs.Secret.from_secrets_manager(ses_smtp_secret, field=cfg.SES_SMTP_SECRET_PASSWORD_KEY)
            },
			environment={
            	"POSTFIX_SMTP_PORT": str(cfg.POSTFIX_SMTP_PORT),
            	"SES_SMTP_ENDPOINT": str(cfg.SES_SMTP_ENDPOINT),
            	"ENABLE_HELO_DOMAIN_RESTRICTIONS": str(cfg.ENABLE_HELO_DOMAIN_RESTRICTIONS),
            	"ALLOWED_CLIENTS": " ".join(cfg.ALLOWED_CLIENTS),
            	"ALLOWED_HELO_DOMAINS": " ".join(cfg.ALLOWED_HELO_DOMAINS)
        	}
		)

		# set parameters based on the architecture chose for the container
		cpu_arch = str(cfg.BUILD_PLATFORM).split('/')[1].upper()
		if cpu_arch == "ARM64" :
			runtime_platform=ecs.RuntimePlatform(
				operating_system_family=ecs.OperatingSystemFamily.LINUX,
        		cpu_architecture=ecs.CpuArchitecture.ARM64
			)
		elif cpu_arch == "AMD64" :
			runtime_platform=ecs.RuntimePlatform(
    			operating_system_family=ecs.OperatingSystemFamily.LINUX,
    			cpu_architecture=ecs.CpuArchitecture.X86_64
    		)
		else :
			runtime_platform=None

		# NLB Security Group
		nlb_sg=ec2.SecurityGroup(
			scope=self, 
			id="NLB-SG",
			vpc=vpc,
    		description="Allow access to SES Relay",
    		allow_all_outbound=True,
		)

		# Allow client access to the NLB
		for cidr in cfg.ALLOWED_CLIENTS :
			nlb_sg.add_ingress_rule(
            	peer = ec2.Peer.ipv4(cidr),
            	connection = ec2.Port.tcp(cfg.POSTFIX_SMTP_PORT),
            	description="Allow from " + cidr
        	)

		# Network Load balancer
		nlb = elbv2.NetworkLoadBalancer(
			scope=self,
			id='FGNLB',
			vpc=vpc,
			security_groups=[nlb_sg],
			internet_facing=cfg.PUBLIC_LOAD_BALANCER,
		)

		# Fargate Service
		fargate_service = ecs_patterns.NetworkLoadBalancedFargateService(
			scope=self,
			id='FG',
			cluster=cluster,
			cpu=cfg.TASK_CPU,
			memory_limit_mib=cfg.TASK_MEMORY_MIB,
			runtime_platform=runtime_platform,
			desired_count=cfg.TASK_COUNT,
			task_image_options=task_image_options,
			# enable below to be able to exec ssh to the Fargate container
			enable_execute_command=cfg.TASK_ENABLE_EXEC_COMMAND,
			load_balancer=nlb.from_network_load_balancer_attributes(scope=self, id='NLB',load_balancer_arn=nlb.load_balancer_arn, vpc=vpc),
			listener_port=cfg.POSTFIX_SMTP_PORT
		)

		# Set max tasks value for Autoscaling
		fargate_scaling_group = fargate_service.service.auto_scale_task_count(
			max_capacity=cfg.AUTOSCALE_MAX_TASKS
		)
		
		# Autoscaling policy for the fargate service - CPU utilization
		fargate_scaling_group.scale_on_cpu_utilization(
			"CpuScaling",
			target_utilization_percent=50,
			scale_in_cooldown=Duration.seconds(60),
			scale_out_cooldown=Duration.seconds(60),
		)
		
		# Autoscaling policy for the fargate service - # of Connections through NLB
		#fargate_scaling.scale_on_metric(
        #    "CpuScaling",
        #    target_utilization_percent=50,
        #    scale_in_cooldown=Duration.seconds(60),
        #    scale_out_cooldown=Duration.seconds(60),
        #)

        # Allow access to the service from the NLB
		fargate_service.service.connections.security_groups[0].add_ingress_rule(
            peer = nlb_sg,
            connection = ec2.Port.tcp(cfg.POSTFIX_SMTP_PORT),
            description="Allow from NLB Security Group"
        )

		# Output the DNS of the LoadBalancer
		#CfnOutput(
        #    self, "LoadBalancerDNS",
        #    value=fargate_service.load_balancer.load_balancer_dns_name
        #)


app = App()

ses_relay_stack = FargateSESStack(app, cfg.APP_NAME, description=cfg.CFN_STACK_DESCRIPTION,
	# If you don't specify 'env', this stack will be environment-agnostic.
	# Account/Region-dependent features and context lookups will not work,
	# but a single synthesized template can be deployed anywhere.

	# Uncomment the next line to specialize this stack for the AWS Account
	# and Region that are implied by the current CLI configuration.

	env=Environment(account=os.getenv('CDK_DEFAULT_ACCOUNT'), region=os.getenv('CDK_DEFAULT_REGION')),

	# Uncomment the next line if you know exactly what Account and Region you
	# want to deploy the stack to. */

	#env=cdk.Environment(account='123456789012', region='us-east-1'),

	# For more information, see https://docs.aws.amazon.com/cdk/latest/guide/environments.html
	)
	
# ensure CFT format version is listed in the output
ses_relay_stack.template_options.template_format_version = '2010-09-09'
	
app.synth()
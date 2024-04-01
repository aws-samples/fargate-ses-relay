# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

# Application Configuration
# Note: changing the APP_NAME will result in a new stack being provisioned
APP_NAME = "SESRELAY"
APP_VERSION = "version 0.1"
CFN_STACK_DESCRIPTION = "FargateSESRelay (" + APP_VERSION + ")"

# Network options
 
VPC_CIDR = "10.21.0.0/16"
# Configure load balancer to be Internet-facing. True/False.
# WARNING: Setting this to TRUE CAN result in an open PUBLIC relay! Use at own risk. Only use if you have also set ALLOWED_CLIENTS and ALLOWED_HELO_DOMAINS appropriately.
PUBLIC_LOAD_BALANCER = False
# Allow list of clients that can access the services. Used for VPC Security Groups, and for the Postfix 'mynetworks' configuration.
ALLOWED_CLIENTS = [
        VPC_CIDR, # Allow access from the VPC
        #"192.168.0.0/16", # Allow access from a specific subnet
        #"10.25.7.123/32" # Allow access from a specific IP address
    ]
    
# Allow list of domains that clients can use during the HELO/EHLO handshake, see Postfix 'smtpd_helo_restrictions' and 'check_helo_access' configuration.
# You can turn this feature off by setting 'False' and an empty domain list below
ENABLE_HELO_DOMAIN_RESTRICTIONS = True
ALLOWED_HELO_DOMAINS = [
        #"domain1.tld", # Allow access from a specific domain
        #"domain2.tld" 
]

# Fargate task defintion parameters
# https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_definition_parameters.html
TASK_CPU=1024
TASK_MEMORY_MIB=2048
TASK_COUNT=1
AUTOSCALE_MAX_TASKS=10
# enable exec command to allow ssh to each task for debugging. Set to 'False' for production deployment.
TASK_ENABLE_EXEC_COMMAND=False
BUILD_PLATFORM="linux/arm64" # "linux/arm64" for Graviton, or "linux/amd64" for X86_64.

# postfix options
POSTFIX_SMTP_PORT=25 # Do not change. This is used for container networking, does NOT affect the Postfix default listening port.
SES_SMTP_ENDPOINT="email-smtp.us-east-1.amazonaws.com"
SES_SMTP_SECRET_ARN="arn:aws:secretsmanager:us-east-1:123456789123:secret:ses_smtp_secret-ABCDEF"
SES_SMTP_SECRET_USERNAME_KEY="ses_smtp_username"
SES_SMTP_SECRET_PASSWORD_KEY="ses_smtp_password"

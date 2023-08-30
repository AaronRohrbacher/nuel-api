import json
import boto3
import os
import pymysql
import time

def create_account(event, context):
    alb_client = boto3.client('elbv2')
    params = json.loads(event['body'])
    stack_client = boto3.client('cloudformation')
    ecs_client = boto3.client('ecs')
    efs_client = boto3.client('efs')
    route53_client = boto3.client('route53')
    acm_client = boto3.client('acm')
    rules = alb_client.describe_rules(ListenerArn="arn:aws:elasticloadbalancing:us-west-2:544012685056:listener/app/nuel-wp/7d9dd0a73c679972/d110efc9b92e9bc1")['Rules']
    listener_rule_priority = (len(rules))

    domain = params['domain']
    account_name = domain.replace('.', '-')
    sql_domain = domain.replace('.', '_')
    
    route53_client.create_hosted_zone(
        Name=domain,
        CallerReference=str(time.time())
    )
    
    acm_client.request_certificate(
        DomainName='*.' + domain,
        ValidationMethod='DNS',
    )
    
        
    database = pymysql.Connect(
        host="nuel-wp.cluster-cjgpfhxb4uwk.us-west-2.rds.amazonaws.com",
        user="admin",
        password="tenorsax"
    )
    cursor = database.cursor()
    sql = "CREATE DATABASE " + sql_domain + ";"
    print(sql)
    cursor.execute(sql)

    
    access_point_response = efs_client.create_access_point(
        Tags=[
            {
                'Key': 'name',
                'Value': account_name
            },
        ],
        FileSystemId='fs-0978aad11e8f483b1',
        PosixUser={
            'Uid': 0,
            'Gid': 0,
        },
        RootDirectory={
            'Path': '/' + account_name,
            'CreationInfo': {
                'OwnerUid': 0,
                'OwnerGid': 0,
                'Permissions': '7777'
            }
        }
    )
    
    task_definition = {
    "containerDefinitions": [
        {
            "name": "nuel-wp",
            "image": "544012685056.dkr.ecr.us-west-2.amazonaws.com/nuel-wp:latest",
            "cpu": 4096,
            "memory": 4096,
            "portMappings": [
                {
                    "name": "nuel-wp-80-tcp",
                    "containerPort": 80,
                    "hostPort": 0,
                    "protocol": "tcp",
                    "appProtocol": "http"
                },
                {
                    "name": "nuel-wp-443-tcp",
                    "containerPort": 443,
                    "hostPort": 0,
                    "protocol": "tcp",
                    "appProtocol": "http"
                },
                {
                    "name": "nuel-wp-22-tcp",
                    "containerPort": 22,
                    "hostPort": 0,
                    "protocol": "tcp",
                    "appProtocol": "http"
                }
            ],
            "essential": True,
            "environment": [
                {
                    "name": "WORDPRESS_DB_USER",
                    "value": "admin"
                },
                {
                    "name": "WORDPRESS_DB_HOST",
                    "value": "nuel-wp.cluster-cjgpfhxb4uwk.us-west-2.rds.amazonaws.com"
                },
                {
                    "name": "WORDPRESS_DB_PASSWORD",
                    "value": "tenorsax"
                },
                {
                    "name": "WORDPRESS_DB_NAME",
                    "value": sql_domain
                },
                {
                    "name": "WORDPRESS_TABLE_PREFIX",
                    "value": "wp_"
                },
                {
                    "name": "FS_METHOD",
                    "value": "direct"
                },
                {
                    "name": "WORDPRESS_HOME",
                    "value": "https://" + domain
                },
                {
                    "name": "WORDPRESS_SITEURL",
                    "value": "https://" + domain
                }
            ],
            "mountPoints": [
                {
                    "sourceVolume": "nuel-wp",
                    "containerPath": "/var/www/vhosts/localhost/html",
                    "readOnly": False
                }
            ],
            "volumesFrom": [],
            "logConfiguration": {
                "logDriver": "awslogs",
                "options": {
                    "awslogs-create-group": "True",
                    "awslogs-group": "/ecs/nuel-wp",
                    "awslogs-region": "us-west-2",
                    "awslogs-stream-prefix": "ecs"
                },
                "secretOptions": []
            },
            "healthCheck": {
                "command": [
                    "CMD-SHELL",
                    "curl -f http://localhost/ || exit 1"
                ],
                "interval": 60,
                "timeout": 20,
                "retries": 10
            }
        }
    ],
    "family": account_name,
    "taskRoleArn": "arn:aws:iam::544012685056:role/ecsTaskExecutionRole",
    "executionRoleArn": "arn:aws:iam::544012685056:role/ecsTaskExecutionRole",
    "networkMode": "bridge",
    "volumes": [
        {
            "name": "nuel-wp",
            "efsVolumeConfiguration": {
                "fileSystemId": "fs-0978aad11e8f483b1",
                "rootDirectory": "/",
                "transitEncryption": "ENABLED",
                "authorizationConfig": {
                    "accessPointId": access_point_response['AccessPointId'],
                    "iam": "DISABLED"
                }
            }
        }
    ],
    "placementConstraints": [],
    "requiresCompatibilities": [
        "EC2"
    ],
    "cpu": "4096",
    "memory": "4096",
    "runtimePlatform": {
        "cpuArchitecture": "X86_64",
        "operatingSystemFamily": "LINUX"
    },
}
    
    template = {
        "AWSTemplateFormatVersion": "2010-09-09",
        "Description": "The template used to create an ECS Service from the ECS Console.",
        "Parameters": {
            "ECSClusterName": {"Type": "String", "Default": "nuel-wp"},
            "SecurityGroupIDs": {
                "Type": "CommaDelimitedList",
                "Default": "sg-e36d02a9",
            },
            "SubnetIDs": {"Type": "CommaDelimitedList", "Default": ""},
            "VpcID": {"Type": "String", "Default": "vpc-7750fe0f"},
            "LoadBalancerName": {"Type": "String", "Default": "nuel-wp"},
        },
        "Resources": {
            "ECSService": {
                "Type": "AWS::ECS::Service",
                "Properties": {
                    "Cluster": "nuel-wp",
                    "TaskDefinition": "arn:aws:ecs:us-west-2:544012685056:task-definition/" + account_name,
                    "LaunchType": "EC2",
                    "ServiceName": account_name,
                    "SchedulingStrategy": "REPLICA",
                    "DesiredCount": 1,
                    "LoadBalancers": [
                        {
                            "ContainerName": "nuel-wp",
                            "ContainerPort": 80,
                            "LoadBalancerName": {"Ref": "AWS::NoValue"},
                            "TargetGroupArn": {"Ref": "TargetGroup"},
                        }
                    ],
                    "DeploymentConfiguration": {
                        "MaximumPercent": 200,
                        "MinimumHealthyPercent": 100,
                        "DeploymentCircuitBreaker": {"Enable": True, "Rollback": True},
                    },
                    "DeploymentController": {"Type": "ECS"},
                    "ServiceConnectConfiguration": {"Enabled": False},
                    "PlacementStrategies": [
                        {"Field": "attribute:ecs.availability-zone", "Type": "spread"},
                        {"Field": "instanceId", "Type": "spread"},
                    ],
                    "PlacementConstraints": [],
                    "Tags": [],
                    "EnableECSManagedTags": True,
                },
                "DependsOn": ["ListenerRule"],
            },
            "TargetGroup": {
                "Type": "AWS::ElasticLoadBalancingV2::TargetGroup",
                "Properties": {
                    "HealthCheckPath": "/wp-admin/css/install.min.css?ver=6.2.2",
                    "Name": account_name,
                    "Port": 80,
                    "Protocol": "HTTP",
                    "TargetType": "instance",
                    "HealthCheckProtocol": "HTTP",
                    "VpcId": "vpc-7750fe0f",
                },
            },
            "ListenerRule": {
                "Type": "AWS::ElasticLoadBalancingV2::ListenerRule",
                "Properties": {
                    "Actions": [
                        {"Type": "forward", "TargetGroupArn": {"Ref": "TargetGroup"}}
                    ],
                    "Conditions": [
                        {"Field": "host-header", "Values": [domain]}
                    ],
                    "ListenerArn": "arn:aws:elasticloadbalancing:us-west-2:544012685056:listener/app/nuel-wp/7d9dd0a73c679972/d110efc9b92e9bc1",
                    "Priority": str(listener_rule_priority),
                },
            },
        },
        "Outputs": {
            "ClusterName": {
                "Description": "The cluster used to create the service.",
                "Value": {"Ref": "ECSClusterName"},
            },
            "ECSService": {
                "Description": "The created service.",
                "Value": {"Ref": "ECSService"},
            },
            "TargetGroup": {
                "Description": "The created target group.",
                "Value": {"Ref": "TargetGroup"},
            },
            "ListenerRule": {
                "Description": "The created listener rule.",
                "Value": {"Ref": "ListenerRule"},
            },
        },
    }

    # with open("/tmp/task_definition.json", "w") as outfile:
    #     outfile.write(task_definition)
        
    # with open('/tmp/task_definition.json', 'r') as infile:
    #     os.system("aws ecs register-task-definition --cli-input-json file:///tmp/task_definition.json")
    task_response = ecs_client.register_task_definition(**task_definition)
    
    print(task_response)

    json_object = json.dumps(template, indent=4)


    with open("/tmp/sample.json", "w") as outfile:
        outfile.write(json_object)
        
    with open('/tmp/sample.json', 'r') as infile:
        response = stack_client.create_stack(
            StackName=account_name,
            TemplateBody=infile.read()
        )
    
    response = {"statusCode": 200, "body": json.dumps(template)}

    return response

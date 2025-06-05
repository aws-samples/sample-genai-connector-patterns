#!/usr/bin/env python3
import os

import aws_cdk as cdk

from aws_cdk import (
    Stack,
    aws_iam as iam,
    aws_kendra as kendra,
    aws_lambda as lambda_,
    RemovalPolicy,
    Duration,
    CfnParameter,
    CfnOutput,
    triggers
)

from constructs import Construct

class BedrockKendraStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs, description="Kendra Bedrock sample pattern with Microsoft SharePoint connector (uksb-y0x1nlspob) (tag:kendra-bedrock-sharepoint-cdk-python)")

        # Define parameters
        model_id_param = CfnParameter(
            self, "ModelId",
            type="String",
            default="anthropic.claude-v2",
            allowed_values=[
                "anthropic.claude-instant-v1",
                "anthropic.claude-3-sonnet-20240229-v1:0",
                "anthropic.claude-3-haiku-20240307-v1:0",
                "anthropic.claude-v2"
            ],
            description="Enter the Model Id of the Anthropic LLM"
        )

        sharepoint_version_param = CfnParameter(
            self, "SharePointVersion",
            type="String",
            default="SHAREPOINT_ONLINE",
            allowed_values=[
                "SHAREPOINT_2013",
                "SHAREPOINT_2016",
                "SHAREPOINT_ONLINE"
            ],
            description="SharePoint version (SHAREPOINT_2013, SHAREPOINT_2016, SHAREPOINT_ONLINE)"
        )

        sharepoint_urls_param = CfnParameter(
            self, "SharePointUrls",
            type="CommaDelimitedList",
            description="Enter comma-separated list of SharePoint site URLs (max 100) (e.g., https://company.sharepoint.com/sites/mysite)"
        )

        secret_arn_param = CfnParameter(
            self, "SecretArn",
            type="String",
            description="ARN of the Secrets Manager secret containing SharePoint credentials"
        )

        kendra_edition_param = CfnParameter(
            self, "KendraEdition",
            type="String",
            default="DEVELOPER_EDITION",
            allowed_values=[
                "DEVELOPER_EDITION",
                "ENTERPRISE_EDITION"
            ],
            description="Kendra edition (DEVELOPER_EDITION, ENTERPRISE_EDITION)"
        )

        # Use the parameter values in your stack
        model_id = model_id_param.value_as_string
        sharepoint_version = sharepoint_version_param.value_as_string
        # Convert CommaDelimitedList to a proper list for the SharePoint configuration
        sharepoint_urls = sharepoint_urls_param.value_as_list
        secret_arn = secret_arn_param.value_as_string
        kendra_edition = kendra_edition_param.value_as_string

        # Create Kendra index role
        kendra_index_role = iam.Role(
            self, "KendraIndexRole",
            assumed_by=iam.ServicePrincipal("kendra.amazonaws.com"),
            role_name=f"{construct_id}-KendraIndexRole"
        )

        # Add inline policy for restricted CloudWatch access
        kendra_index_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["cloudwatch:PutMetricData"],
            resources=["*"],
            conditions={
                "StringEquals": {
                    "cloudwatch:namespace": "AWS/Kendra"
                }
            }
        ))

        # Add permissions for CloudWatch Logs - scoped to Kendra log groups
        kendra_index_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["logs:DescribeLogGroups"],
            resources=[f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/kendra/*"]
        ))

        kendra_index_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["logs:CreateLogGroup"],
            resources=[f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/kendra/*"]
        ))

        kendra_index_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "logs:DescribeLogStreams",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            resources=[f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/kendra/*:log-stream:*"]
        ))

        # Create Kendra index
        kendra_index = kendra.CfnIndex(
            self, "KendraIndex",
            name=f"{construct_id}-KendraIndex",
            role_arn=kendra_index_role.role_arn,
            edition=kendra_edition
        )

        # Create Kendra data source role
        kendra_ds_role = iam.Role(
            self, "KendraDSRole",
            assumed_by=iam.ServicePrincipal("kendra.amazonaws.com"),
            role_name=f"{construct_id}-SharePointDSRole",
            inline_policies={
                "SharePointDSPolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "kendra:BatchPutDocument", 
                                "kendra:BatchDeleteDocument"
                            ],
                            resources=[kendra_index.attr_arn]
                        ),
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=["secretsmanager:GetSecretValue"],
                            resources=[secret_arn]
                        )
                    ]
                )
            }
        )

        # Create Kendra SharePoint data source
        kendra_ds = kendra.CfnDataSource(
            self, "KendraDS",
            index_id=kendra_index.attr_id,
            name=f"{construct_id}-KendraSharePointDS",
            type='SHAREPOINT',
            data_source_configuration=kendra.CfnDataSource.DataSourceConfigurationProperty(
                share_point_configuration=kendra.CfnDataSource.SharePointConfigurationProperty(
                    share_point_version=sharepoint_version,
                    urls=sharepoint_urls,
                    secret_arn=secret_arn
                )
            ),
            role_arn=kendra_ds_role.role_arn
        )

        # Add dependency
        kendra_ds.node.add_dependency(kendra_index)

        # Create a role for the DataSourceSyncLambda
        data_source_sync_lambda_role = iam.Role(
            self, "DataSourceSyncLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            inline_policies={
                "CloudWatchLogsPolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=[
                                "logs:CreateLogGroup",
                                "logs:CreateLogStream",
                                "logs:PutLogEvents"
                            ],
                            resources=[
                                f"arn:aws:logs:{Stack.of(self).region}:{Stack.of(self).account}:log-group:/aws/lambda/*"
                            ]
                        )
                    ]
                ),
                "KendraDataSourceSyncPolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=[
                                "kendra:StartDataSourceSyncJob",
                                "kendra:StopDataSourceSyncJob"
                            ],
                            resources=[
                                kendra_index.attr_arn,
                                f"{kendra_index.attr_arn}/data-source/{kendra_ds.attr_id}"
                            ]
                        )
                    ]
                )
            }
        )

        # Lambda function for initiating data source sync
        data_source_sync_lambda = lambda_.Function(
            self, "DataSourceSyncLambda",
            runtime=lambda_.Runtime.PYTHON_3_12,
            code=lambda_.Code.from_asset("src/dataSourceSync"),
            handler="dataSourceSyncLambda.lambda_handler",
            timeout=Duration.minutes(15),
            memory_size=1024,
            role=data_source_sync_lambda_role,
            environment={
                "INDEX_ID": kendra_index.attr_id,
                "DS_ID": kendra_ds.attr_id
            }
        )

        # Trigger data source sync lambda
        triggers.Trigger(
            self, "data_source_sync_lambda_trigger",
            handler=data_source_sync_lambda,
            timeout=Duration.minutes(10),
            invocation_type=triggers.InvocationType.EVENT
        )

        # Create the IAM role
        invoke_bedrock_lambda_role = iam.Role(
            self, "InvokeBedRockLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            inline_policies={
                "InvokeBedRockPolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=["bedrock:InvokeModel"],
                            resources=[f"arn:aws:bedrock:{self.region}::foundation-model/{model_id}"]
                        )
                    ]
                ),
                "KendraRetrievalPolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=["kendra:Retrieve"],
                            resources=[kendra_index.attr_arn]
                        )
                    ]
                )
            }
        )

        # Add specific CloudWatch Logs permissions
        invoke_bedrock_lambda_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["logs:CreateLogGroup"],
            resources=[f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/lambda/*"]
        ))

        invoke_bedrock_lambda_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            resources=[f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/lambda/*:log-stream:*"]
        ))

        # Lambda function for invoking Bedrock
        invoke_bedrock_lambda = lambda_.Function(
            self, "InvokeBedrockLambda",
            runtime=lambda_.Runtime.PYTHON_3_12,
            code=lambda_.Code.from_asset("src/invokeBedrockLambda"),
            handler="invokeBedrockLambda.lambda_handler",
            timeout=Duration.seconds(120),
            memory_size=3008,
            role=invoke_bedrock_lambda_role,
            environment={
                "INDEX_ID": kendra_index.attr_id,
                "MODEL_ID": model_id
            }
        )

        # Output values
        CfnOutput(self, "KendraIndexRoleArn", value=kendra_index_role.role_arn, description="Kendra index role ARN")
        CfnOutput(self, "KendraIndexID", value=kendra_index.attr_id, description="Kendra index ID")
        CfnOutput(self, "SharePointDataSourceId", value=kendra_ds.attr_id, description="Kendra SharePoint data source ID")
        CfnOutput(self, "DataSourceSyncLambdaArn", value=data_source_sync_lambda.function_arn, description="Data source sync lambda function ARN")
        CfnOutput(self, "InvokeBedrockLambdaArn", value=invoke_bedrock_lambda.function_arn, description="Invoke bedrock lambda function ARN")

app = cdk.App()
BedrockKendraStack(app, "BedrockKendraSharePointStack")
app.synth()
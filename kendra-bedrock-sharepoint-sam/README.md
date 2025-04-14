# AWS Lambda to Amazon Kendra to Amazon Bedrock

This pattern contains a sample AWS SAM stack that utilizes an AWS Lambda function to retrieve documents from an Amazon Kendra index and then pass it to Amazon Bedrock to generate a response. The pattern includes usage of the Microsoft SharePoint data source connector.

Important: this application uses various AWS services and there are costs associated with these services after the Free Tier usage - please see the AWS Pricing page for details. You are responsible for any AWS costs incurred. No warranty is implied in this example.

## Requirements
* [Create an AWS account](https://portal.aws.amazon.com/gp/aws/developer/registration/index.html) if you do not already have one and log in. The IAM user that you use must have sufficient permissions to make necessary AWS service calls and manage AWS resources.
* [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html) installed and configured
* [Git Installed](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git)
* [AWS Serverless Application Model](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-install.html) (AWS SAM) installed
* [Request Amazon Bedrock Model Access for Anthropic Claude models on Amazon Bedrock](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html)
* Before deploying the solution, you need to [configure your Microsoft SharePoint environment.](https://www.microsoft.com/en-us/microsoft-365/sharepoint/collaboration) Ensure you have access to a SharePoint site with the necessary permissions and content. For Authentication, store valid credentials (username and password) with sufficient permissions in AWS Secrets Manager to access the content. The SharePoint account should have at least Read permissions for all documents you intend to index. Your SharePoint environment should contain the documents you want to make searchable, which can include Microsoft Office files (.doc, .docx, .xls, .xlsx, .ppt, .pptx), PDFs, and various text file formats. While configuring the connector, you'll need to specify which SharePoint sites, lists, and document libraries to include in the index. Before proceeding with the deployment, verify that all intended documents are accessible and that your SharePoint site's content organization aligns with your search requirements. The credentials provided will be stored securely in AWS Secrets Manager and used by the Kendra connector to synchronize content from your SharePoint environment.

## Deployment Instructions
1. Create a new directory, navigate to that directory in a terminal and clone the GitHub repository:
    ```
    git clone https://github.com/aws-samples/sample-genai-connector-patterns
    ```
1. Change directory to the pattern directory:
    ```
    cd kendra-bedrock-sharepoint-sam
    ```
1. From the command line, use AWS SAM to deploy the AWS resources for the pattern as specified in the template.yml file:
    ```
    sam deploy --guided --capabilities CAPABILITY_NAMED_IAM
    ```
1. During the prompts:

    * Enter a SAM stack name
    * Enter the desired AWS Region
    * Enter one of the supported model IDs for Anthropic Claude on Bedrock from: `'anthropic.claude-instant-v1'`, `'anthropic.claude-3-sonnet-20240229-v1:0'`, `'anthropic.claude-3-haiku-20240307-v1:0'`, `'anthropic.claude-v2'`
    * Enter the version of Microsoft SharePoint that you use: SHAREPOINT_2013, SHAREPOINT_2016, SHAREPOINT_ONLINE
    * Enter your SharePoint site URLs (atleast 1)
    * Enter your AWS Secrets Manager ARN which will store Microsoft Sharepoint username and password for authentication.
    * Optionally, you can edit the template.yaml file to [configure additional attributes](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-kendra-datasource-sharepointconfiguration.html)
    * Enter Amazon Kendra edition: DEVELOPER_EDITION, ENTERPRISE_EDITION
    * Allow SAM CLI to create IAM roles with the required permissions.

    Once you have run `sam deploy --guided --capabilities CAPABILITY_NAMED_IAM` mode once and saved arguments to a configuration file (samconfig.toml), you can use `sam deploy` in future to use these defaults.*

1. Note the outputs from the SAM deployment process. These contain the resource names and/or ARNs which are used for testing.

# How it works
Please refer to the architecture diagram below:

![End to End Architecture](images/architecture.png)

Here's a breakdown of the steps:

**AWS Lambda:** Two AWS Lambda functions are created. `DataSourceSync` crawls and indexes the content. `InvokeBedrockLambda` invokes the specified model by passing the retrieved content from Amazon Kendra as context to the generative AI model.

**Amazon Kendra:** An Amazon Kendra index is created with a Microsoft Sharepoint data source connector. When a the `InvokeBedrockLambda` function is called, documents are retrieved from the Amazon Kendra index. The Kendra index created is an example and customers should update the configurations to match their data security practices. 

**Amazon Bedrock:** Documents retrieved from the Amazon Kendra index are sent to Amazon Bedrock which responds with a generated response.

## Testing

CLI Lambda invoke with test event:

```bash
aws lambda invoke --function-name LAMBDA_FUNCTION_ARN --cli-binary-format raw-in-base64-out --payload '{"question": "Value" }' output.txt
```
Replace "LAMBDA_FUNCTION_ARN" with invokeBedrock lambda function ARN and "Value" with prompt for bedrock.
The output.txt will contain the response generated by Amazon Bedrock.

Example JSON Lambda test event:

```
{
    "question": "Value"
}
```

## Cleanup

1. Delete the stack
    ```bash
    sam delete
    ```
----
<!-- Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

SPDX-License-Identifier: MIT-0 -->
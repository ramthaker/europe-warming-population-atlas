import * as path from 'node:path';
import * as fs from 'node:fs';
import { execFileSync } from 'node:child_process';
import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as location from 'aws-cdk-lib/aws-location';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
import * as s3deploy from 'aws-cdk-lib/aws-s3-deployment';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';

interface ClimateExplorerStackProps extends cdk.StackProps {
  siteDomain?: string;
}

export class ClimateExplorerStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: ClimateExplorerStackProps) {
    super(scope, id, props);

    const contentBucket = new s3.Bucket(this, 'SiteAndClimateData', {
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      enforceSSL: true,
      versioned: false,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    const agentPath = path.resolve(__dirname, '../../../agent');
    const agentFunction = new lambda.Function(this, 'ResilienceAgent', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'lambda_handler.handler',
      code: lambda.Code.fromAsset(agentPath, {
        exclude: ['.env', '.env.example', '.venv', '__pycache__'],
        bundling: {
          image: lambda.Runtime.PYTHON_3_12.bundlingImage,
          command: [
            'bash', '-c',
            'pip install --no-cache-dir -r requirements.txt -t /asset-output && cp -au . /asset-output',
          ],
          local: {
            tryBundle(outputDir: string) {
              const localPython = process.env.PYTHON
                ?? path.resolve(__dirname, '../../../pipeline/.venv/Scripts/python.exe');
              if (!fs.existsSync(localPython)) return false;
              try {
                execFileSync(localPython, [
                  '-m', 'pip', 'install', '--disable-pip-version-check', '--no-cache-dir',
                  '--target', outputDir,
                  '--platform', 'manylinux2014_x86_64',
                  '--python-version', '3.12', '--implementation', 'cp', '--abi', 'cp312',
                  '--only-binary=:all:', '-r', path.join(agentPath, 'requirements.txt'),
                ], { stdio: 'inherit' });
                for (const file of ['main.py', 'lambda_handler.py']) {
                  fs.copyFileSync(path.join(agentPath, file), path.join(outputDir, file));
                }
                return true;
              } catch {
                return false;
              }
            },
          },
        },
      }),
      description: 'Strands agent for map-grounded community heat preparedness briefs',
      memorySize: 2048,
      timeout: cdk.Duration.seconds(90),
      reservedConcurrentExecutions: 2,
      environment: {
        STRANDS_REGION: 'eu-central-1',
        STRANDS_MODEL_ID: 'eu.amazon.nova-lite-v1:0',
        WEB_ORIGIN: 'http://127.0.0.1:5173',
      },
    });

    const inferenceProfileArn = `arn:${cdk.Aws.PARTITION}:bedrock:eu-central-1:${cdk.Aws.ACCOUNT_ID}:inference-profile/eu.amazon.nova-lite-v1:0`;
    const modelArns = [
      'eu-west-3', 'eu-west-1', 'eu-central-1', 'eu-north-1',
    ].map((region) => `arn:${cdk.Aws.PARTITION}:bedrock:${region}::foundation-model/amazon.nova-lite-v1:0`);
    agentFunction.addToRolePolicy(new iam.PolicyStatement({
      actions: ['bedrock:InvokeModel', 'bedrock:InvokeModelWithResponseStream'],
      resources: [inferenceProfileArn, ...modelArns],
    }));

    const agentFunctionUrl = agentFunction.addFunctionUrl({
      authType: lambda.FunctionUrlAuthType.AWS_IAM,
    });

    const distribution = new cloudfront.Distribution(this, 'SiteDistribution', {
      defaultRootObject: 'index.html',
      defaultBehavior: {
        origin: origins.S3BucketOrigin.withOriginAccessControl(contentBucket),
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        cachePolicy: cloudfront.CachePolicy.CACHING_OPTIMIZED,
      },
      errorResponses: [
        { httpStatus: 403, responseHttpStatus: 200, responsePagePath: '/index.html', ttl: cdk.Duration.minutes(1) },
        { httpStatus: 404, responseHttpStatus: 200, responsePagePath: '/index.html', ttl: cdk.Duration.minutes(1) },
      ],
    });

    const map = new location.CfnMap(this, 'ClimateMap', {
      mapName: 'europe-climate-explorer-map',
      configuration: { style: 'VectorOpenDataVisualizationLight' },
      description: 'Basemap for Europe climate scenario explorer',
    });

    const key = new location.CfnAPIKey(this, 'PublicMapKey', {
      keyName: 'europe-climate-explorer-web',
      noExpiry: false,
      expireTime: new Date(Date.now() + 90 * 24 * 60 * 60 * 1000).toISOString(),
      forceUpdate: true,
      restrictions: {
        allowActions: ['geo:GetMap*'],
        allowResources: [map.attrArn],
        allowReferers: props.siteDomain
          ? [`https://${props.siteDomain}/*`]
          : [`https://${distribution.distributionDomainName}/*`],
      },
    });

    distribution.addBehavior(
      '/api/*',
      origins.FunctionUrlOrigin.withOriginAccessControl(agentFunctionUrl, {
        readTimeout: cdk.Duration.seconds(120),
      }),
      {
        allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
        cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
        originRequestPolicy: cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
      },
    );

    const webDistPath = path.resolve(__dirname, '../../../web/dist');
    new s3deploy.BucketDeployment(this, 'DeployWebAssets', {
      sources: [s3deploy.Source.asset(webDistPath)],
      destinationBucket: contentBucket,
      distribution,
      distributionPaths: ['/*'],
      prune: false,
    });

    new cdk.CfnOutput(this, 'SiteUrl', { value: `https://${distribution.distributionDomainName}` });
    new cdk.CfnOutput(this, 'ContentBucketName', { value: contentBucket.bucketName });
    new cdk.CfnOutput(this, 'LocationMapName', { value: map.mapName });
    new cdk.CfnOutput(this, 'LocationMapApiKeyArn', {
      value: key.attrKeyArn,
      description: 'Use aws location describe-key to retrieve the browser key after deployment.',
    });
    new cdk.CfnOutput(this, 'AgentApiUrl', {
      value: `https://${distribution.distributionDomainName}/api`,
      description: 'Agent API routed through CloudFront; Lambda Function URL requires CloudFront OAC.',
    });
  }
}

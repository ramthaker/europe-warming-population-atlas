import * as path from 'node:path';
import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as location from 'aws-cdk-lib/aws-location';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
import * as s3deploy from 'aws-cdk-lib/aws-s3-deployment';

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
      restrictions: {
        allowActions: ['geo:GetMap*'],
        allowResources: [map.attrArn],
        allowReferers: props.siteDomain
          ? [`https://${props.siteDomain}/*`]
          : [`https://${distribution.distributionDomainName}/*`],
      },
    });

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
  }
}

import * as cdk from 'aws-cdk-lib';
import { ClimateExplorerStack } from '../lib/climate-explorer-stack.js';

const app = new cdk.App();
const env = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: process.env.CLIMATE_EXPLORER_REGION ?? 'eu-central-1',
};

new ClimateExplorerStack(app, 'EuropeClimateExplorer', {
  env,
  siteDomain: process.env.SITE_DOMAIN,
});

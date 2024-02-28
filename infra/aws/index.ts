import * as pulumi from "@pulumi/pulumi";
import * as aws from "@pulumi/aws";
import * as awsx from "@pulumi/awsx";

// TODO: @Larisa : double memory for the scorer-api-default
// 
import {
  ScorerEnvironmentConfig,
  ScorerService,
  buildHttpLambdaFn,
  createIndexerService,
  createScoreExportBucketAndDomain,
  createScorerECSService,
  createTargetGroup,
  getEnvironment,
  secrets,
  createSharedLambdaResources,
  createDeadLetterQueue,
  createRescoreQueue,
  buildQueueLambdaFn,
} from "../lib/scorer/service";
import { createScheduledTask } from "../lib/scorer/scheduledTasks";

// The following vars are not allowed to be undefined, hence the `${...}` magic

//////////////////////////////////////////////////////////////
// Loading environment variables
//////////////////////////////////////////////////////////////

export const stack = pulumi.getStack();

const route53Zone = `${process.env["ROUTE_53_ZONE"]}`;
const route53ZoneForPublicData = `${process.env["ROUTE_53_ZONE_FOR_PUBLIC_DATA"]}`;

const domain = stack== "production"? `api.scorer.${process.env["DOMAIN"]}` : `api.${stack}.scorer.${process.env["DOMAIN"]}`;
const rootDomain = process.env["DOMAIN"];

const publicDataDomain = stack== "production"? `public.scorer.${process.env["DOMAIN"]}`: `public.${stack}.scorer.${process.env["DOMAIN"]}`;
const publicServiceUrl = `https://${domain}`;

const SCORER_SERVER_SSM_ARN = `${process.env["SCORER_SERVER_SSM_ARN"]}`;

const dockerGtcPassportScorerImage = `${process.env["DOCKER_GTC_PASSPORT_SCORER_IMAGE"]}`;
const dockerGtcPassportVerifierImage = `${process.env["DOCKER_GTC_PASSPORT_VERIFIER_IMAGE"]}`;

const dockerGtcSubmitPassportLambdaImage = `${process.env["DOCKER_GTC_SUBMIT_PASSPORT_LAMBDA_IMAGE"]}`;
const trustedIAMIssuers = `${process.env["TRUSTED_IAM_ISSUERS"]}`;


const redashDbUsername = `${process.env["REDASH_DB_USER"]}`;
const redashDbPassword = pulumi.secret(`${process.env["REDASH_DB_PASSWORD"]}`);
const redashDbName = `${process.env["REDASH_DB_NAME"]}`;
const redashSecretKey = pulumi.secret(`${process.env["REDASH_SECRET_KEY"]}`);
const redashMailUsername = `${process.env["REDASH_MAIL_USERNAME"]}`;
const redashMailPassword = pulumi.secret(
  `${process.env["REDASH_MAIL_PASSWORD"]}`
);

const pagerDutyIntegrationEndpoint = `${process.env["PAGERDUTY_INTEGRATION_ENDPOINT"]}`;

const coreInfraStack = new pulumi.StackReference(`gitcoin/core-infra/review`); // new pulumi.StackReference(`gitcoin/core-infra/${stack}`);
const RDS_SECRET_ARN = coreInfraStack.getOutput("rdsSecretArn");

const vpcID = coreInfraStack.getOutput("vpcId");
const vpcPrivateSubnetIds = coreInfraStack.getOutput("privateSubnetIds")
const vpcPublicSubnetIds = coreInfraStack.getOutput("publicSubnetIds")

const vpcPublicSubnetId1 = vpcPublicSubnetIds.apply(
  (values) => values[0]
);

const vpcPublicSubnetId2 = vpcPublicSubnetIds.apply(
  (values) => values[1]
);

const redisCacheOpsConnectionUrl= coreInfraStack.getOutput("redisConnectionUrl");

// This matches the default security group that awsx previously created when creating the Cluster.
// https://github.com/pulumi/pulumi-awsx/blob/45136c540f29eb3dc6efa5b4f51cfe05ee75c7d8/awsx-classic/ecs/cluster.ts#L110
const privateSubnetSecurityGroup = new aws.ec2.SecurityGroup(
  "private-subnet-secgrp",
  {
    description: "Security Group for Web Services",
    vpcId: vpcID,
    ingress: [
      {
        protocol: "TCP",
        fromPort: 22,
        toPort: 22,
        cidrBlocks: ["0.0.0.0/0"],
        description: "allow ssh in from any ipv4 address",
      },
      {
        protocol: "TCP",
        fromPort: 0,
        toPort: 65535,
        cidrBlocks: ["0.0.0.0/0"],
        description: "allow incoming tcp on any port from any ipv4 address",
      },
    ],
    egress: [
      {
        protocol: "-1",
        fromPort: 0,
        toPort: 0,
        cidrBlocks: ["0.0.0.0/0"],
        description: "allow output to any ipv4 address using any protocol",
      },
    ],
  }
);

const scorerDbProxyEndpoint =  coreInfraStack.getOutput("rdsProxyConnectionUrl"); 
const readreplica0ConnectionUrl = coreInfraStack.getOutput("readreplica0ConnectionUrl"); 

//////////////////////////////////////////////////////////////
// Set up ALB and ECS cluster
//////////////////////////////////////////////////////////////

const cluster = new aws.ecs.Cluster("scorer", {
  settings: [{ name: "containerInsights", value: "enabled" }],
});

// export const clusterInstance = cluster;
export const clusterId = cluster.id;

// Generate an SSL certificate
const certificate = new aws.acm.Certificate("cert", {
  domainName: `*.${domain}`,
  subjectAlternativeNames: [domain],
  tags: {
    Environment: "review",
  },
  validationMethod: "DNS",
});

const certificateValidationDomain = new aws.route53.Record(
  `${domain}-validation`,
  {
    name: certificate.domainValidationOptions[0].resourceRecordName,
    zoneId: route53Zone,
    type: certificate.domainValidationOptions[0].resourceRecordType,
    records: [certificate.domainValidationOptions[0].resourceRecordValue],
    ttl: 600
  }
);

const certificateValidation = new aws.acm.CertificateValidation(
  "certificateValidation",
  {
    certificateArn: certificate.arn,
    validationRecordFqdns: [certificateValidationDomain.fqdn],
  },
  { customTimeouts: { create: "30s", update: "30s" } }
);

// Create bucket for access logs
const accessLogsBucket = new aws.s3.Bucket(`gitcoin-scorer-access-logs`, {
  acl: "private",
  forceDestroy: true,
});

const serviceAccount = aws.elb.getServiceAccount({});

const accessLogsBucketPolicyDocument = aws.iam.getPolicyDocumentOutput({
  statements: serviceAccount.then((serviceAccount) => [
    {
      effect: "Allow",
      principals: [
        {
          type: "AWS",
          identifiers: [pulumi.interpolate`${serviceAccount.arn}`],
        },
      ],
      actions: ["s3:PutObject"],
      resources: [
        pulumi.interpolate`arn:aws:s3:::${accessLogsBucket.id}/AWSLogs/*`,
      ],
    },
    {
      effect: "Allow",
      principals: [
        {
          type: "Service",
          identifiers: ["logdelivery.elb.amazonaws.com"],
        },
      ],
      actions: ["s3:GetBucketAcl"],
      resources: [pulumi.interpolate`arn:aws:s3:::${accessLogsBucket.id}`],
    },
  ]),
});

const accessLogsBucketPolicy = new aws.s3.BucketPolicy(
  `gitcoin-accessLogs-policy`,
  {
    bucket: accessLogsBucket.id,
    policy: accessLogsBucketPolicyDocument.apply(
      (accessLogsBucketPolicyDocument) => accessLogsBucketPolicyDocument.json
    ),
  }
);

const albSecGrp = new aws.ec2.SecurityGroup(`scorer-service-alb`, {
  description: "scorer-service-alb",
  vpcId: vpcID,
  ingress: [
    { protocol: "tcp", fromPort: 80, toPort: 80, cidrBlocks: ["0.0.0.0/0"] },
    { protocol: "tcp", fromPort: 443, toPort: 443, cidrBlocks: ["0.0.0.0/0"] },
  ],
  egress: [
    { protocol: "tcp", fromPort: 80, toPort: 80, cidrBlocks: ["0.0.0.0/0"] },
    { protocol: "tcp", fromPort: 443, toPort: 443, cidrBlocks: ["0.0.0.0/0"] },
  ],
});

// Creates an ALB associated with our custom VPC.
const alb = new aws.alb.LoadBalancer(`scorer-service`, {
  loadBalancerType: "application",
  internal: false,
  securityGroups: [albSecGrp.id],
  subnets: vpcPublicSubnetIds,
  accessLogs: {
    bucket: accessLogsBucket.bucket,
    enabled: true,
  },
  tags: {
    name: "scorer-service",
  },
});

// Listen to HTTP traffic on port 80 and redirect to 443
const httpListener = new aws.alb.Listener("scorer-http-listener", {
  loadBalancerArn: alb.arn,
  port: 80,
  protocol: "HTTP",
  defaultActions: [
    {
      type: "redirect",
      redirect: {
        protocol: "HTTPS",
        port: "443",
        statusCode: "HTTP_301",
      },
    },
  ],
  tags: {
    name: "scorer-http-listener",
  },
});

//////////////////////////////////////////////////////////////
// Set up the target groups
//////////////////////////////////////////////////////////////

// Target group with the port of the Docker image
const targetGroupDefault = createTargetGroup("scorer-api-default", vpcID);
const targetGroupPassport = createTargetGroup("scorer-api-passport", vpcID);
const targetGroupRegistry = createTargetGroup("scorer-api-reg", vpcID);
const targetGroupRegistrySubmitPassport = createTargetGroup(
  "scorer-api-reg-sp",
  vpcID
);

//////////////////////////////////////////////////////////////
// Create the HTTPS listener, and set the default target group
//////////////////////////////////////////////////////////////
const httpsListener = new aws.alb.Listener("scorer-https-listener", {
  loadBalancerArn: alb.arn,
  protocol: "HTTPS",
  port: 443,
  certificateArn: certificateValidation.certificateArn,
  defaultActions: [
    {
      type: "forward",
      targetGroupArn: targetGroupDefault.arn,
    },
  ],
  tags: {
    name: "scorer-https-listener",
  },
}, {dependsOn: [certificateValidation, certificate]});

// Create a DNS record for the load balancer
const www = new aws.route53.Record("scorer", {
  zoneId: route53Zone,
  name: domain , //TODO: @Larisa - > make sure this works for production 
  type: "A",
  aliases: [
    {
      name: alb.dnsName,
      zoneId: alb.zoneId,
      evaluateTargetHealth: true,
    },
  ],
});

const dpoppEcsRole = new aws.iam.Role("dpoppEcsRole", {
  assumeRolePolicy: JSON.stringify({
    Version: "2012-10-17",
    Statement: [
      {
        Action: "sts:AssumeRole",
        Effect: "Allow",
        Sid: "",
        Principal: {
          Service: "ecs-tasks.amazonaws.com",
        },
      },
    ],
  }),
  inlinePolicies: [
    {
      name: "allow_exec",
      policy: JSON.stringify({
        Version: "2012-10-17",
        Statement: [
          {
            Effect: "Allow",
            Action: [
              "ssmmessages:CreateControlChannel",
              "ssmmessages:CreateDataChannel",
              "ssmmessages:OpenControlChannel",
              "ssmmessages:OpenDataChannel",
            ],
            Resource: "*",
          },
        ],
      }),
    },
    {
      name: "allow_iam_secrets_access",
      policy: JSON.stringify({
        Version: "2012-10-17",
        Statement: [
          {
            Action: ["secretsmanager:GetSecretValue"],
            Effect: "Allow",
            Resource: SCORER_SERVER_SSM_ARN,
          },
        ],
      }),
    },
  ],
  managedPolicyArns: [
    "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy",
  ],
  tags: {
    dpopp: "",
  },
});

const pagerdutyTopic = new aws.sns.Topic("pagerduty", {
  name: "Pagerduty",
  tracingConfig: "PassThrough",
});

// const PAGERDUTY_INTEGRATION_ENDPOINT = pulumi.secret(
//   pagerDutyIntegrationEndpoint
// );

const identity = aws.getCallerIdentity();

const pagerdutyTopicPolicy = new aws.sns.TopicPolicy("pagerdutyTopicPolicy", {
  arn: pagerdutyTopic.arn,
  policy: pagerdutyTopic.arn.apply((arn) =>
    identity.then(({ accountId }) =>
      JSON.stringify({
        Id: "__default_policy_ID",
        Statement: [
          {
            Action: [
              "SNS:GetTopicAttributes",
              "SNS:SetTopicAttributes",
              "SNS:AddPermission",
              "SNS:RemovePermission",
              "SNS:DeleteTopic",
              "SNS:Subscribe",
              "SNS:ListSubscriptionsByTopic",
              "SNS:Publish",
            ],
            Condition: {
              StringEquals: { "AWS:SourceOwner": accountId },
            },
            Effect: "Allow",
            Principal: { AWS: "*" },
            Resource: arn,
            Sid: "__default_statement_ID",
          },
        ],
        Version: "2008-10-17",
      })
    )
  ),
});

// const pagerdutySubscription = new aws.sns.TopicSubscription(
//   "pagerdutySubscription",
//   {
//     endpoint: PAGERDUTY_INTEGRATION_ENDPOINT,
//     protocol: "https",
//     topic: pagerdutyTopic.arn,
//   }
// );

const deadLetterQueue = createDeadLetterQueue({ alertTopic: pagerdutyTopic });

const rescoreQueue = createRescoreQueue({ deadLetterQueue });

const serviceTaskRole = new aws.iam.Role("scorer-service-execution-role", {
  assumeRolePolicy: JSON.stringify({
    Version: "2012-10-17",
    Statement: [
      {
        Action: "sts:AssumeRole",
        Effect: "Allow",
        Sid: "",
        Principal: {
          Service: "ecs-tasks.amazonaws.com",
        },
      },
    ],
  }),
  inlinePolicies: [
    {
      name: "allow_write_sqs",
      policy: rescoreQueue.arn.apply((rescoreQueueArn) =>
        JSON.stringify({
          Version: "2012-10-17",
          Statement: [
            {
              Effect: "Allow",
              Action: ["sqs:SendMessage"],
              Resource: rescoreQueueArn,
            },
          ],
        })
      ),
    },
  ],
});

const envConfig: ScorerEnvironmentConfig = {
  allowedHosts: JSON.stringify([domain, "*"]),
  domain: domain,
  csrfTrustedOrigins: JSON.stringify([`https://${domain}`]),
  rdsConnectionUrl: scorerDbProxyEndpoint,
  readReplicaConnectionUrl: readreplica0ConnectionUrl,
  redisCacheOpsConnectionUrl: redisCacheOpsConnectionUrl,
  uiDomains: JSON.stringify([
    "scorer." + rootDomain,
    "www.scorer." + rootDomain,
  ]),
  debug: "off",
  passportPublicUrl: "https://passport.gitcoin.co/",
  rescoreQueueUrl: rescoreQueue.url,
};

const environment = getEnvironment(envConfig);

//////////////////////////////////////////////////////////////
// Set up log groups for API service and worker
//////////////////////////////////////////////////////////////
const serviceLogGroup = new aws.cloudwatch.LogGroup("scorer-service", {
  retentionInDays: 90,
  tags: {
    name: `cloudwatch-loggroup-scorer-service`,
  },
});
const workerLogGroup = new aws.cloudwatch.LogGroup("scorer-worker", {
  retentionInDays: 90,
  tags: {
    name: `cloudwatch-loggroup-scorer-worker`,
  },
});

//////////////////////////////////////////////////////////////
// Set up the Scorer ECS service
//////////////////////////////////////////////////////////////
const baseScorerServiceConfig: ScorerService = {
  cluster,
  alb,
  dockerImageScorer: dockerGtcPassportScorerImage,
  dockerImageVerifier: dockerGtcPassportVerifierImage,
  executionRole: dpoppEcsRole,
  taskRole: serviceTaskRole,
  logGroup: serviceLogGroup,
  subnets: vpcPrivateSubnetIds,
  securityGroup: privateSubnetSecurityGroup,
  needsVerifier: false,
  httpListenerArn: httpsListener.arn,
  targetGroup: targetGroupDefault,
  autoScaleMaxCapacity: 20,
  autoScaleMinCapacity: 2,
  alertTopic: pagerdutyTopic,
};

const scorerServiceDefault = createScorerECSService(
  "scorer-api-default",
  {
    ...baseScorerServiceConfig,
    targetGroup: targetGroupDefault,
    memory: 1024,
    cpu: 512,
    desiredCount: 2,
  },
  envConfig
);

const scorerServiceRegistry = createScorerECSService(
  "scorer-api-reg",
  {
    ...baseScorerServiceConfig,
    listenerRulePriority: 3000,
    httpListenerRulePaths: ["/registry/*"],
    targetGroup: targetGroupRegistry,
    memory: 4096,
    cpu: 2048,
    desiredCount: 2,
  },
  envConfig
);

//////////////////////////////////////////////////////////////
// Set up the worker role
//////////////////////////////////////////////////////////////
const workerRole = RDS_SECRET_ARN.apply( (rdsSecrets) => new aws.iam.Role("scorer-bkgrnd-worker-role", {
  assumeRolePolicy: JSON.stringify({
    Version: "2012-10-17",
    Statement: [
      {
        Action: "sts:AssumeRole",
        Effect: "Allow",
        Sid: "",
        Principal: {
          Service: "ecs-tasks.amazonaws.com",
        },
      },
    ],
  }),
  inlinePolicies: [
    {
      name: "allow_exec",
      policy: JSON.stringify({
        Version: "2012-10-17",
        Statement: [
          {
            Effect: "Allow",
            Action: [
              "ssmmessages:CreateControlChannel",
              "ssmmessages:CreateDataChannel",
              "ssmmessages:OpenControlChannel",
              "ssmmessages:OpenDataChannel",
            ],
            Resource: "*",
          },
        ],
      }),
    },
    {
      name: "allow_iam_secrets_access",
      policy: JSON.stringify({
        Version: "2012-10-17",
        Statement: [
          {
            Action: ["secretsmanager:GetSecretValue"],
            Effect: "Allow",
            Resource: [SCORER_SERVER_SSM_ARN, rdsSecrets]
          },
        ],
      }),
    },
  ],
  managedPolicyArns: [
    "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy",
  ],
  tags: {
    dpopp: "",
  },
}));

const secgrp = new aws.ec2.SecurityGroup(`scorer-run-migrations-task`, {
  description: "gitcoin-ecs-task",
  vpcId: vpcID,
  ingress: [
    { protocol: "tcp", fromPort: 22, toPort: 22, cidrBlocks: ["0.0.0.0/0"] },
    { protocol: "tcp", fromPort: 80, toPort: 80, cidrBlocks: ["0.0.0.0/0"] },
  ],
  egress: [
    {
      protocol: "-1",
      fromPort: 0,
      toPort: 0,
      cidrBlocks: ["0.0.0.0/0"],
    },
  ],
});

export const securityGroupForTaskDefinition = secgrp.id;

//////////////////////////////////////////////////////////////
// Set up EC2 instance
//      - it is intended to be used for troubleshooting
//////////////////////////////////////////////////////////////

const ubuntu = aws.ec2.getAmi({
  mostRecent: true,
  filters: [
    {
      name: "name",
      values: ["ubuntu/images/hvm-ssd/ubuntu-focal-20.04-amd64-server-*"],
    },
    {
      name: "virtualization-type",
      values: ["hvm"],
    },
  ],
  owners: ["099720109477"],
});

// Script to install docker in ec2 instance
const ec2InitScript = `#!/bin/bash

# Installing docker in ubuntu
# Instructions taken from here: https://docs.docker.com/engine/install/ubuntu/

mkdir /var/log/gitcoin
echo $(date) "Starting installation of docker" >> /var/log/gitcoin/init.log
apt-get remove docker docker-engine docker.io containerd runc

apt-get update

apt-get install -y \
  ca-certificates \
  curl \
  gnupg \
  lsb-release

curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

echo \
"deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
$(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io awscli
mkdir /var/log/gitcoin
echo $(date) "Finished installation of docker" >> /var/log/gitcoin/init.log

echo $(date) "Installing postgresql client" >> /var/log/gitcoin/init.log
# Install postgresql client, instructions from here: https://www.postgresql.org/download/linux/ubuntu/
# Create the file repository configuration:
sh -c 'echo "deb https://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'

# Import the repository signing key:
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add -

# Update the package lists:
apt-get update

# Install the latest version of PostgreSQL.
# If you want a specific version, use 'postgresql-12' or similar instead of 'postgresql':
apt-get -y install postgresql-client-13

`;

const web = new aws.ec2.Instance("troubleshooting-instance", {
  ami: ubuntu.then((ubuntu) => ubuntu.id),
  associatePublicIpAddress: true,
  instanceType: "t3.medium",
  subnetId: vpcPublicSubnetId1,
  vpcSecurityGroupIds: [secgrp.id],
  rootBlockDevice: {
    volumeSize: 50,
  },
  tags: {
    name: "Passport Scorer - troubleshooting instance",
    Name: "Passport Scorer - troubleshooting instance",
  },
  userData: ec2InitScript,
});

export const ec2PublicIp = web.publicIp;
export const dockrRunCmd = pulumi.secret(
  pulumi.interpolate`docker run -it -e CERAMIC_CACHE_SCORER_ID=1  -e 'DATABASE_URL=${scorerDbProxyEndpoint}' -e 'CELERY_BROKER_URL=${redisCacheOpsConnectionUrl}' '${dockerGtcPassportScorerImage}' bash`
);

///////////////////////
// Redash instance
///////////////////////

const redashDbSecgrp = new aws.ec2.SecurityGroup(`redashDbSecgrp-fe96c4b`, {
  description: "Security Group for DB",
  vpcId: vpcID,
  ingress: [
    {
      protocol: "tcp",
      fromPort: 5432,
      toPort: 5432,
      cidrBlocks: ["0.0.0.0/0"],
    },
  ],
  egress: [
    {
      protocol: "-1",
      fromPort: 0,
      toPort: 0,
      cidrBlocks: ["0.0.0.0/0"],
    },
  ],
  name: "redashDbSecgrp-fe96c4b",
});

let dbSubnetGroup = new aws.rds.SubnetGroup(`scorer-db-subnet`, {
  subnetIds: vpcPrivateSubnetIds,
});

// Create an RDS instance
const redashDb = new aws.rds.Instance(
  "redash-db-0",
  {
    identifier: "redash-db-0",
    allocatedStorage: 20,
    maxAllocatedStorage: 20,
    engine: "postgres",
    engineVersion: "13.10",
    instanceClass: "db.t3.micro",
    dbName: redashDbName,
    password: redashDbPassword,
    username: redashDbUsername,
    skipFinalSnapshot: true,
    dbSubnetGroupName: dbSubnetGroup.id,
    vpcSecurityGroupIds: [redashDbSecgrp.id],
    backupRetentionPeriod: 5,
    performanceInsightsEnabled: true,
  },
  { protect: true }
);

const dbUrl = redashDb.endpoint;
export const redashDbUrl = pulumi.secret(
  pulumi.interpolate`postgresql://${redashDbUsername}:${redashDbPassword}@${dbUrl}/${redashDbName}`
);

const redashSecurityGroup = new aws.ec2.SecurityGroup(
  "redashServerSecurityGroup",
  {
    vpcId: vpcID,
    ingress: [
      {
        protocol: "tcp",
        fromPort: 443,
        toPort: 443,
        cidrBlocks: ["0.0.0.0/0"],
      }, // IPv4 HTTPS
      { protocol: "tcp", fromPort: 443, toPort: 443, ipv6CidrBlocks: ["::/0"] }, // IPv6 HTTPS
      { protocol: "tcp", fromPort: 22, toPort: 22, cidrBlocks: ["0.0.0.0/0"] }, // IPv4 SSH
      { protocol: "tcp", fromPort: 80, toPort: 80, cidrBlocks: ["0.0.0.0/0"] }, // IPv4 HTTP
      { protocol: "tcp", fromPort: 80, toPort: 80, ipv6CidrBlocks: ["::/0"] }, // IPv6 HTTP
      {
        protocol: "tcp",
        fromPort: 5000,
        toPort: 5000,
        cidrBlocks: ["0.0.0.0/0"],
      }, // IPv4 Custom TCP 5000
      {
        protocol: "tcp",
        fromPort: 5000,
        toPort: 5000,
        ipv6CidrBlocks: ["::/0"],
      }, // IPv6 Custom TCP 5000
    ],
    egress: [
      {
        protocol: "-1",
        fromPort: 0,
        toPort: 0,
        cidrBlocks: ["0.0.0.0/0"],
      },
    ],
  }
);

const redashInitScript = redashDbUrl.apply((url) =>
  redashDbPassword.apply((password) =>
    redashSecretKey.apply((secretKey) =>
      redashMailPassword.apply(
        (mailPassword) =>
          `#!/bin/bash

          echo "Setting environment variables..."
          export POSTGRES_PASSWORD="${password}"
          export REDASH_DATABASE_URL="${url}"
          export REDASH_SECRET_KEY="${secretKey}"
          export REDASH_MAIL_USERNAME="${redashMailUsername}"
          export REDASH_MAIL_PASSWORD="${mailPassword}"
          export REDASH_HOST="https://redash.api.staging.scorer.gitcoin.co"
          export REDASH_MAIL_DEFAULT_SENDER="passport+redash_staging@gitcoin.co"

          echo "Try to pull from git repo or clone the repo if it was not cloned before ..."
          git pull /passport-redash || git clone https://github.com/gitcoinco/passport-redash.git /passport-redash

          echo "Changing directory and setting permissions..."
          cd /passport-redash

          chmod +x ./setup.sh
          ./setup.sh

          cd data
          echo "Check docker compose version ..."
          docker-compose -v

          echo "Start docker-compose ..."
          docker-compose up -d
          `
      )
    )
  )
);

const redashinstance = new aws.ec2.Instance("redashinstance", {
  ami: ubuntu.then((ubuntu: { id: any }) => ubuntu.id),
  associatePublicIpAddress: true,
  instanceType: "t3.medium",
  subnetId: vpcPublicSubnetId2,
  rootBlockDevice: {
    volumeSize: 50,
  },
  tags: {
    name: "Redash Analytics",
    Name: "Redash Analytics",
  },
  userData: redashInitScript,
  vpcSecurityGroupIds: [redashSecurityGroup.id],
});

// Generate an SSL certificate
const redashCertificate = new aws.acm.Certificate("redash", {
  domainName: "redash." + domain,
  tags: {
    Environment: "staging",
  },
  validationMethod: "DNS",
});

const redashCertificateValidationDomain = new aws.route53.Record(
  `redash.${domain}-validation`,
  {
    name: redashCertificate.domainValidationOptions[0].resourceRecordName,
    zoneId: route53Zone,
    type: redashCertificate.domainValidationOptions[0].resourceRecordType,
    records: [redashCertificate.domainValidationOptions[0].resourceRecordValue],
    ttl: 600,
  }
);

const redashCertificateValidation = new aws.acm.CertificateValidation(
  "redashCertificateValidation",
  {
    certificateArn: redashCertificate.arn,
    validationRecordFqdns: [redashCertificateValidationDomain.fqdn],
  },
  { customTimeouts: { create: "30s", update: "30s" } }
);

const redashAlbSecGrp = new aws.ec2.SecurityGroup(`redash-service-alb`, {
  description: "redash-service-alb",
  vpcId: vpcID,
  ingress: [
    { protocol: "tcp", fromPort: 80, toPort: 80, cidrBlocks: ["0.0.0.0/0"] },
    { protocol: "tcp", fromPort: 443, toPort: 443, cidrBlocks: ["0.0.0.0/0"] },
  ],
  egress: [
    { protocol: "tcp", fromPort: 80, toPort: 80, cidrBlocks: ["0.0.0.0/0"] },
    { protocol: "tcp", fromPort: 443, toPort: 443, cidrBlocks: ["0.0.0.0/0"] },
  ],
});

// Creates an ALB associated with our custom VPC.
const redashAlb = new aws.alb.LoadBalancer(`redash-service`, {
  loadBalancerType: "application",
  internal: false,
  securityGroups: [redashAlbSecGrp.id],
  subnets: vpcPublicSubnetIds,
  tags: {
    name: "redash-service",
  },
});

// Listen to HTTP traffic on port 80 and redirect to 443
const redashHttpListener = new aws.alb.Listener("redash-http-listener", {
  loadBalancerArn: redashAlb.arn,
  port: 80,
  protocol: "HTTP",
  defaultActions: [
    {
      type: "redirect",
      redirect: {
        protocol: "HTTPS",
        port: "443",
        statusCode: "HTTP_301",
      },
    },
  ],
  tags: {
    name: "redash-http-listener",
  },
});

// Target group with the port of the UI
const redashTarget = new aws.alb.TargetGroup("redash-target", {
  vpcId: vpcID,
  targetType: "ip",
  port: 80,
  protocol: "HTTP",
  healthCheck: { path: "/ping", unhealthyThreshold: 5 },
});

// Listen to traffic on port 443 & route it through the target group
const redashHttpsListener = new aws.alb.Listener("redash-https-listener", {
  loadBalancerArn: redashAlb.arn,
  port: 443,
  protocol: "HTTPS",
  certificateArn: redashCertificate.arn,
  defaultActions: [
    {
      type: "forward",
      targetGroupArn: redashTarget.arn,
    },
  ],
  tags: {
    name: "redash-https-listener",
  },
});

const redashRecord = new aws.route53.Record("redash", {
  zoneId: route53Zone,
  name: "redash." + domain,
  type: "A",
  aliases: [
    {
      name: redashAlb.dnsName,
      zoneId: redashAlb.zoneId,
      evaluateTargetHealth: true,
    },
  ],
});

new aws.lb.TargetGroupAttachment("redashTargetAttachment", {
  targetId: redashinstance.privateIp,
  targetGroupArn: redashTarget.arn,
});

export const weeklyDataDumpTaskDefinition = createScheduledTask(
  "weekly-data-dump",
  {
    ...baseScorerServiceConfig,
    securityGroup: secgrp,
    command: "python manage.py dump_stamp_data",
    scheduleExpression: "cron(30 23 ? * FRI *)", // Run the task every friday at 23:30 UTC
    alertTopic: pagerdutyTopic,
  },
  envConfig
);

export const dailyDataDumpTaskDefinition = createScheduledTask(
  "daily-data-dump",
  {
    ...baseScorerServiceConfig,
    cpu: 1024,
    memory: 2048,
    securityGroup: secgrp,
    ephemeralStorageSizeInGiB: 100,
    command: [
      "python",
      "manage.py",
      "scorer_dump_data",
      "--config",
      "'" +
        JSON.stringify([
          { name: "ceramic_cache.CeramicCache", "extra-args": {} },
          { name: "registry.Event", "extra-args": {} },
          { name: "registry.HashScorerLink", "extra-args": {} },
          {
            name: "registry.Stamp",
            select_related: ["passport"],
            "extra-args": {},
          },
        ]) +
        "'",
      "--s3-uri=s3://passport-scorer/daily_data_dumps/",
      "--batch-size=20000",
    ].join(" "),
    scheduleExpression: "cron(30 0 ? * * *)", // Run the task daily at 00:30 UTC
    alertTopic: pagerdutyTopic,
  },
  envConfig
);

export const dailyDataDumpTaskDefinitionParquet = createScheduledTask(
  "daily-data-dump-parquet",
  {
    ...baseScorerServiceConfig,
    cpu: 1024,
    memory: 2048,
    securityGroup: secgrp,
    ephemeralStorageSizeInGiB: 100,
    command: [
      "python",
      "manage.py",
      "scorer_dump_data_parquet",
      "--apps=registry,ceramic_cache,account,scorer_weighted,trusta_labs",
      "--s3-uri=s3://passport-scorer/daily_data_dumps/",
      "--batch-size=20000",
    ].join(" "),
    scheduleExpression: "cron(30 0 ? * * *)", // Run the task daily at 00:30 UTC
    alertTopic: pagerdutyTopic,
  },
  envConfig
);

// The follosing scorer dumps the Allo scorer scores to a public S3 bucket
// for the Allo team to easily pull the data
export const frequentAlloScorerDataDumpTaskDefinition = createScheduledTask(
  "frequent-allo-scorer-data-dump",
  {
    ...baseScorerServiceConfig,
    securityGroup: secgrp,
    command: [
      "python",
      "manage.py",
      "scorer_dump_data",
      "--config",
      "'" +
        JSON.stringify([
          {
            name: "registry.Score",
            filter: { community_id: 335 },
            select_related: ["passport"],
          },
        ]) +
        "'",
      `--s3-uri=s3://${publicDataDomain}/passport_scores/`,
      // "--summary-extra-args",
      // JSON.stringify({ ACL: "public-read" }),
    ].join(" "),
    scheduleExpression: "cron(*/30 * ? * * *)", // Run the task every 30 min
    alertTopic: pagerdutyTopic,
  },
  envConfig
);

const exportVals = createScoreExportBucketAndDomain(
  stack == "production" ? publicDataDomain : `${stack}-${publicDataDomain}`,
  publicDataDomain,
  route53ZoneForPublicData
);

const rdsConnectionConfig = {
  dbHost: scorerDbProxyEndpoint,
  dbPort: String(5432),
};

workerRole.apply ((serviceRole) => createIndexerService({
  rdsConnectionConfig,
  rdsSecretArn: RDS_SECRET_ARN,
  cluster,
  vpc: vpcID,
  privateSubnetIds: vpcPrivateSubnetIds,
  privateSubnetSecurityGroup,
  workerRole: serviceRole,
  alertTopic: pagerdutyTopic,
}));

const {
  httpLambdaRole,
  queueLambdaRole,
  httpRoleAttachments,
  queueRoleAttachments,
} = createSharedLambdaResources({
  rescoreQueue,
});

const lambdaSettings = {
  httpsListener,
  imageUri: dockerGtcSubmitPassportLambdaImage,
  privateSubnetSecurityGroup,
  vpcPrivateSubnetIds,
  environment: [
    ...environment,
    {
      name: "TRUSTED_IAM_ISSUERS",
      value: trustedIAMIssuers,
    },
    {
      name: "FF_API_ANALYTICS",
      value: "on",
    },
    {
      name: "CERAMIC_CACHE_SCORER_ID",
      value: "1", //  TODO: @Larisa, this changes for each  env
    },
    {
      name: "SCORER_SERVER_SSM_ARN",
      value: SCORER_SERVER_SSM_ARN,
    },
  ],
  roleAttachments: httpRoleAttachments,
  role: httpLambdaRole,
};

buildHttpLambdaFn({
  ...lambdaSettings,
  name: "submit-passport",
  memorySize: 1024,
  dockerCmd: ["aws_lambdas.submit_passport.submit_passport.handler"],
  pathPatterns: ["/registry/submit-passport", "/registry/v2/submit-passport"],
  listenerPriority: 1001,
});

buildHttpLambdaFn({
  ...lambdaSettings,
  name: "cc-v1-st-bulk-POST",
  memorySize: 512,
  dockerCmd: ["aws_lambdas.scorer_api_passport.v1.stamps.bulk_POST.handler"],
  pathPatterns: ["/ceramic-cache/stamps/bulk"],
  httpRequestMethods: ["POST"],
  listenerPriority: 1002,
});

buildHttpLambdaFn({
  ...lambdaSettings,
  name: "cc-v1-st-bulk-PATCH",
  memorySize: 512,
  dockerCmd: ["aws_lambdas.scorer_api_passport.v1.stamps.bulk_PATCH.handler"],
  pathPatterns: ["/ceramic-cache/stamps/bulk"],
  httpRequestMethods: ["PATCH"],
  listenerPriority: 1003,
});

buildHttpLambdaFn({
  ...lambdaSettings,
  name: "cc-v1-st-bulk-DELETE",
  memorySize: 512,
  dockerCmd: ["aws_lambdas.scorer_api_passport.v1.stamps.bulk_DELETE.handler"],
  pathPatterns: ["/ceramic-cache/stamps/bulk"],
  httpRequestMethods: ["DELETE"],
  listenerPriority: 1004,
});

buildHttpLambdaFn({
  ...lambdaSettings,
  name: "cc-auhenticate",
  memorySize: 512,
  dockerCmd: ["aws_lambdas.scorer_api_passport.v1.authenticate_POST.handler"],
  pathPatterns: ["/ceramic-cache/authenticate"],
  httpRequestMethods: ["POST"],
  listenerPriority: 1005,
});

buildHttpLambdaFn({
  ...lambdaSettings,
  name: "cc-v1-score-POST",
  memorySize: 512,
  dockerCmd: ["aws_lambdas.scorer_api_passport.v1.score_POST.handler"],
  pathPatterns: ["/ceramic-cache/score/*"],
  httpRequestMethods: ["POST"],
  listenerPriority: 1006,
});

buildHttpLambdaFn({
  ...lambdaSettings,
  name: "cc-v1-score-GET",
  memorySize: 512,
  dockerCmd: ["aws_lambdas.scorer_api_passport.v1.score_GET.handler"],
  pathPatterns: ["/ceramic-cache/score/*"],
  httpRequestMethods: ["GET"],
  listenerPriority: 1007,
});

buildHttpLambdaFn({
  ...lambdaSettings,
  name: "cc-weights-GET",
  memorySize: 512,
  dockerCmd: ["aws_lambdas.scorer_api_passport.v1.weights_GET.handler"],
  pathPatterns: ["/ceramic-cache/weights"],
  httpRequestMethods: ["GET"],
  listenerPriority: 1015,
});

buildHttpLambdaFn({
  ...lambdaSettings,
  name: "cc-v1-st-GET",
  memorySize: 512,
  dockerCmd: ["aws_lambdas.scorer_api_passport.v1.stamp_GET.handler"],
  pathPatterns: ["/ceramic-cache/stamp"],
  httpRequestMethods: ["GET"],
  listenerPriority: 1010,
});

buildQueueLambdaFn({
  ...lambdaSettings,
  name: "rescore",
  memorySize: 1024,
  dockerCmd: ["aws_lambdas.rescore.handler"],
  roleAttachments: queueRoleAttachments,
  role: queueLambdaRole,
  queue: rescoreQueue,
});
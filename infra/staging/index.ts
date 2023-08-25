import * as pulumi from "@pulumi/pulumi";
import * as aws from "@pulumi/aws";
import * as awsx from "@pulumi/awsx";
import { Listener } from "@pulumi/aws/lb";

import {
  ScorerEnvironmentConfig,
  ScorerService,
  createScorerECSService,
  createTargetGroup,
  getEnvironment,
  secrets,
} from "./gitcoin";

import {
  ScorerEnvironmentConfig,
  ScorerService,
  createScorerECSService,
  createTargetGroup,
  getEnvironment,
  secrets,
} from "../lib/scorer/service";

// The following vars are not allowed to be undefined, hence the `${...}` magic

let route53Zone = `${process.env["ROUTE_53_ZONE"]}`;
export const domain = `api.staging.scorer.${process.env["DOMAIN"]}`;
export const publicServiceUrl = `https://${domain}`;

let SCORER_SERVER_SSM_ARN = `${process.env["SCORER_SERVER_SSM_ARN"]}`;
let dbUsername = `${process.env["DB_USER"]}`;
let dbPassword = pulumi.secret(`${process.env["DB_PASSWORD"]}`);
let dbName = `${process.env["DB_NAME"]}`;
let flowerUser = `${process.env["FLOWER_USER"]}`;
let flowerPassword = `${process.env["FLOWER_PASSWORD"]}`;

export const dockerGtcPassportScorerImage = `${process.env["DOCKER_GTC_PASSPORT_SCORER_IMAGE"]}`;
export const dockerGtcPassportVerifierImage = `${process.env["DOCKER_GTC_PASSPORT_VERIFIER_IMAGE"]}`;

//////////////////////////////////////////////////////////////
// Set up VPC
//////////////////////////////////////////////////////////////

const vpc = new awsx.ec2.Vpc("scorer", {
  subnets: [{ type: "public" }, { type: "private", mapPublicIpOnLaunch: true }],
});

export const vpcID = vpc.id;
export const vpcPrivateSubnetIds = vpc.privateSubnetIds;
export const vpcPublicSubnetIds = vpc.publicSubnetIds;
export const vpcPrivateSubnetId1 = vpcPrivateSubnetIds.then(
  (values) => values[0]
);
export const vpcPublicSubnetId1 = vpcPublicSubnetIds.then(
  (values) => values[0]
);
export const vpcPrivateSubnetId2 = vpcPrivateSubnetIds.then(
  (values) => values[1]
);
export const vpcPublicSubnetId2 = vpcPublicSubnetIds.then(
  (values) => values[1]
);

export const vpcPublicSubnet1 = vpcPublicSubnetIds.then((subnets) => {
  return subnets[0];
});

//////////////////////////////////////////////////////////////
// Set up RDS instance
//////////////////////////////////////////////////////////////
let dbSubnetGroup = new aws.rds.SubnetGroup(`scorer-db-subnet`, {
  subnetIds: vpcPrivateSubnetIds,
});

const db_secgrp = new aws.ec2.SecurityGroup(`scorer-db-secgrp`, {
  description: "Security Group for DB",
  vpcId: vpc.id,
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
});

const postgresql = new aws.rds.Instance(
  `scorer-db`,
  {
    allocatedStorage: 20,
    maxAllocatedStorage: 100,
    engine: "postgres",
    // engineVersion: "5.7",
    instanceClass: "db.t3.2xlarge",
    dbName: dbName,
    password: dbPassword,
    username: dbUsername,
    skipFinalSnapshot: true,
    dbSubnetGroupName: dbSubnetGroup.id,
    vpcSecurityGroupIds: [db_secgrp.id],
    backupRetentionPeriod: 5,
    performanceInsightsEnabled: true,
  },
  { protect: true }
);

export const rdsEndpoint = postgresql.endpoint;
export const rdsArn = postgresql.arn;
export const rdsConnectionUrl = pulumi.secret(
  pulumi.interpolate`psql://${dbUsername}:${dbPassword}@${rdsEndpoint}/${dbName}`
);
export const rdsId = postgresql.id;

//////////////////////////////////////////////////////////////
// Set up Redis
//////////////////////////////////////////////////////////////

const redisSubnetGroup = new aws.elasticache.SubnetGroup(
  "scorer-redis-subnet",
  {
    subnetIds: vpcPrivateSubnetIds,
  }
);

const secgrp_redis = new aws.ec2.SecurityGroup("scorer-redis-secgrp", {
  description: "scorer",
  vpcId: vpc.id,
  ingress: [
    {
      protocol: "tcp",
      fromPort: 6379,
      toPort: 6379,
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
});

const redis = new aws.elasticache.Cluster("scorer-redis", {
  engine: "redis",
  engineVersion: "4.0.10",
  nodeType: "cache.m5.large",
  numCacheNodes: 1,
  port: 6379,
  subnetGroupName: redisSubnetGroup.name,
  securityGroupIds: [secgrp_redis.id],
});

export const redisPrimaryNode = redis.cacheNodes[0];
// export const redisConnectionUrl = pulumi.interpolate`rediscache://${redisPrimaryNode.address}:${redisPrimaryNode.port}/0?client_class=django_redis.client.DefaultClient`
export const redisCacheOpsConnectionUrl = pulumi.interpolate`redis://${redisPrimaryNode.address}:${redisPrimaryNode.port}/0`;

//////////////////////////////////////////////////////////////
// Set up ALB and ECS cluster
//////////////////////////////////////////////////////////////

const cluster = new awsx.ecs.Cluster("scorer", { vpc });
// export const clusterInstance = cluster;
export const clusterId = cluster.id;

// Generate an SSL certificate
const certificate = new aws.acm.Certificate("cert", {
  domainName: domain,
  tags: {
    Environment: "staging",
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
    ttl: 600,
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

// Creates an ALB associated with our custom VPC.
const alb = new awsx.lb.ApplicationLoadBalancer(`scorer-service`, { vpc });

// Listen to HTTP traffic on port 80 and redirect to 443
const httpListener = alb.createListener("web-listener", {
  port: 80,
  protocol: "HTTP",
  defaultAction: {
    type: "redirect",
    redirect: {
      protocol: "HTTPS",
      port: "443",
      statusCode: "HTTP_301",
    },
  },
});

//////////////////////////////////////////////////////////////
// Set up the target groups
//////////////////////////////////////////////////////////////
// Target group with the port of the Docker image
const target = alb.createTargetGroup("scorer-api-default", {
  vpc,
  port: 80,
  healthCheck: { path: "/health/", unhealthyThreshold: 5 },
});

const targetGroupDefault = target.targetGroup;
const targetGroupPassport = createTargetGroup("scorer-api-passport", vpcID);
const targetGroupRegistry = createTargetGroup("scorer-api-reg", vpcID);
const targetGroupRegistrySubmitPassport = createTargetGroup(
  "scorer-api-reg-sp",
  vpcID
);

//////////////////////////////////////////////////////////////
// Create the HTTPS listener, and set the default target group
//////////////////////////////////////////////////////////////
const httpsListener = target.createListener("scorer-listener", {
  port: 443,
  certificateArn: certificateValidation.certificateArn,
});

// Create a DNS record for the load balancer
const www = new aws.route53.Record("scorer", {
  zoneId: route53Zone,
  name: domain,
  type: "A",
  aliases: [
    {
      name: httpsListener.endpoint.hostname,
      zoneId: httpsListener.loadBalancer.loadBalancer.zoneId,
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

const envConfig: ScorerEnvironmentConfig = {
  allowedHosts: JSON.stringify([domain, "*"]),
  domain: domain,
  csrfTrustedOrigins: JSON.stringify([`https://${domain}`]),
  rdsConnectionUrl: rdsConnectionUrl,
  redisCacheOpsConnectionUrl: redisCacheOpsConnectionUrl,
  uiDomains: JSON.stringify([
    "scorer." + process.env["DOMAIN"],
    "www.scorer." + process.env["DOMAIN"],
  ]),
  debug: "off",
  passportPublicUrl: "https://staging.passport.gitcoin.co/",
};
const environment = getEnvironment(envConfig);

//////////////////////////////////////////////////////////////
// Set up log groups for API service and worker
//////////////////////////////////////////////////////////////
const serviceLogGroup = new aws.cloudwatch.LogGroup("scorer-service", {
  retentionInDays: 90,
});
const workerLogGroup = new aws.cloudwatch.LogGroup("scorer-worker", {
  retentionInDays: 90,
});

//////////////////////////////////////////////////////////////
// Set up the Scorer ECS service
//////////////////////////////////////////////////////////////
const baseScorerServiceConfig: ScorerService = {
  cluster: cluster,
  dockerImageScorer: dockerGtcPassportScorerImage,
  dockerImageVerifier: dockerGtcPassportVerifierImage,
  executionRole: dpoppEcsRole,
  logGroup: serviceLogGroup,
  subnets: vpc.privateSubnetIds,
  needsVerifier: false,
  httpListenerArn: httpsListener.listener.arn,
  targetGroup: targetGroupDefault,
  autoScaleMaxCapacity: 2,
  autoScaleMinCapacity: 1,
};

const scorerServiceDefault = createScorerECSService(
  "scorer-api-default",
  {
    ...baseScorerServiceConfig,
    targetGroup: targetGroupDefault,
  },
  envConfig
);

const scorerServicePassport = createScorerECSService(
  "scorer-api-passport",
  {
    ...baseScorerServiceConfig,
    needsVerifier: true,
    listenerRulePriority: 2000,
    httpListenerRulePaths: ["/ceramic-cache/*"],
    targetGroup: targetGroupPassport,
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
  },
  envConfig
);

const scorerServiceRegistrySubmitPassport = createScorerECSService(
  "scorer-api-reg-sp", // scorer-registry-submit-passport
  {
    ...baseScorerServiceConfig,
    listenerRulePriority: 2500,
    httpListenerRulePaths: ["/registry/submit-passport"],
    targetGroup: targetGroupRegistrySubmitPassport,
  },
  envConfig
);

//////////////////////////////////////////////////////////////
// Set up the Celery Worker Secrvice
//////////////////////////////////////////////////////////////
const workerRole = new aws.iam.Role("scorer-bkgrnd-worker-role", {
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

const celery1 = new awsx.ecs.FargateService("scorer-bkgrnd-worker-registry", {
  cluster,
  desiredCount: 0,
  subnets: vpc.privateSubnetIds,
  taskDefinitionArgs: {
    logGroup: workerLogGroup,
    executionRole: workerRole,
    containers: {
      worker1: {
        memory: 2048,
        cpu: 2000,
        image: dockerGtcPassportScorerImage,
        command: [
          "celery",
          "-A",
          "scorer",
          "worker",
          "-Q",
          "score_registry_passport",
          "-l",
          "DEBUG",
          "-c",
          "32",
        ],
        portMappings: [],
        secrets: secrets,
        environment: environment,
        dependsOn: [],
        links: [],
      },
    },
  },
});

const ecsScorerWorker1AutoscalingTarget = new aws.appautoscaling.Target(
  "scorer-worker1-autoscaling-target",
  {
    maxCapacity: 4,
    minCapacity: 0,
    resourceId: pulumi.interpolate`service/${cluster.cluster.name}/${celery1.service.name}`,
    scalableDimension: "ecs:service:DesiredCount",
    serviceNamespace: "ecs",
  }
);

const ecsScorerWorker1Autoscaling = new aws.appautoscaling.Policy(
  "scorer-worker1-autoscaling-policy",
  {
    policyType: "TargetTrackingScaling",
    resourceId: ecsScorerWorker1AutoscalingTarget.resourceId,
    scalableDimension: ecsScorerWorker1AutoscalingTarget.scalableDimension,
    serviceNamespace: ecsScorerWorker1AutoscalingTarget.serviceNamespace,
    targetTrackingScalingPolicyConfiguration: {
      predefinedMetricSpecification: {
        predefinedMetricType: "ECSServiceAverageCPUUtilization",
      },
      targetValue: 30,
      scaleInCooldown: 300,
      scaleOutCooldown: 300,
    },
  }
);

const celery2 = new awsx.ecs.FargateService("scorer-bkgrnd-worker-passport", {
  cluster,
  desiredCount: 1,
  subnets: vpc.privateSubnetIds,
  taskDefinitionArgs: {
    executionRole: workerRole,
    containers: {
      worker1: {
        image: dockerGtcPassportScorerImage,
        command: [
          "celery",
          "-A",
          "scorer",
          "worker",
          "-Q",
          "score_passport_passport",
          "-l",
          "DEBUG",
        ],
        memory: 4096,
        cpu: 2000,
        portMappings: [],
        secrets: secrets,
        environment: environment,
        dependsOn: [],
        links: [],
      },
    },
  },
});

const ecsScorerWorker2AutoscalingTarget = new aws.appautoscaling.Target(
  "scorer-worker2-autoscaling-target",
  {
    maxCapacity: 4,
    minCapacity: 2,
    resourceId: pulumi.interpolate`service/${cluster.cluster.name}/${celery2.service.name}`,
    scalableDimension: "ecs:service:DesiredCount",
    serviceNamespace: "ecs",
  }
);

const ecsScorerWorker2Autoscaling = new aws.appautoscaling.Policy(
  "scorer-worker2-autoscaling-policy",
  {
    policyType: "TargetTrackingScaling",
    resourceId: ecsScorerWorker2AutoscalingTarget.resourceId,
    scalableDimension: ecsScorerWorker2AutoscalingTarget.scalableDimension,
    serviceNamespace: ecsScorerWorker2AutoscalingTarget.serviceNamespace,
    targetTrackingScalingPolicyConfiguration: {
      predefinedMetricSpecification: {
        predefinedMetricType: "ECSServiceAverageCPUUtilization",
      },
      targetValue: 30,
      scaleInCooldown: 300,
      scaleOutCooldown: 300,
    },
  }
);

// Flower

// Generate an SSL certificate
const flowerCertificate = new aws.acm.Certificate("flower", {
  domainName: "flower." + domain,
  tags: {
    Environment: "staging",
  },
  validationMethod: "DNS",
});

const flowerCertificateValidationDomain = new aws.route53.Record(
  `flower.${domain}-validation`,
  {
    name: flowerCertificate.domainValidationOptions[0].resourceRecordName,
    zoneId: route53Zone,
    type: flowerCertificate.domainValidationOptions[0].resourceRecordType,
    records: [flowerCertificate.domainValidationOptions[0].resourceRecordValue],
    ttl: 600,
  }
);

const flowerCertificateValidation = new aws.acm.CertificateValidation(
  "flowerCertificateValidation",
  {
    certificateArn: flowerCertificate.arn,
    validationRecordFqdns: [flowerCertificateValidationDomain.fqdn],
  },
  { customTimeouts: { create: "30s", update: "30s" } }
);

// Creates an ALB associated with our custom VPC.
const flowerAlb = new awsx.lb.ApplicationLoadBalancer(`flower-service`, {
  vpc,
});

// Listen to HTTP traffic on port 80 and redirect to 443
const flowerHttpListener = flowerAlb.createListener("flower-listener", {
  port: 80,
  protocol: "HTTP",
  defaultAction: {
    type: "redirect",
    redirect: {
      protocol: "HTTPS",
      port: "443",
      statusCode: "HTTP_301",
    },
  },
});

// Target group with the port of the Docker image
const flowerTarget = flowerAlb.createTargetGroup("flower-target", {
  vpc,
  port: 5555,
  protocol: "HTTP",
  healthCheck: { path: "/healthcheck", unhealthyThreshold: 5 },
});

// Listen to traffic on port 443 & route it through the target group
const flowerHttpsListener = flowerTarget.createListener("flower-listener", {
  port: 443,
  certificateArn: flowerCertificate.arn,
});

const flowerRecord = new aws.route53.Record("flower", {
  zoneId: route53Zone,
  name: "flower." + domain,
  type: "A",
  aliases: [
    {
      name: flowerHttpsListener.endpoint.hostname,
      zoneId: flowerHttpsListener.loadBalancer.loadBalancer.zoneId,
      evaluateTargetHealth: true,
    },
  ],
});

const flower = new awsx.ecs.FargateService("flower", {
  cluster,
  desiredCount: 1,
  taskDefinitionArgs: {
    containers: {
      celery: {
        image: "mher/flower",
        command: ["celery", "flower", "-A", "taskapp", "--port=5555"],
        memory: 4096,
        cpu: 2000,
        portMappings: [flowerHttpsListener],
        environment: [
          {
            name: "BROKER_URL",
            value: redisCacheOpsConnectionUrl,
          },
          {
            name: "FLOWER_BASIC_AUTH",
            value: flowerUser + ":" + flowerPassword,
          },
        ],
        dependsOn: [],
        links: [],
      },
    },
  },
});

const secgrp = new aws.ec2.SecurityGroup(`scorer-run-migrations-task`, {
  description: "gitcoin-ecs-task",
  vpcId: vpc.id,
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

`;

const web = new aws.ec2.Instance("Web", {
  ami: ubuntu.then((ubuntu) => ubuntu.id),
  associatePublicIpAddress: true,
  instanceType: "t3.medium",
  subnetId: vpcPublicSubnetId1.then(),

  vpcSecurityGroupIds: [secgrp.id],
  rootBlockDevice: {
    volumeSize: 50,
  },
  tags: {
    Name: "Passport Scorer - troubleshooting instance",
  },
  userData: ec2InitScript,
});

export const ec2PublicIp = web.publicIp;
export const dockrRunCmd = pulumi.secret(
  pulumi.interpolate`docker run -it -e 'DATABASE_URL=${rdsConnectionUrl}' -e 'CELERY_BROKER_URL=${redisCacheOpsConnectionUrl}' '${dockerGtcPassportScorerImage}' bash`
);

///////////////////////
// Redash instance
///////////////////////

const redashDbSecgrp = new aws.ec2.SecurityGroup(`redashDbSecgrp`, {
  description: "Security Group for DB",
  vpcId: vpc.id,
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
});

let redashDbUsername = `${process.env["REDASH_DB_USER"]}`;
let redashDbPassword = pulumi.secret(`${process.env["REDASH_DB_PASSWORD"]}`);
let redashDbName = `${process.env["REDASH_DB_NAME"]}`;

// Create an RDS instance
const redashDb = new aws.rds.Instance(
  "redash-db",
  {
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
    vpcId: vpc.id,
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

// const redashDbUrlString = redashDbUrl.apply((url) => url).toString();

const redashInitScript = redashDbUrl.apply(
  (url) => `#!/bin/bash
echo "Setting environment variables..."
export POSTGRES_PASSWORD="${redashDbPassword}"
export REDASH_DATABASE_URL="${url}"

echo "Cloning passport-redash repository..."
git clone https://github.com/gitcoinco/passport-redash.git

echo "Changing directory and setting permissions..."
cd passport-redash
sudo chmod +x ./setup.sh
./setup.sh

cd data

sudo docker-compose run --rm server create_db
sudo docker-compose up -d

`
);

const redashinstance = new aws.ec2.Instance("redashinstance", {
  ami: ubuntu.then((ubuntu) => ubuntu.id),
  associatePublicIpAddress: true,
  instanceType: "t3.medium",
  subnetId: vpcPublicSubnetId2.then(),
  rootBlockDevice: {
    volumeSize: 50,
  },
  tags: {
    Name: "Redash Analytics",
  },
  userData: redashInitScript,
  securityGroups: [redashSecurityGroup.id],
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

// Creates an ALB associated with our custom VPC.
const redashAlb = new awsx.lb.ApplicationLoadBalancer(`redash-service`, {
  vpc,
});

// Listen to HTTP traffic on port 80 and redirect to 443
const redashHttpListener = redashAlb.createListener("redash-listener", {
  port: 80,
  protocol: "HTTP",
  defaultAction: {
    type: "redirect",
    redirect: {
      protocol: "HTTPS",
      port: "443",
      statusCode: "HTTP_301",
    },
  },
});

// Target group with the port of the UI
const redashTarget = redashAlb.createTargetGroup("redash-target", {
  vpc,
  port: 80,
  protocol: "HTTP",
  healthCheck: { path: "/ping", unhealthyThreshold: 5 },
});

// Listen to traffic on port 443 & route it through the target group
const redashHttpsListener = redashTarget.createListener("redash-listener", {
  port: 443,
  certificateArn: redashCertificate.arn,
});

const redashRecord = new aws.route53.Record("redash", {
  zoneId: route53Zone,
  name: "redash." + domain,
  type: "A",
  aliases: [
    {
      name: redashHttpsListener.endpoint.hostname,
      zoneId: redashHttpsListener.loadBalancer.loadBalancer.zoneId,
      evaluateTargetHealth: true,
    },
  ],
});

new aws.lb.TargetGroupAttachment("redashTargetAttachment", {
  targetId: redashinstance.privateIp,
  targetGroupArn: redashTarget.targetGroup.arn,
});

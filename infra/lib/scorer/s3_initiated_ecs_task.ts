import * as aws from "@pulumi/aws";
import { Input, Output } from "@pulumi/pulumi";

export function createS3InitiatedECSTask(
  bucketName: string,
  clusterArn: Output<string>,
  taskDefinitionArn: Output<string>,
  subnetIds: Output<any>,
  securityGroupIds: Output<string>[],
  eventsStsAssumeRoleArn: Input<string>,
) {
  // Create S3 bucket
  const bucket = new aws.s3.Bucket(bucketName, {
    bucket: bucketName,
  });

  // Enable S3 event notifications to EventBridge
  new aws.s3.BucketNotification(`${bucketName}-notification`, {
    bucket: bucket.id,
    eventbridge: true,
  });

  const folders = ["address-lists/", "model-score-results/"];
  folders.forEach((folder) => {
    new aws.s3.BucketObject(`${folder}`, {
      bucket: bucket.id,
      key: folder,
      content: "",
    });
  });

  // Create EventBridge rule
  const rule = new aws.cloudwatch.EventRule("s3-to-ecs-rule", {
    eventPattern: JSON.stringify({
      source: ["aws.s3"],
      "detail-type": ["Object Created"],
      detail: {
        bucket: {
          name: [bucketName],
        },
        object: {
          key: [{
            prefix: "address-lists/"
          }]
        }
      },
    }),
  });

  // Create EventBridge target
  new aws.cloudwatch.EventTarget("ecs-task-target", {
    rule: rule.name,
    arn: clusterArn,
    roleArn: eventsStsAssumeRoleArn,
    ecsTarget: {
      taskDefinitionArn: taskDefinitionArn,
      taskCount: 1,
      launchType: "FARGATE",
      networkConfiguration: {
        assignPublicIp: false,
        subnets: subnetIds,
        securityGroups: securityGroupIds,
      },
    },
  });

  return {
    bucketName: bucket.id,
    eventBridgeRuleArn: rule.arn,
  };
}

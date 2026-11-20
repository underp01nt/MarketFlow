/*
    Definition of AWS resources to run the MarketFlow poller:
        - CloudWatch Log Group
        - An ECS cluster
        - An ECS task definition
*/

resource "aws_cloudwatch_log_group" "poller" {
  name              = var.log_group_name
  retention_in_days = 30
}

resource "aws_ecs_cluster" "main" {
  name = var.ecs_cluster_name
}

# ECS Fargate task definition
resource "aws_ecs_task_definition" "poller" {
  family                   = var.task_definition_family
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "256"
  memory                   = "1024"

  execution_role_arn = aws_iam_role.execution.arn
  task_role_arn      = aws_iam_role.task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  depends_on = [
    aws_iam_role_policy_attachment.execution_managed,
    aws_iam_role_policy.execution_secrets,
    aws_iam_role_policy.task_s3
  ]

  container_definitions = jsonencode([
    {
      name      = "marketflow-poller"
      image     = "${aws_ecr_repository.poller.repository_url}:${var.image_tag}"
      essential = true

      environment = [
        {
          name  = "S3_BUCKET"
          value = aws_s3_bucket.data.bucket
        },
        {
          name  = "AWS_REGION"
          value = var.aws_region
        }
      ]

      secrets = [
        {
          name      = "WEBULL_APP_KEY"
          valueFrom = "${aws_secretsmanager_secret.webull.arn}:WEBULL_APP_KEY::"
        },
        {
          name      = "WEBULL_APP_SECRET"
          valueFrom = "${aws_secretsmanager_secret.webull.arn}:WEBULL_APP_SECRET::"
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"

        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.poller.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }
    }
  ])
}
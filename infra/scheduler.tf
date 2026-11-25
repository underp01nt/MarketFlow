/*
    EventBridge scheduling implementation
*/

# create scheduler IAM trust policy
data "aws_iam_policy_document" "scheduler_assume_role" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

# create IAM role referencing the trust policy
resource "aws_iam_role" "scheduler" {
  name               = "marketflow-scheduler-role"
  assume_role_policy = data.aws_iam_policy_document.scheduler_assume_role.json
}

# define permissions for EventBridge Scheduler to launch ECS Fargate task
data "aws_iam_policy_document" "scheduler_run_task" {
  statement {   # allow ECS task execution
    effect = "Allow"
    actions = ["ecs:RunTask"]
    resources = [aws_ecs_task_definition.poller.arn]

    condition {  # focus on the MarketFlow cluster only
      test     = "ArnEquals"
      variable = "ecs:cluster"

      values = [aws_ecs_cluster.main.arn]
    }
  }

  statement {   # baton passing, allow scheduler (caller) to pass IAM roles the ECS needs to run its workload
                # IAM role ARNs will be passed from scheduler to ECS
    effect = "Allow"
    actions = ["iam:PassRole"]

    resources = [
      aws_iam_role.execution.arn,
      aws_iam_role.task.arn
    ]

    condition {
      test     = "StringLike"
      variable = "iam:PassedToService"

      values = ["ecs-tasks.amazonaws.com"]
    }
  }
}

# attach permissions to the scheduler role
resource "aws_iam_role_policy" "scheduler_run_task" {
  name   = "marketflow-scheduler-run-task"
  role   = aws_iam_role.scheduler.id
  policy = data.aws_iam_policy_document.scheduler_run_task.json
}

# create scheduler, assign scheduler role, and allow startup on weekdays at 9:30 AM EST
resource "aws_scheduler_schedule" "marketflow" {
  name                         = "marketflow-market-open"
  schedule_expression          = "cron(30 9 ? * MON-FRI *)"
  schedule_expression_timezone = "America/New_York"
  state                        = "DISABLED"               # automatically trigger on creation?

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_ecs_cluster.main.arn
    role_arn = aws_iam_role.scheduler.arn

    ecs_parameters {
      task_definition_arn = aws_ecs_task_definition.poller.arn
      launch_type        = "FARGATE"
      task_count         = 1

      network_configuration {
        subnets          = aws_subnet.public[*].id
        security_groups  = [aws_security_group.poller.id]
        assign_public_ip = true
      }
    }
  }

  depends_on = [
    aws_iam_role_policy.scheduler_run_task
  ]
}

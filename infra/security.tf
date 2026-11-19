/*   
    definition of IAM access permissions + roles   
    
    ECS execution role: pull ECR image, retrieve Webull secrets, send logs to CloudWatch
    ECS task role: upload market data to S3

*/

/*  POLICY DEFINITIONS  */

# defines (trust) policy for ECS to assume IAM role
data "aws_iam_policy_document" "ecs_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]   # allow ECS to assume IAM
    }
  }
}

# defines S3 object writing (permission) policy to location /candles/*
# whoever receives this policy can upload to S3 at that folder
data "aws_iam_policy_document" "s3_write" {
  statement {
    actions = [
      "s3:PutObject",
      "s3:AbortMultipartUpload"   # cancel incomplete upload
    ]

    resources = ["${aws_s3_bucket.data.arn}/candles/*"]
  }
}

# defines reading (permission) policy for accessing Webull secret
# whoever receives this policy can read Webull credentials from Secrets Manager
data "aws_iam_policy_document" "secrets_read" {
  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.webull.arn]
  }
}


/*  CREATE BASE TASK/EXECUTION ROLES AND ASSIGN POLICIES  */

# creates IAM task role and assigns it to the ecs_assume_role policy
resource "aws_iam_role" "task" {
  name               = "marketflow-ecs-writer-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume_role.json   
  # entities assuming this role are defined by value of assume_role_policy  
}

# creates IAM task execution role and assigns it to the ecs_assume_role policy
resource "aws_iam_role" "execution" {
  name               = "marketflow-ecs-task-execution-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume_role.json
}


/*  CREATES AND ATTACHES POLICIES TO THE APPROPRIATE ROLES  */

# give task role S3 permissions
resource "aws_iam_role_policy" "task_s3" {
  name   = "marketflow-s3-write-policy"
  role   = aws_iam_role.task.name
  policy = data.aws_iam_policy_document.s3_write.json
}

# give execution role for webull read permissions
resource "aws_iam_role_policy" "execution_secrets" {
  name   = "marketflow-secrets-read-policy"
  role   = aws_iam_role.execution.name
  policy = data.aws_iam_policy_document.secrets_read.json
}

# give execution role an existing AWS policy
resource "aws_iam_role_policy_attachment" "execution" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}


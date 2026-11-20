/* 
    three sections to this:
        1. ECR -- stores Docker image
        2. S3  -- stores collected Webull OpenAPI market data
        3. Secrets Manager -- stores secrets
*/


# creates ECR repo
resource "aws_ecr_repository" "poller" {
  name                 = var.ecr_repository_name
  image_tag_mutability = "MUTABLE"   # allow latest tag to be reused if needed

  image_scanning_configuration {
    scan_on_push = true   # vulnerability scanning
  }
}

# creates S3 bucket
resource "aws_s3_bucket" "data" {    # bucket = aws_s3_bucket.data
  bucket        = var.s3_bucket_name
  force_destroy = false
}

# tracks object versions
resource "aws_s3_bucket_versioning" "data" {
  bucket = aws_s3_bucket.data.id

  versioning_configuration {
    status = "Enabled"
  }
}

# enables encryption for objects uploaded in S3
resource "aws_s3_bucket_server_side_encryption_configuration" "data" {
  bucket = aws_s3_bucket.data.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# blocks market data from exiting out to public network
resource "aws_s3_bucket_public_access_block" "data" {
  bucket                  = aws_s3_bucket.data.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# creates a secret in Secrets Manager
resource "aws_secretsmanager_secret" "webull" {    # aws_secretsmanager_secret.webull
  name = var.webull_secret_name
}

# store credentials in the secret as JSON
resource "aws_secretsmanager_secret_version" "webull" {
  secret_id = aws_secretsmanager_secret.webull.id

  secret_string = jsonencode({
    WEBULL_APP_KEY    = var.webull_app_key
    WEBULL_APP_SECRET = var.webull_app_secret
  })
}

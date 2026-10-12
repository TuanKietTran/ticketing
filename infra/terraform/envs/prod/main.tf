terraform {
  required_version = ">= 1.6"
  backend "s3" {
    bucket         = "ticketing-tf-state-prod"
    key            = "prod/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "ticketing-tf-lock"
    encrypt        = true
  }
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}
provider "aws" { region = var.region }
variable "region" {
  type    = string
  default = "us-east-1"
}
variable "image" {
  type    = string
  default = "REPLACE_WITH_ECR_IMAGE"
}
variable "domain" {
  type    = string
  default = "api.example.com"
}
module "network" {
  source = "../../modules/network"
  name   = "ticketing-prod"
  azs    = ["us-east-1a", "us-east-1b", "us-east-1c"]
}
module "data" {
  source            = "../../modules/data"
  name              = "ticketing-prod"
  vpc_id            = module.network.vpc_id
  subnets           = module.network.private_subnets
  security_group_id = module.network.app_security_group_id
  multi_az          = true
}
module "ecs" {
  source            = "../../modules/ecs"
  name              = "ticketing-prod"
  subnets           = module.network.private_subnets
  security_group_id = module.network.app_security_group_id
  image             = var.image
  secret_arn        = module.data.secret_arn
  desired_count     = 4
}
resource "aws_acm_certificate" "api" {
  domain_name       = var.domain
  validation_method = "DNS"
  lifecycle { create_before_destroy = true }
}
module "edge" {
  source            = "../../modules/edge"
  name              = "ticketing-prod"
  vpc_id            = module.network.vpc_id
  public_subnets    = module.network.public_subnets
  security_group_id = module.network.app_security_group_id
  certificate_arn   = aws_acm_certificate.api.arn
}
resource "aws_sns_topic" "alerts" { name = "ticketing-prod-alerts" }
module "alarms" {
  source        = "../../modules/alarms"
  name          = "ticketing-prod"
  sns_topic_arn = aws_sns_topic.alerts.arn
}
resource "aws_iam_role" "github_oidc" {
  name = "ticketing-prod-github-deploy"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Federated = "REPLACE_WITH_GITHUB_OIDC_PROVIDER_ARN" }, Action = "sts:AssumeRoleWithWebIdentity" }]
  })
}

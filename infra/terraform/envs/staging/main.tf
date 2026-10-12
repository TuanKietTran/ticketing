terraform {
  required_version = ">= 1.6"
  backend "s3" {
    bucket         = "ticketing-tf-state-staging"
    key            = "staging/terraform.tfstate"
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
  default = "staging.example.com"
}
module "network" {
  source = "../../modules/network"
  name   = "ticketing-staging"
  azs    = ["us-east-1a", "us-east-1b"]
}
module "data" {
  source            = "../../modules/data"
  name              = "ticketing-staging"
  vpc_id            = module.network.vpc_id
  subnets           = module.network.private_subnets
  security_group_id = module.network.app_security_group_id
  multi_az          = false
}
module "ecs" {
  source            = "../../modules/ecs"
  name              = "ticketing-staging"
  subnets           = module.network.private_subnets
  security_group_id = module.network.app_security_group_id
  image             = var.image
  secret_arn        = module.data.secret_arn
  desired_count     = 2
}
resource "aws_acm_certificate" "api" {
  domain_name       = var.domain
  validation_method = "DNS"
  lifecycle { create_before_destroy = true }
}
module "edge" {
  source            = "../../modules/edge"
  name              = "ticketing-staging"
  vpc_id            = module.network.vpc_id
  public_subnets    = module.network.public_subnets
  security_group_id = module.network.app_security_group_id
  certificate_arn   = aws_acm_certificate.api.arn
}
resource "aws_sns_topic" "alerts" { name = "ticketing-staging-alerts" }
module "alarms" {
  source        = "../../modules/alarms"
  name          = "ticketing-staging"
  sns_topic_arn = aws_sns_topic.alerts.arn
}

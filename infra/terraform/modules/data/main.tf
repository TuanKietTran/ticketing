variable "name" { type = string }
variable "vpc_id" { type = string }
variable "subnets" { type = list(string) }
variable "security_group_id" { type = string }
variable "multi_az" { type = bool }
resource "aws_db_subnet_group" "postgres" {
  name       = "${var.name}-db"
  subnet_ids = var.subnets
}
resource "aws_db_instance" "postgres" {
  identifier                  = var.name
  engine                      = "postgres"
  engine_version              = "16"
  instance_class              = "db.t4g.medium"
  allocated_storage           = 100
  storage_encrypted           = true
  multi_az                    = var.multi_az
  db_subnet_group_name        = aws_db_subnet_group.postgres.name
  vpc_security_group_ids      = [var.security_group_id]
  username                    = "ticketing"
  manage_master_user_password = true
  skip_final_snapshot         = false
  deletion_protection         = var.multi_az
}
resource "aws_elasticache_subnet_group" "redis" {
  name       = "${var.name}-redis"
  subnet_ids = var.subnets
}
resource "aws_elasticache_replication_group" "redis" {
  replication_group_id       = var.name
  description                = "ticketing redis"
  engine                     = "redis"
  node_type                  = "cache.t4g.small"
  num_cache_clusters         = var.multi_az ? 2 : 1
  automatic_failover_enabled = var.multi_az
  multi_az_enabled           = var.multi_az
  subnet_group_name          = aws_elasticache_subnet_group.redis.name
  security_group_ids         = [var.security_group_id]
}
resource "aws_secretsmanager_secret" "app" { name = "${var.name}/application" }
output "database_endpoint" { value = aws_db_instance.postgres.address }
output "redis_endpoint" { value = aws_elasticache_replication_group.redis.primary_endpoint_address }
output "secret_arn" { value = aws_secretsmanager_secret.app.arn }

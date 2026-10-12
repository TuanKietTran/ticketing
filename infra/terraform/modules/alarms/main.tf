variable "name" { type = string }
variable "sns_topic_arn" { type = string }
resource "aws_cloudwatch_metric_alarm" "api_5xx" {
  alarm_name          = "${var.name}-5xx"
  namespace           = "AWS/ApplicationELB"
  metric_name         = "HTTPCode_ELB_5XX_Count"
  statistic           = "Sum"
  period              = 60
  evaluation_periods  = 2
  threshold           = 5
  comparison_operator = "GreaterThanThreshold"
  alarm_actions       = [var.sns_topic_arn]
}
resource "aws_cloudwatch_metric_alarm" "latency" {
  alarm_name          = "${var.name}-latency"
  namespace           = "AWS/ApplicationELB"
  metric_name         = "TargetResponseTime"
  extended_statistic  = "p99"
  period              = 60
  evaluation_periods  = 3
  threshold           = 0.8
  comparison_operator = "GreaterThanThreshold"
  alarm_actions       = [var.sns_topic_arn]
}
resource "aws_cloudwatch_metric_alarm" "dlq_depth" {
  alarm_name          = "${var.name}-dlq-depth"
  namespace           = "Ticketing"
  metric_name         = "dead_letter_depth"
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 2
  threshold           = 1
  comparison_operator = "GreaterThanThreshold"
  alarm_actions       = [var.sns_topic_arn]
}
resource "aws_cloudwatch_metric_alarm" "dlq_age" {
  alarm_name          = "${var.name}-dlq-age"
  namespace           = "Ticketing"
  metric_name         = "dead_letter_oldest_age_seconds"
  statistic           = "Maximum"
  period              = 300
  evaluation_periods  = 2
  threshold           = 900
  comparison_operator = "GreaterThanThreshold"
  alarm_actions       = [var.sns_topic_arn]
}

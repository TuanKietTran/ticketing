# AWS deployment (Terraform, static-only in this session)

The Terraform under `terraform/` defines staging and production VPCs, ALB/ACM/WAF, ECS Fargate services (`api`, `worker`, `outbox-dispatcher`), ECR, RDS PostgreSQL 16 (Multi-AZ in prod), ElastiCache Redis, Secrets Manager, IAM, autoscaling, CloudWatch alarms, and optional GitHub OIDC.

## First deploy (owner executes in a later session)

1. Bootstrap state in `terraform/bootstrap` with the owner’s AWS credentials.
2. Copy the resulting bucket/table settings into the selected environment backend.
3. Publish the image to ECR and set `-var=image=...`.
4. Create/validate ACM DNS records.
5. Run the ECS one-off task `${name}-migrations` with `alembic upgrade head`.
6. Apply the environment only after reviewing a locally generated plan in the owner’s controlled session.

This coding session did **not** run `terraform apply`, `terraform plan`, create AWS resources, access AWS credentials, or initialize a remote backend. Only `fmt`, `init -backend=false`, and `validate` are permitted here.

## Rollback and destroy

Rollback by deploying the previous immutable ECR image and rerunning health checks. Do not destroy production casually: disable traffic, snapshot RDS, export secrets/configuration, and follow the owner’s change approval. Staging destroy must preserve state backups.

## Cost estimate (ESTIMATE, us-east-1)

| Component | Staging/month | Prod/month |
|---|---:|---:|
| ECS/Fargate | $40–120 | $180–500 |
| RDS PostgreSQL 16 | $50–150 | $250–700 |
| ElastiCache Redis | $20–80 | $100–300 |
| ALB/WAF/CloudWatch/ECR | $30–100 | $80–250 |
| **Total estimate** | **$140–450** | **$610–1,750** |

Actual cost depends on traffic, storage, NAT, data transfer, reserved pricing, and region.

## Unverified

Terraform has not been applied or planned against AWS. IAM trust/resource policies, route/NAT completeness, ACM DNS validation, ECS secret wiring, ALB target registration, WAF tuning, alarm dimensions, RDS/Redis connectivity, and the cost estimate are unverified. Run static validation locally before any owner-controlled deployment.

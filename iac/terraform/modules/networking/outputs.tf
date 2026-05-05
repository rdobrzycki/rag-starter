output "vpc_id" { value = local.vpc_id }
output "public_subnet_ids" { value = local.public_subnet_ids }
output "private_subnet_ids" { value = local.private_subnet_ids }
output "alb_security_group_id" { value = aws_security_group.alb.id }
output "ecs_tasks_security_group_id" { value = aws_security_group.ecs_tasks.id }
output "lambda_security_group_id" { value = aws_security_group.lambda.id }

# Secrets và cấu hình chạy

Frontend dùng cùng origin và không cần biến `VITE_*`. Không đưa `DATABASE_URL`, provider API keys, Supabase service-role key hay GHCR token vào frontend, Docker image, GitHub Actions output, release asset hoặc repository. `SUPABASE_PUBLISHABLE_KEY` được dùng ở backend để gọi Supabase Auth; nó không phải service-role credential.

Backend đọc tên biến trong `backend/app/core/config.py` và `backend/app/ai/embedding_config.py`. Mẫu nằm ở `deploy/runtime.env.example`. Production cần `APP_ENV=production`, `DATABASE_URL` với runtime DML role và TLS, `DATABASE_POOL_MODE=session`, `SUPABASE_URL` HTTPS, `SUPABASE_PUBLISHABLE_KEY`, `FRONTEND_ORIGIN=https://moodprint.duckdns.org`, và Secure cookies. `AI_ENABLED`, `STT_ENABLED`, semantic memory, accounting, and chat history stay disabled unless their credentials, schema, consent, provider limits, and smoke tests have been reviewed. `DATABASE_MIGRATION_URL` is never part of the runtime environment.

## Parameter Store

The runtime file is stored in the existing Standard SecureString `/moodprint/staging/runtime` in `ap-southeast-2`. Standard parameters are limited to 4 KB. The EC2 role needs `ssm:GetParameter` only for this exact parameter ARN. When encrypted with the AWS managed `alias/aws/ssm` key, its default key policy allows account IAM principals to decrypt; do not add a placeholder customer-key grant. If a customer managed key is selected, review its exact `kms:Decrypt` permission separately.

`deploy.sh` retrieves the value only for a verified deployment, writes it to a unique file under `/run/moodprint` with mode `0600`, and passes the file path to Compose. It never prints the parameter value. The active and previous deployments keep their own root-owned runtime files for rollback. Root and Docker administrators on EC2 can inspect container environment metadata, so restrict OS and Docker access. Do not send the env file or container inspection output to logs, tickets, screenshots, or backups.

## GHCR access

The new packages start private. Public GHCR packages can be pulled anonymously. If packages remain private, store a separate token with only `read:packages` in a SecureString and set its exact parameter name in root-owned `/opt/moodprint/deployment.conf`. Add access only to that token parameter on the EC2 role. The poller keeps Docker credentials in a temporary root-only `DOCKER_CONFIG`, and removes them after verification. Never place the token in GitHub Actions or images.

Public package visibility is difficult to reverse and exposes image layers to anonymous pulls. Review the published images and secret checks before changing visibility. See the [GitHub Packages billing page](https://docs.github.com/en/billing/concepts/product-billing/github-packages) and [container registry permissions](https://docs.github.com/en/packages/learn-github-packages/about-permissions-for-github-packages).

## Rotation and recovery

Update SecureString values through the secret-entry channel, never chat or workflow inputs. Routine deployments retrieve the current runtime values when a new verified main release is installed. To apply a rotated runtime file without a new application SHA, an operator can use the reviewed SSM recovery document with the currently approved image digests and full release SHA, then verify readiness. This recovery path is separate from normal polling. Do not run database migrations from deployment.

Backend logs contain request IDs and error classes, not request bodies, SQL parameters, provider tokens, or transcripts. Caddy does not enable access logs. Check log redaction with synthetic tokens before any live provider smoke.

# CI và phát hành có kiểm soát

## CI

`verify.yml` chạy backend, PostgreSQL disposable, frontend, end-to-end, workflow syntax, image/package checks và poller unit tests. Pull request CI chỉ cần quyền đọc mã nguồn; không dùng AWS credentials, không đẩy image và không triển khai.

## Phát hành tự động

`deploy-staging.yml` chạy sau khi `Verify local application` kết thúc thành công cho một push lên `main`. Job xác minh cùng repository, event `push`, branch `main`, workflow ID chính xác và SHA đúng với commit hiện tại trên `main`. Nếu `main` đã đổi thì release cũ bị bỏ qua.

Build job chỉ đọc source ở SHA đã xác minh. Job build hai image `linux/amd64`, kiểm tra biến runtime nhạy cảm trong image config, file `.env` và source maps, rồi chuyển image archive qua artifact ngắn hạn. Job publish kiểm tra lại SHA, CI run, image ID và revision label; sau đó đẩy image vào:

- `ghcr.io/mhiu05/moodprint-api`
- `ghcr.io/mhiu05/moodprint-web`

Release manifest ghi SHA, CI/publish run ID, tên image và digest OCI. Manifest và từng digest có GitHub attestations. Workflow tạo prerelease `staging-<SHA>` chỉ khi `main` vẫn ở cùng SHA. EC2 poller kiểm tra main, manifest, CI, publish run và attestations trước khi dùng digest bất biến.

Workflow không dùng AWS OIDC, IAM role, ECR, AWS access key hoặc API AWS. `id-token: write` trong job publish chỉ phục vụ GitHub artifact attestations; nó không cấp quyền AWS. Không có self-hosted GitHub runner. Routine deploy do EC2 pull release; GitHub Actions không gọi SSM.

## EC2 puller

Systemd timer kiểm tra mỗi năm phút. Poller xác minh repository/workflow/source identity, không chạy script tải từ repository khi polling, lấy SecureString chỉ khi có release mới, rồi gọi root-owned `deploy.sh`. Lock file ngăn poll trùng. Deploy dùng digest refs, đợi container health và HTTPS readiness, lưu image pair trước đó, và cố khôi phục pair cũ khi health check thất bại. Pipeline không chạy migration database.

## GHCR access

GHCR packages bắt đầu private. Để giữ private, lưu token chỉ có `read:packages` trong một SecureString riêng, cấu hình tên parameter trong `/opt/moodprint/deployment.conf`, rồi cấp quyền đọc chỉ parameter đó cho EC2 role. Không lưu token trong GitHub Actions, repository hoặc image.

Public packages cho phép pull ẩn danh, nhưng đổi package thành public là lựa chọn có hậu quả lâu dài. Review image contents và secret checks trước khi thay visibility. Xem [GitHub Packages billing and permissions](https://docs.github.com/en/billing/concepts/product-billing/github-packages) và [container registry permissions](https://docs.github.com/en/packages/learn-github-packages/about-permissions-for-github-packages).

`workflow_dispatch` là owner-only fallback để chạy lại publication cho SHA hiện tại sau khi nhập SHA và cụm xác nhận. Đây không phải routine deployment: EC2 vẫn tự phát hiện và xác minh release. Configure branch protection trên `main` nếu push cần review. Hạ tầng ECR cũ được giữ nguyên nhưng pipeline mới không dùng nó.

Chi tiết cài đặt và vận hành: [staging setup](staging-setup.md), [AWS release poller](../../deploy/aws/README.md), [release checklist](release-checklist.md).

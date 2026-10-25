# Rollback và xử lý sự cố

Systemd timer `moodprint-release-poll.timer` kiểm tra release hiện hành. Nếu CI, SHA, manifest, workflow run hoặc image attestation không hợp lệ, poller không gọi deploy script và containers hiện có tiếp tục chạy. Nếu `main` đổi trong lúc xác minh, release cũ bị bỏ qua.

`deploy.sh` lưu active/previous digest pair cùng runtime file, pull image mới, khởi động Compose, rồi đợi cả hai container healthy và `https://APP_DOMAIN/api/v1/health/ready`. Nếu health check thất bại, script đưa previous pair trở lại và kiểm tra lại readiness. Lần deploy đầu không có pair cũ; failed containers sẽ dừng. Poller/service ghi lỗi để operator xử lý; chỉ xác nhận rollback thành công sau khi readiness của pair cũ đã được kiểm tra.

## Chẩn đoán an toàn

```bash
sudo systemctl status moodprint-release-poll.timer
sudo systemctl start moodprint-release-poll.service
sudo journalctl -u moodprint-release-poll.service --since today --no-pager
sudo docker compose --project-directory /opt/moodprint -f /opt/moodprint/compose.staging.yml ps
```

Kiểm tra release SHA, main/CI/run status, GHCR pull, container health, DNS/TLS, Caddy và readiness theo thứ tự. Không in `docker inspect` environment, không `cat` file trong `/run/moodprint`, và không gửi logs có thể chứa token. Không dùng `docker compose down -v`; thao tác đó xóa Caddy TLS storage.

## Emergency recovery

SSM document `MoodPrint-Staging-Deploy` chỉ là operator recovery route. Trước khi dùng, xác minh manifest/attestations và chọn GHCR image refs theo digest cùng full commit SHA; không nhập tag mutable. Routine deployment không gọi SSM Run Command. Giữ repository ECR cũ nguyên trạng; không xóa resources trong quá trình rollback.

Rollback ứng dụng chỉ an toàn khi image cũ tương thích với schema đang có. Deployment không chạy migrations. Alembic downgrade phá dữ liệu từ revisions 0006–0010 bị chặn. Restore database là thao tác riêng, cần bản sao và review: trước khi mở traffic hãy reconcile account/memory deletion tombstones, revocations, consent và deletion queue để dữ liệu đã xóa không tái xuất hiện. Raw AI context không được đưa vào backup. Restart làm mất context tạm trong RAM và ngắt SSE; không tự replay model call.

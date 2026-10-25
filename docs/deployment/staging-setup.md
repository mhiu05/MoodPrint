# Cài poller staging trên EC2 hiện có

Tài liệu này dùng hạ tầng staging đã tồn tại; không tạo EC2, Elastic IP, ECR repository, NAT, load balancer hay DNS service mới. Giữ AWS Free Plan và các spending limits hiện có. Application chưa được xác minh live cho đến khi một release проходит health checks.

## Trước khi cài

1. Trong AWS Console, xác minh đúng account/Region, EC2 instance đang chạy và SSM Managed node Online. Xác minh Security Group chỉ mở HTTP/HTTPS cần thiết; không mở SSH hoặc API port. Giữ role `MoodPrint-Staging-EC2-Role` với `AmazonSSMManagedInstanceCore`.
2. Xác minh `/moodprint/staging/runtime` là Standard SecureString. Không in hoặc chụp plaintext. Kiểm tra chỉ tên biến và các giá trị boolean cần thiết. Parameter Store Standard có giới hạn 4 KB.
3. Review `deploy/aws/instance-policy.json`, thay placeholder Region/account bằng giá trị thật, rồi attach cho role EC2. Policy chỉ cho phép `ssm:GetParameter` trên parameter runtime này. Nếu parameter dùng AWS managed key `alias/aws/ssm`, không thêm placeholder CMK permission; nếu dùng customer managed key thì review key policy riêng.
4. Xác minh DNS A record của `moodprint.duckdns.org` trỏ tới Elastic IP hiện có. Không đổi IP hoặc mua domain mới.
5. GHCR images bắt đầu private. Chọn cách pull sau khi first images đãผ่าน secret checks: public packages cho anonymous pulls, hoặc token `read:packages` trong SecureString riêng. Không thể hoàn tác việc chuyển package sang public; hãy xem nội dung image trước khi đổi visibility. Nếu giữ private, đặt `GHCR_TOKEN_PARAMETER_NAME` và `GHCR_USERNAME` trong config root-owned, rồi cấp cho role quyền đọc đúng parameter token.

## Install

Từ repository tại commit `main` đã được review, chạy qua Session Manager:

```bash
sudo bash deploy/aws/install-release-poller.sh
```

Installer memasang `poll_release.py`, `deploy.sh`, Compose/Caddy files, systemd service/timer, dan GitHub CLI minimal 2.102.0 dari repository resmi GitHub jika versi yang tersedia terlalu lama. Itu tidak membuat resource AWS. Script dipasang sebagai root; jangan beri akses tulis ke user aplikasi.

Review `/opt/moodprint/deployment.conf` dengan mode `0600`. Non-secret settings mencakup Region, repository `mhiu05/MoodPrint`, GHCR image names, dan `APP_DOMAIN=moodprint.duckdns.org`. Jangan meletakkan backend secrets atau package token langsung di file.

Verifikasi timer dan log tanpa membaca env file:

```bash
sudo systemctl status moodprint-release-poll.timer
sudo systemctl start moodprint-release-poll.service
sudo journalctl -u moodprint-release-poll.service --since today --no-pager
```

Untuk emergency recovery saja, review/update SSM document dari `deploy/aws/ssm-document.json`; routine deployment tidak memanggil SSM Run Command. Pertahankan dua repository ECR lama dan lifecycle policies; release workflow baru menggunakan GHCR.

## Release dan pemeriksaan

Setelah perubahan berada di `main`, CI harus sukses pada SHA yang sama. Release workflow membangun, memindai, dan menerbitkan image digest serta attestations. EC2 poller mengambil release untuk SHA `main` terbaru dalam sekitar 2–5 menit, memverifikasi provenance, lalu menggunakan Compose. CI gagal berarti tidak ada release baru untuk dipasang.

Konfirmasi kedua container healthy dan `https://moodprint.duckdns.org/api/v1/health/ready` berhasil. Caddy mengelola HTTPS dan redirect HTTP ke HTTPS; pastikan Supabase Auth Site URL dan callback allow-list sesuai sebelum login smoke tests. App deployment tidak menjalankan migration. Jika health check release baru gagal, `deploy.sh` mencoba memulihkan image pair sebelumnya; verifikasi readiness setelahnya sebelum menyatakan rollback berhasil.

AI, memory, semantic retrieval, STT, Auth, messaging, dan pengalaman mobile memerlukan smoke tests terpisah dengan synthetic accounts. Jangan menganggapnya lulus hanya karena container atau readiness sehat.

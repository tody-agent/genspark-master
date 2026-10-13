# 🚀 Hướng Dẫn Cài Đặt & Chia Sẻ Genspark Plugin Sang Máy Khác

## 📦 Cách 1: Chia sẻ qua file nén (.tar.gz hoặc .zip)

### Bước 1: Chuyển file sang máy mới
Copy file `genspark-plugin-v0.5.0.tar.gz` (hoặc `.zip`) sang máy mới (qua AirDrop, USB, Google Drive, hoặc SCP):
```bash
# Ví dụ gửi qua SCP:
scp genspark-plugin-v0.5.0.tar.gz user@target-machine:~/
```

### Bước 2: Giải nén trên máy mới
```bash
tar -xzf genspark-plugin-v0.5.0.tar.gz
cd genspark-plugin-v0.5.0
```

### Bước 3: Chạy cài đặt tự động 1 lệnh
```bash
./install.sh
```
*Script sẽ tự động:*
- Khởi tạo môi trường ảo Python 3.10+
- Cài đặt toàn bộ dependencies & Playwright Chromium
- Tạo lệnh toàn cục `genspark`, `gsk`, `genspark-mcp` trong `~/.local/bin/`
- Đăng ký plugin vào `~/.gemini/config/plugins/genspark` (Antigravity), Claude Code, và Codex.

### Bước 4: Đăng nhập tài khoản Genspark (Chỉ 1 lần duy nhất)
```bash
genspark auth login
```
Trình duyệt sẽ mở ra để bạn đăng nhập Google/Email vào Genspark. Sau khi đăng nhập thành công, phiên đăng nhập sẽ được lưu tại `~/.genspark/storage_state.json`.

---

## 🌐 Cách 2: Chia sẻ qua Git

### Bước 1: Clone trên máy mới
```bash
git clone <url-repository> genspark
cd genspark
```

### Bước 2: Cài đặt
```bash
./install.sh --link
```
(Dùng `--link` để tự động tạo symlink vào `~/.gemini/config/plugins/genspark`, giúp cập nhật code `git pull` là tự động ăn ngay).

### Bước 3: Đăng nhập
```bash
genspark auth login
```

---

## 🛠️ Kiểm tra sau khi cài đặt

Kiểm tra sức khỏe hệ thống:
```bash
genspark doctor
```

Thử nghiệm chat:
```bash
genspark chat ask "Xin chào, bạn là AI nào?" --model claude-opus-4.7
```

Thử nghiệm tạo ảnh:
```bash
genspark image create "A futuristic cyberpunk city in neon lights" --model flux-2-pro
```

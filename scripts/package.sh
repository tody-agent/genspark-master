#!/usr/bin/env bash
# Packager for Genspark Master AI Suite Plugin
# Creates clean, standalone distributable bundles for sharing across machines
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
DIST_DIR="$PLUGIN_ROOT/dist"

cd "$PLUGIN_ROOT"

VERSION=$(grep -m 1 'version' pyproject.toml | tr -d ' "version=,')
if [ -z "$VERSION" ]; then
    VERSION="0.5.0"
fi

PKG_NAME="genspark-plugin-v${VERSION}"
STAGE_DIR="/tmp/${PKG_NAME}"

echo "=========================================================="
echo "📦 Packaging Genspark Plugin v${VERSION} for Distribution"
echo "=========================================================="

mkdir -p "$DIST_DIR"
rm -rf "$STAGE_DIR"
mkdir -p "$STAGE_DIR"

echo "1. Staging clean plugin files..."
rsync -a --exclude='.git' \
         --exclude='.venv' \
         --exclude='__pycache__' \
         --exclude='*.pyc' \
         --exclude='.pytest_cache' \
         --exclude='.DS_Store' \
         --exclude='dist' \
         --exclude='*.tmp' \
         --exclude='*.egg-info' \
         --exclude='.genspark' \
         "$PLUGIN_ROOT/" "$STAGE_DIR/"

# Ensure all scripts in stage are executable
chmod +x "$STAGE_DIR/install.sh"
chmod +x "$STAGE_DIR/bin/"* || true
chmod +x "$STAGE_DIR/scripts/"* || true

echo "2. Building distribution archives..."
cd /tmp
# Create .tar.gz
tar -czf "$DIST_DIR/${PKG_NAME}.tar.gz" "$PKG_NAME"
echo "  ✓ Created $DIST_DIR/${PKG_NAME}.tar.gz"

# Create .zip
zip -rq "$DIST_DIR/${PKG_NAME}.zip" "$PKG_NAME"
echo "  ✓ Created $DIST_DIR/${PKG_NAME}.zip"

# Create Codex .plugin bundle if build_plugin.py exists
if [ -f "$PLUGIN_ROOT/scripts/build_plugin.py" ]; then
    python3 "$PLUGIN_ROOT/scripts/build_plugin.py" --output "$DIST_DIR/genspark-master-${VERSION}.plugin" >/dev/null 2>&1 || true
    echo "  ✓ Created $DIST_DIR/genspark-master-${VERSION}.plugin"
fi

# Clean stage
rm -rf "$STAGE_DIR"

# 3. Create SHA256 Checksums
cd "$DIST_DIR"
if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "${PKG_NAME}.tar.gz" "${PKG_NAME}.zip" > "${PKG_NAME}.sha256"
elif command -v sha256sum >/dev/null 2>&1; then
    sha256sum "${PKG_NAME}.tar.gz" "${PKG_NAME}.zip" > "${PKG_NAME}.sha256"
fi

echo ""
echo "4. Generating Transfer & Installation Guide..."
cat > "$DIST_DIR/HOW_TO_TRANSFER.md" << 'EOF'
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
EOF

echo "✓ Created $DIST_DIR/HOW_TO_TRANSFER.md"

echo ""
echo "=========================================================="
echo "🎉 Package Completed Successfully!"
echo "Files ready in dist/:"
ls -lh "$DIST_DIR/${PKG_NAME}"* "$DIST_DIR/HOW_TO_TRANSFER.md"
echo "=========================================================="

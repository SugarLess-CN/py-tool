# Archive Processor - 自动化压缩包处理工具

一个用于自动处理压缩文件、图片优化和内容发布的Python工具。

## 📋 功能特性

- 🔓 **智能解压支持**: 支持 ZIP、RAR、7Z 格式，多密码尝试
- 🧹 **智能文件清理**: 根据配置自动删除不需要的文件
- 🖼️ **图片优化**: 自动压缩图片，转换为 WebP 格式
- 📦 **多种压缩格式**: 支持 7z、ZIP、TAR、GZIP、BZIP2、XZ
- ☁️ **自动上传**: 多线程文件上传到指定图床
- 📝 **内容发布**: 自动创建并提交文章到内容平台
- 🎨 **彩色日志**: 支持不同级别的彩色日志输出
- ⚡ **多线程处理**: 支持并行解压和上传操作

## 🚀 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置文件

创建 `config.toml` 配置文件：

```toml
[source]
directory = "./archives"

[delete]
prefix = ["ewm_"]
suffix = ["html"]
extra = ["index", "thumb"]

[file_name]
prefix = "sugarless"

[unpack]
password = ["cosfan.cc","fantwo", "fantwo2"]

[compress_file]
format = "7z"
compression_level = 8
password = "sugarless"
method = "lzma2"

[compress_img]
format = "webp"
quality = 80
longWidth = 1280

[url]
upload = "https://picapi.picart.cc/api/v1/upload/file"
create = "https://picapi.picart.cc/api/v1/article"

[auth]
token = "your-auth-token-here"
did = "uuid-1"
d_name = "DeviceName"
d_type = "android"

[logger]
level = "info"
file_name = "info.log"
name = "sugarless"

[worker]
upload = 4
unpack = 4
```

### 运行程序

```bash
python main.py
```

## 📁 项目结构

```
.
├── main.py              # 主程序入口
├── config.toml          # 配置文件
├── ArchiveProcessor.py  # 压缩包处理核心类
├── PicartHTTPClient.py  # HTTP客户端类
├── FanTwoLogger.py      # 日志记录器类
├── archives/            # 源压缩文件目录
├── output/              # 处理后的输出目录
├── temp/                # 临时工作目录
└── info.log             # 日志文件
```

## ⚙️ 配置说明

### 源文件配置
- `directory`: 源压缩文件存放目录

### 文件清理配置
- `prefix`: 按前缀删除文件
- `suffix`: 按后缀删除文件  
- `extra`: 精确匹配删除文件

### 解压配置
- `password`: 解压密码列表，按顺序尝试

### 压缩配置
支持多种格式和压缩级别：
- **7z**: 级别 0-9，支持 lzma2、lzma、bzip2 等方法
- **ZIP**: 级别 0-3，对应不同压缩算法
- **TAR**: 无压缩归档
- **GZIP/BZIP2/XZ**: 单文件压缩

### 图片压缩
- `format`: 输出格式 (webp)
- `quality`: 压缩质量 (1-100)
- `longWidth`: 最大宽度限制

### API 配置
- `upload`: 文件上传API地址
- `create`: 内容创建API地址

### 认证配置
- `token`: 认证令牌
- `did`: 设备ID
- `d_name`: 设备名称
- `d_type`: 设备类型

## 🎯 使用流程

1. **准备文件**: 将需要处理的压缩包放入 `archives/` 目录
2. **配置参数**: 修改 `config.toml` 中的相关配置
3. **运行程序**: 执行主程序开始处理
4. **查看结果**: 处理后的文件在 `output/` 目录，日志在 `info.log`

## 🔧 高级功能

### 多线程处理
```toml
[worker]
upload = 4    # 上传线程数
unpack = 4    # 解压线程数
```

### 自定义文件命名
```toml
[file_name]
prefix = "custom_prefix"  # 生成文件名为 custom_prefix0001.webp 等
```

### 支持的压缩格式
- 解压: `.zip`, `.rar`, `.7z`
- 压缩: `7z`, `zip`, `tar`, `gzip`, `bz2`, `xz`

## 📊 日志级别

支持以下日志级别：
- `DEBUG` - 调试信息
- `INFO` - 普通信息  
- `SUCCESS` - 成功信息
- `WARNING` - 警告信息
- `ERROR` - 错误信息
- `CRITICAL` - 严重错误

## ❓ 常见问题

### Q: 解压失败怎么办？
A: 检查密码配置，确保在 `[unpack].password` 中提供了正确的密码

### Q: 上传失败怎么办？
A: 检查网络连接和API配置，确认认证信息正确

### Q: 如何处理其他格式的压缩文件？
A: 目前支持 ZIP、RAR、7Z 格式，如需其他格式请提交需求

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📞 支持

如有问题请查看日志文件 `info.log`
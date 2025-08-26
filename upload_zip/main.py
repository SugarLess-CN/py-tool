import bz2
import gzip
import lzma
import mimetypes
import queue
import re
import shutil
import threading
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from queue import Queue
from typing import List, Dict, Any

import py7zr
import rarfile
import toml
from PIL import Image

from FanTwoLogger import FanTwoLogger
from HttpClient import PicartHTTPClient


# 添加项目根目录到 Python 路径
# current_dir = os.path.dirname(os.path.abspath(__file__))
# project_root = os.path.dirname(current_dir)  # 获取 upload_zip 的上级目录
# sys.path.insert(0, project_root)


def _extract_zip(archive_path: Path, extract_dir: Path, password: str) -> bool:
    """解压 ZIP 文件"""
    with zipfile.ZipFile(archive_path, 'r') as zip_ref:
        zip_ref.extractall(extract_dir, pwd=password.encode())
    return True


def _extract_rar(archive_path: Path, extract_dir: Path, password: str) -> bool:
    """解压 RAR 文件"""
    with rarfile.RarFile(archive_path, 'r') as rar_ref:
        rar_ref.extractall(extract_dir, pwd=password)
    return True


def _extract_7z(archive_path: Path, extract_dir: Path, password: str) -> bool:
    """解压 7Z 文件"""
    with py7zr.SevenZipFile(archive_path, 'r', password=password) as zip_ref:
        zip_ref.extractall(extract_dir)
    return True


class ArchiveProcessor:
    def __init__(self, config_path: str):
        self.config = self.load_config(config_path)
        log_name = self.config['logger']['name']
        file_name = self.config['logger']['file_name']
        self.logger = FanTwoLogger(log_name, file_name)  # 新增Logger

        self.http_client = PicartHTTPClient(self.config, self.logger)  # 传入logger
        self.task_queue = Queue()
        self.lock = threading.Lock()

    @staticmethod
    def load_config(config_path: str) -> Dict[str, Any]:
        """加载配置文件"""
        with open(config_path, 'r', encoding='utf-8') as f:
            return toml.load(f)

    def scan_archives(self):
        """扫描指定目录下的所有压缩文件"""
        source_dir = self.config.get('source', {}).get('directory', './archives')
        archive_extensions = ['.zip', '.rar', '.7z']

        for _file_path in Path(source_dir).iterdir():
            if _file_path.suffix.lower() in archive_extensions and _file_path.is_file():
                self.task_queue.put(_file_path)
                self.logger.info(f"发现压缩文件: {_file_path.name}")

    @staticmethod
    def format_folder_name(name: str) -> str:
        """格式化文件夹名称，删除包含P、-和MB的[]内容，并移除所有[]符号"""
        # 先删除包含尺寸信息的 []
        pattern = r'\[[^\]]*P[^\]]*-[^\]]*MB[^\]]*\]'
        name = re.sub(pattern, '', name)

        # 再移除所有剩余的 [] 符号（但不删除其中的内容）
        name = re.sub(r'[\[\]]', '', name)

        # 清理空格和格式
        name = name.strip().strip('-').strip()
        name = re.sub(r'\s+', ' ', name)

        return name

    def extract_archive(self, archive_path: Path, extract_dir: Path) -> bool:
        """解压压缩文件"""
        # 确保解压目录存在
        extract_dir.mkdir(parents=True, exist_ok=True)

        # 获取密码列表，默认包含 'fantwo'
        passwords = self.config['unpack'].get('password', ['fantwo'])

        # 支持的压缩格式映射
        archive_handlers = {
            '.zip': _extract_zip,
            '.rar': _extract_rar,
            '.7z': _extract_7z
        }

        file_ext = archive_path.suffix.lower()

        # 检查是否支持该格式
        if file_ext not in archive_handlers:
            self.logger.error(f"不支持的压缩格式: {file_ext}, 文件: {archive_path.name}")
            return False

        extract_handler = archive_handlers[file_ext]

        # 尝试所有密码
        for password in passwords:
            try:
                if extract_handler(archive_path, extract_dir, password):
                    self.logger.success(
                        f"解压成功 (密码: {password}), 格式: {file_ext}, 文件: {archive_path.name}"
                    )
                    return True
            except Exception as e:
                self.logger.warning(
                    f"解压失败 (密码: {password}): {e}, 文件: {archive_path.name}"
                )
                continue

        self.logger.error(f"所有密码尝试失败，无法解压文件: {archive_path.name}")
        return False

    def clean_files(self, folder_path: Path):
        """清理不需要的文件"""
        delete_config = self.config['delete']

        for file_path in folder_path.rglob('*'):
            if file_path.is_file():
                filename = file_path.stem
                # suffix = file_path.suffix

                # 前缀匹配删除
                for prefix in delete_config.get('prefix', []):
                    if re.match(prefix, file_path.name):
                        file_path.unlink()
                        break

                # 后缀匹配删除
                for suffix_pattern in delete_config.get('suffix', []):
                    if re.search(suffix_pattern + '$', file_path.name):
                        file_path.unlink()
                        break

                # 全字匹配删除
                for exact_name in delete_config.get('extra', []):
                    if re.fullmatch(exact_name, filename):
                        file_path.unlink()
                        break

    def rename_files(self, folder_path: Path):
        """重命名文件"""
        prefix = self.config['file_name'].get('prefix', 'fantwo')
        files = sorted([f for f in folder_path.iterdir() if f.is_file()],
                       key=lambda x: x.name)

        for idx, file_path in enumerate(files, 1):
            new_name = f"{prefix}{idx:04d}{file_path.suffix}"
            new_path = folder_path / new_name
            file_path.rename(new_path)

    def compress_images(self, folder_path: Path):
        """压缩图片"""
        img_config = self.config['compress_img']
        output_format = img_config.get('format', 'webp')
        quality = img_config.get('quality', 80)
        max_width = img_config.get('longWidth', 1280)

        image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.gif']

        for file_path in folder_path.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in image_extensions:
                try:
                    with Image.open(file_path) as img:
                        # 调整尺寸
                        if max_width > 0:
                            width, height = img.size
                            if width > height and width > max_width:
                                new_height = int(height * (max_width / width))
                                img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
                            elif height > max_width:
                                new_width = int(width * (max_width / height))
                                img = img.resize((new_width, max_width), Image.Resampling.LANCZOS)

                        # 转换格式并保存
                        output_path = file_path.with_suffix(f'.{output_format}')
                        img.save(output_path, format=output_format.upper(), quality=quality)

                        # 删除原文件
                        file_path.unlink()

                except Exception as e:
                    self.logger.error(f"图片压缩失败 {file_path.name}: {e}")

    # def create_archive(self, folder_path: Path, output_path: Path):
    #     """创建压缩包"""
    #     compress_config = self.config['compress_file']
    #     format_type = compress_config.get('format', '7z')
    #     password = compress_config.get('password', 'fantwo')
    #     quality = compress_config.get('quality', 8)
    #
    #     if format_type.lower() == '7z':
    #         with py7zr.SevenZipFile(output_path, 'w', password=password) as archive:
    #             for file_path in folder_path.iterdir():
    #                 if file_path.is_file():
    #                     archive.write(file_path, file_path.name)

    def create_archive(self, folder_path: Path, output_path: Path):
        """创建压缩包，支持多种格式"""
        compress_config = self.config['compress_file']
        format_type = compress_config.get('format', '7z').lower()

        try:
            if format_type == '7z':
                self._create_7z_archive(folder_path, output_path, compress_config)

            elif format_type == 'zip':
                self._create_zip_archive(folder_path, output_path, compress_config)

            elif format_type == 'tar':
                self._create_tar_archive(folder_path, output_path, compress_config)

            elif format_type in ['gz', 'gzip', 'bz2', 'bzip2', 'xz']:
                self._create_single_archive(folder_path, output_path, compress_config, format_type)

            else:
                self.logger.error(f"不支持的压缩格式: {format_type}")
                self.logger.info(f"使用默认7z模式压缩")
                self._create_7z_archive(folder_path, output_path, compress_config)
                return False

            return True

        except Exception as e:
            self.logger.error(f"创建压缩包失败: {e}")
            return False

    def _create_7z_archive(self, folder_path: Path, output_path: Path, config: dict):
        """创建7z压缩包"""
        password = config.get('password', 'fantwo')
        compression_level = config.get('compression_level', 5)
        method = config.get('method', 'lzma2')

        filters = self._get_7z_filters(method, compression_level)

        archive_args = {
            'password': password,
            'filters': filters
        }

        with py7zr.SevenZipFile(output_path, 'w', **archive_args) as archive:
            for file_path in folder_path.iterdir():
                if file_path.is_file():
                    archive.write(file_path, file_path.name)

        self.logger.info(f"创建7z压缩包完成 - 方法: {method}, 级别: {compression_level}")

    def _create_zip_archive(self, folder_path: Path, output_path: Path, config: dict):
        """创建ZIP压缩包"""
        compression_level = config.get('compression_level', 6)
        password = config.get('password')

        # 映射压缩级别到ZIP压缩方法
        compression_methods = {
            0: zipfile.ZIP_STORED,  # 不压缩
            1: zipfile.ZIP_DEFLATED,  # DEFLATE压缩
            2: zipfile.ZIP_BZIP2,  # BZIP2压缩 (需要Python 3.3+)
            3: zipfile.ZIP_LZMA,  # LZMA压缩 (需要Python 3.3+)
        }

        # 选择压缩方法
        if compression_level == 0:
            compression = zipfile.ZIP_STORED
        elif 1 <= compression_level <= 3:
            compression = compression_methods.get(compression_level, zipfile.ZIP_DEFLATED)
        else:
            compression = zipfile.ZIP_DEFLATED

        with zipfile.ZipFile(output_path, 'w', compression=compression) as archive:
            for file_path in folder_path.iterdir():
                if file_path.is_file():
                    # 设置密码（如果提供）
                    if password:
                        archive.setpassword(password.encode('utf-8'))
                    archive.write(file_path, file_path.name)

        self.logger.info(f"创建ZIP压缩包完成 - 压缩方法: {compression}")

    def _create_tar_archive(self, folder_path: Path, output_path: Path, _config: dict):
        """创建TAR归档（不压缩）"""
        import tarfile

        with tarfile.open(output_path, 'w') as archive:
            for file_path in folder_path.iterdir():
                if file_path.is_file():
                    archive.add(file_path, arcname=file_path.name)

        self.logger.info("创建TAR归档完成")

    def _create_single_archive(self, folder_path: Path, output_path: Path, config: dict, format_type: str):
        temp_tar = output_path.with_suffix('.temp.tar')
        try:
            # 先创建TAR
            self._create_tar_archive(folder_path, temp_tar, config)

            # 再用GZIP压缩
            compression_level = config.get('compression_level', 6)
            if format_type in ['gz', 'gzip']:
                with open(temp_tar, 'rb') as f_in:
                    with gzip.open(output_path, 'wb', compresslevel=compression_level) as f_out:
                        shutil.copyfileobj(f_in, f_out)
                self.logger.info(f"创建GZIP压缩包完成 - 级别: {compression_level}")

            elif format_type in ['bz2', 'bzip2']:
                with open(temp_tar, 'rb') as f_in:
                    with bz2.open(output_path, 'wb', compresslevel=compression_level) as f_out:
                        shutil.copyfileobj(f_in, f_out)
                    self.logger.info(f"创建BZIP2压缩包完成 - 级别: {compression_level}")
            elif format_type == 'xz':
                compression_level = config.get('compression_level', 6)
                with open(temp_tar, 'rb') as f_in:
                    with lzma.open(output_path, 'wb', preset=compression_level) as f_out:
                        shutil.copyfileobj(f_in, f_out)
                self.logger.info(f"创建XZ压缩包完成 - 级别: {compression_level}")
        finally:
            # 清理临时文件
            if temp_tar.exists():
                temp_tar.unlink()

    @staticmethod
    def _get_7z_filters(method: str, level: int) -> list:
        """获取7z压缩过滤器配置"""
        method_map = {
            'lzma2': {'id': py7zr.FILTER_LZMA2, 'preset': level},
            'lzma': {'id': py7zr.FILTER_LZMA, 'preset': level},
            'bzip2': {'id': py7zr.FILTER_BZIP2},
            'deflate': {'id': py7zr.FILTER_DEFLATE, 'preset': level},
            'copy': {'id': py7zr.FILTER_COPY},
            'ppmd': {'id': py7zr.FILTER_PPMD, 'order': 6, 'mem': 64},
            'delta': {'id': py7zr.FILTER_DELTA},
        }

        return [method_map.get(method.lower(), method_map['lzma2'])]

    @staticmethod
    def get_mime_type(filename):
        """根据文件名获取MIME类型"""
        mime_type, _ = mimetypes.guess_type(filename)
        return mime_type or 'image/jpeg'

    def create_post_request(self, folder_name: str, image_urls: List[str]) -> Dict:
        """构建发布请求"""
        self.logger.debug(folder_name + " 图片URL列表:")
        for i, url in enumerate(image_urls, 1):
            self.logger.debug(f"图片 {i}: {url}")
        first_image = image_urls[0] if image_urls else ""

        return {
            "title": folder_name,
            "content": "",
            "summary": "",
            "images": ",".join(image_urls),
            "cover": first_image,
            "categoryId": 2,
            "downloads": [],
            "tagNames": [],
            "tagIds": [],
            "status": "DRAFT",
            "requireLogin": False,
            "requireFollow": False,
            "requirePayment": False,
            "viewPrice": 0,
            "type": "image",
            "sort": 0
        }

    # def submit_post(self, post_data: Dict) -> bool:
    #     """提交发布请求"""
    #     create_url = self.config['url'].get('create')
    #     if not create_url:
    #         return False
    #
    #     try:
    #         response = requests.post(create_url, json=post_data)
    #         return response.status_code == 200
    #     except Exception as e:
    #         self.logger.error(f"提交发布失败: {e}")
    #         return False

    def process_archive(self, archive_path: Path):
        """处理单个压缩文件"""
        try:
            # 创建临时工作目录
            temp_dir = Path('./temp') / archive_path.stem

            # 如果文件夹存在就删除
            if temp_dir.exists() and temp_dir.is_dir():
                shutil.rmtree(temp_dir)

            temp_dir.mkdir(parents=True, exist_ok=True)

            self.logger.info(f"已创建目录: {temp_dir}")

            self.logger.info(f"开始解压: {archive_path.name}")
            self.logger.info(f"目标目录: {temp_dir}")

            # 解压
            if not self.extract_archive(archive_path, temp_dir):
                self.logger.error(f"解压失败: {archive_path.name}")
                return

            # 详细检查解压结果
            self.logger.debug("解压后目录内容:")
            for item in temp_dir.iterdir():
                self.logger.debug(f"{item.name} (文件夹: {item.is_dir()})")

            # 获取解压后的文件夹
            extracted_folders = [f for f in temp_dir.iterdir() if f.is_dir()]
            if not extracted_folders:
                self.logger.warning("警告: 未找到文件夹，可能文件直接解压到根目录")
                # 检查是否有图片文件直接解压
                image_files = [f for f in temp_dir.iterdir()
                               if f.is_file() and f.suffix.lower() in ['.jpg', '.png', '.jpeg']]
                self.logger.info(f"找到图片文件: {len(image_files)} 个")

                # 如果没有文件夹但有图片文件，使用临时目录作为内容文件夹
                if image_files:
                    content_folder = temp_dir
                    formatted_name = self.format_folder_name(archive_path.stem)
                    processed_folder = temp_dir

                    self.logger.info(f"使用根目录作为内容文件夹: {content_folder}")
                else:
                    self.logger.info("既没有文件夹也没有图片文件，跳过处理")
                    return
            else:
                # 正常情况：有文件夹
                content_folder = extracted_folders[0]
                formatted_name = self.format_folder_name(archive_path.stem)
                processed_folder = temp_dir / formatted_name
                self.logger.info(f"使用第一个文件夹: {content_folder.name}")

            # 重命名文件夹
            content_folder.rename(processed_folder)
            # content_folder.rename(temp_dir)

            # 清理文件
            self.clean_files(processed_folder)

            # 重命名文件
            self.rename_files(processed_folder)

            # 压缩图片
            self.compress_images(processed_folder)

            # 创建压缩包
            output_archive = Path('./output') / f"{formatted_name}.7z"
            output_archive.parent.mkdir(exist_ok=True)
            self.create_archive(processed_folder, output_archive)

            # 上传图片
            worker_num = self.config.get('worker', {}).get('upload', 1)
            uploaded_files = self.http_client.upload_files(processed_folder, worker_num)
            image_urls = [f.get('url', '') for f in uploaded_files if f.get('url')]

            # 创建并提交发布请求
            if image_urls:
                post_data = self.create_post_request(formatted_name, image_urls)
                success, res_data = self.http_client.submit_post(post_data)
                if success:
                    self.logger.success(f"处理完成: {archive_path.name}")
                    self.logger.success(res_data)
                else:
                    self.logger.error(f"发布提交失败: {archive_path.name}")

            # 清理临时文件
            shutil.rmtree(temp_dir)

        except Exception as e:
            self.logger.error(f"处理失败 {archive_path.name}: {e}")

    def worker(self):
        """工作线程函数"""
        while True:
            try:
                archive_path = self.task_queue.get_nowait()
            except queue.Empty:
                # 队列为空，退出循环
                break
            except Exception as e:
                # 捕获其他可能的异常，记录日志后继续
                self.logger.error(f"从队列获取任务时发生错误: {e}")
                break

            self.logger.info(f"开始处理: {archive_path.name}")
            self.process_archive(archive_path)
            self.task_queue.task_done()

    def run(self):
        """启动处理流程"""
        self.logger.separator("=", 60)
        self.logger.info("开始扫描压缩文件...")
        self.scan_archives()
        max_workers = self.config.get('worker', {}).get('unpack', 1)
        total_files = self.task_queue.qsize()
        self.logger.info(f"开始处理 {total_files} 个文件，使用 {max_workers} 个线程...")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(self.worker) for _ in range(max_workers)]

            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    self.logger.error(f"线程执行错误: {e}")

        self.logger.success("所有任务处理完成")
        self.logger.separator("=", 60)


if __name__ == "__main__":
    processor = ArchiveProcessor('config.toml')
    processor.run()

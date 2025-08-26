import mimetypes
import sys
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import requests

from FanTwoLogger import FanTwoLogger


class PicartHTTPClient:
    """HTTP 请求客户端，封装所有网络请求操作"""

    def __init__(self, config: Dict[str, Any], logger: FanTwoLogger):
        self.config = config
        self.session = requests.Session()
        self.logger = logger
        if not self._validate_auth_config():
            self.logger.critical("配置文件中的auth字段不完整或为空，程序退出")
            sys.exit(1)  # 直接退出进程
        token = self.config['auth']['token']
        if token is None:
            self.logger.error("token 不能为空")
            return
        self._setup_headers()

    def _setup_headers(self):
        """设置请求头"""
        auth_config = self.config.get('auth', {})
        self.headers = {
            'Authorization': f'Bearer {auth_config.get("token", "")}',
            'Device-Id': auth_config.get('did', ''),
            'Device-Name': auth_config.get('d_name', ''),
            'Device-Type': auth_config.get('d_type', ''),
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        # 清理空值头
        self.headers = {k: v for k, v in self.headers.items() if v and str(v).strip()}

    @staticmethod
    def get_mime_type(filename: str) -> str:
        """根据文件名获取MIME类型"""
        mime_type, _ = mimetypes.guess_type(filename)
        return mime_type or 'image/jpeg'

    def upload_file(self, file_path: Path, max_retries: int = 3) -> Optional[Dict]:
        """上传单个文件"""
        upload_url = self.config['url'].get('upload')
        if not upload_url:
            self.logger.error("未配置上传URL")
            return None

        if not file_path.exists() or not file_path.is_file() or file_path.stat().st_size == 0:
            self.logger.warning(f"文件无效或为空: {file_path.name}")
            return None

        for attempt in range(max_retries):
            try:
                with open(file_path, 'rb') as f:
                    mime_type = self.get_mime_type(file_path.name)
                    files = {'file': (file_path.name, f, mime_type)}

                    response = self.session.post(
                        upload_url,
                        files=files,
                        headers=self.headers,
                        timeout=60
                    )

                    if response.status_code in [200, 201]:
                        result = response.json()
                        if result.get('code') in [0, 200]:
                            self.logger.success(f"✓ 上传成功: {file_path.name}")
                            return result.get('data')[0]
                        else:
                            self.logger.error(f"✗ 业务错误 {file_path.name}: {result.get('message')}")
                            if attempt == max_retries - 1:
                                return None
                    else:
                        self.logger.error(f"✗ HTTP错误 {file_path.name}: {response.status_code}")
                        if attempt == max_retries - 1:
                            return None

            except requests.exceptions.Timeout:
                self.logger.warning(f"✗ 上传超时 {file_path.name} (尝试 {attempt + 1}/{max_retries})")
                if attempt == max_retries - 1:
                    return None
            except Exception as e:
                self.logger.error(f"✗ 上传错误 {file_path.name}: {e}")
                if attempt == max_retries - 1:
                    return None

            # 重试前等待
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # 指数退避

        return None

    def upload_files(self, folder_path: Path, max_workers: int = 1) -> List[Dict]:
        """上传文件夹中的所有文件"""
        valid_files = [f for f in folder_path.iterdir()
                       if f.is_file() and f.stat().st_size > 0]

        if not valid_files:
            self.logger.warning("文件夹中没有有效文件")
            return []

        uploaded_files = []

        if max_workers > 1:
            # 多线程上传
            from concurrent.futures import ThreadPoolExecutor, as_completed

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_file = {
                    executor.submit(self.upload_file, file_path): file_path
                    for file_path in sorted(valid_files)
                }

                for future in as_completed(future_to_file):
                    file_path = future_to_file[future]
                    try:
                        result = future.result()
                        if result:
                            uploaded_files.append(result)
                    except Exception as e:
                        self.logger.error(f"✗ 上传失败 {file_path.name}: {e}")
        else:
            # 单线程上传
            for file_path in sorted(valid_files):
                result = self.upload_file(file_path)
                if result:
                    uploaded_files.append(result)

        self.logger.success(f"上传完成，成功: {len(uploaded_files)}/{len(valid_files)}")
        return uploaded_files

    def submit_post(self, post_data: Dict) -> Tuple[bool, Optional[Dict]]:
        """提交发布请求"""
        create_url = self.config['url'].get('create')
        if not create_url:
            self.logger.error("未配置创建URL")
            return False, None

        try:
            response = self.session.post(
                create_url,
                json=post_data,
                headers=self.headers,
                timeout=30
            )

            if response.status_code in [200, 201]:
                result = response.json()
                if result.get('code') in [0, 200]:
                    self.logger.success("✓ 发布提交成功")
                    return True, result
                else:
                    self.logger.error(f"✗ 发布业务错误: {result.get('message')}")
                    return False, result
            else:
                self.logger.error(f"✗ 发布HTTP错误: {response.status_code}")
                return False, None

        except Exception as e:
            self.logger.error(f"✗ 发布提交失败: {e}")
            return False, None

    def test_connection(self) -> bool:
        """测试连接是否正常"""
        upload_url = self.config['url'].get('upload')
        if not upload_url:
            return False

        try:
            response = self.session.head(upload_url, timeout=10)
            return response.status_code < 400
        except:
            return False

    def update_token(self, new_token: str):
        """更新认证token"""
        self.headers['Authorization'] = f'Bearer {new_token}'
        if 'auth' in self.config:
            self.config['auth']['token'] = new_token
        self.logger.info("Token已更新")

    def _validate_auth_config(self) -> bool:
        """验证auth配置是否完整"""
        if 'auth' not in self.config:
            self.logger.error("配置文件中缺少auth字段")
            return False

        auth = self.config['auth']
        required_fields = ['token', 'did', 'd_name', 'd_type']

        for field in required_fields:
            if field not in auth:
                self.logger.error(f"auth字段中缺少必需的配置项: {field}")
                return False

            if not auth[field] or auth[field].strip() == "":
                self.logger.error(f"auth字段中的{field}不能为空")
                return False

        # 额外检查token格式（可选）
        token = auth['token']
        if len(token) < 10:  # 简单检查token长度
            self.logger.warning(f"token长度异常: {len(token)}")

        self.logger.info("auth配置验证通过")
        return True

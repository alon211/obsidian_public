#!/usr/bin/env python3
"""
Sync Obsidian markdown files to Notion database via GitHub Actions

Version: 1.0.0
Author: Claude (with user collaboration)
Date: 2026-02-19

Features:
- Uses unique file ID (SHA256 of relative path) for reliable page matching
- Supports both Markdown ![](path) and Obsidian ![[path]] image syntax
- Handles inline images (images within text lines)
- Converts images to GitHub Raw URLs for reliable Notion display
- Handles YAML frontmatter
- Supports headings, lists, code blocks, quotes, paragraphs
- Creates new pages or updates existing ones based on file_id
- Windows UTF-8 encoding support for Chinese characters and emojis

Requirements:
pip install notion-client>=2.2.1,<3.0.0 markdown2 httpx

Notion Database Setup:
1. Create a database in Notion
2. Add a "file_id" property (type: rich_text) to your database
3. Add a "Name" property (type: title) - this is the page title
4. Create a Notion Integration at https://www.notion.so/my-integrations
5. Add the Integration to your database (click "..." > "Add connections")
6. Copy the Integration token (starts with "ntn_")
7. Copy the Database ID from the database URL

GitHub Actions Setup:
1. Add NOTION_TOKEN and NOTION_DATABASE_ID as repository secrets
2. Push changes to trigger automatic sync
"""

import os
import re
import sys
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional

# Windows UTF-8 encoding fix for Chinese and emoji display
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

try:
    from notion_client import Client, APIResponseError
    import httpx
except ImportError:
    print("Error: notion-client not installed. Run: pip install notion-client")
    sys.exit(1)


class ObsidianToNotionSync:
    """Sync Obsidian vault to Notion database using unique file ID"""

    def __init__(self, token: str, database_id: str, vault_path: str):
        self.notion = Client(auth=token)
        self.token = token  # 保存 token 用于 HTTP API
        self.database_id = database_id
        self.vault_path = Path(vault_path)

        # 调试：打印 Client 类型
        print(f"[Debug] Notion Client type: {type(self.notion)}")
        print(f"[Debug] Has databases attr: {hasattr(self.notion, 'databases')}")
        if hasattr(self.notion, 'databases'):
            print(f"[Debug] Databases type: {type(self.notion.databases)}")
            print(f"[Debug] Has query attr: {hasattr(self.notion.databases, 'query')}")

    def generate_file_id(self, file_path: Path) -> str:
        """为文件生成唯一 ID

        使用文件相对路径的 SHA256 hash 作为唯一 ID
        这样即使文件移动或重命名，只要内容路径关系不变，ID 就稳定

        Args:
            file_path: 文件的完整路径

        Returns:
            16 位十六进制的文件 ID
        """
        # 计算相对路径
        try:
            relative_path = file_path.relative_to(self.vault_path)
        except ValueError:
            # 文件不在 vault_path 下，使用绝对路径
            relative_path = file_path

        # 转换为正斜杠（跨平台一致性）
        path_str = str(relative_path).replace('\\', '/')

        # 生成 SHA256 hash 并取前 16 位
        file_id = hashlib.sha256(path_str.encode('utf-8')).hexdigest()[:16]

        return file_id

    def find_image_path(self, markdown_dir: Path, image_ref: str) -> Optional[str]:
        """查找图片文件的完整路径

        支持以下格式:
        - [[Pasted image 20260217085700.png]]
        - [[./images/photo.png]]
        """
        # 去掉 [[]] 包裹
        clean_name = image_ref.strip('[]!')

        # 去掉可能的路径前缀
        clean_name = Path(clean_name).name

        # 检查 images 子文件夹 (Obsidian 默认图片附件位置)
        images_dir = markdown_dir / "images"
        if images_dir.exists():
            for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.PNG', '.JPG', '.JPEG']:
                img_path = images_dir / (clean_name + ext)
                if img_path.exists():
                    return str(img_path)

        # 检查附件文件夹
        attachments_dir = markdown_dir / "attachments"
        if attachments_dir.exists():
            for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.PNG', '.JPG', '.JPEG']:
                img_path = attachments_dir / (clean_name + ext)
                if img_path.exists():
                    return str(img_path)

        # 检查同级目录
        for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.PNG', '.JPG', '.JPEG']:
            img_path = markdown_dir / (clean_name + ext)
            if img_path.exists():
                return str(img_path)

        return None

    def upload_image_to_notion(self, image_path: str) -> Optional[str]:
        """上传图片到 Notion

        使用 GitHub Raw URL 作为外部图片
        需要设置环境变量: GITHUB_REPO (格式: username/repo)
        """
        try:
            print(f"  [Image] Processing: {Path(image_path).name}")

            # 计算相对于仓库根目录的路径
            try:
                rel_path = Path(image_path).relative_to(self.vault_path)
                print(f"    [Image] Relative path: {rel_path}")
            except ValueError:
                rel_path = Path(image_path).name
                print(f"    [Image] Using filename only: {rel_path}")

            # 获取 GitHub 仓库信息（从环境变量或默认值）
            github_repo = os.environ.get('GITHUB_REPO', 'alon211/obsidian_public')
            github_branch = os.environ.get('GITHUB_BRANCH', 'main')

            # 转换为 GitHub Raw URL
            # 将反斜杠转换为正斜杠
            rel_path_str = str(rel_path).replace('\\', '/')

            # URL 编码中文字符 - 使用 safe 参数避免编码斜杠
            from urllib.parse import quote
            rel_path_encoded = quote(rel_path_str.encode('utf-8'), safe='/')

            github_raw_url = f"https://raw.githubusercontent.com/{github_repo}/{github_branch}/{rel_path_encoded}"

            print(f"  [Image] GitHub URL created (length: {len(github_raw_url)})")
            return github_raw_url

        except Exception as e:
            print(f"  [Error] Failed to process image: {type(e).__name__}")
            print(f"  [Error] Message: {str(e)[:200]}")
            import traceback
            traceback.print_exc()
            return None

    def _get_mime_type(self, file_path: str) -> str:
        """获取文件的 MIME 类型"""
        ext = Path(file_path).suffix.lower()
        mime_types = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.webp': 'image/webp'
        }
        return mime_types.get(ext, 'image/png')

    def _resolve_image_path(self, markdown_dir: Path, image_path: str) -> Optional[str]:
        """解析图片路径（支持相对路径）

        支持的格式:
        - assets/OP20EM10程序逻辑/file.png (相对于 markdown 文件)
        - ../images/file.png (相对路径)
        - /absolute/path/file.png (绝对路径)
        """
        # 去掉 URL 协议前缀
        if image_path.startswith(('http://', 'https://')):
            return None  # 外部图片，不需要处理

        # 转换为 Path 对象
        img_path = Path(image_path)

        # 如果是绝对路径，直接返回
        if img_path.is_absolute():
            return str(img_path) if img_path.exists() else None

        # 相对路径：相对于 markdown 文件所在目录
        full_path = markdown_dir / img_path

        print(f"    [Debug] Resolving: {image_path}")
        print(f"    [Debug] markdown_dir: {markdown_dir}")
        print(f"    [Debug] full_path: {full_path}")
        print(f"    [Debug] exists: {full_path.exists()}")

        if full_path.exists():
            return str(full_path)

        # 如果直接找不到，尝试其他可能的路径
        # 检查 images 文件夹
        images_path = markdown_dir / "images" / img_path.name
        if images_path.exists():
            print(f"    [Debug] Found in images/: {images_path}")
            return str(images_path)

        # 检查 assets 文件夹
        assets_path = markdown_dir / "assets" / img_path.name
        if assets_path.exists():
            print(f"    [Debug] Found in assets/: {assets_path}")
            return str(assets_path)

        # 检查 attachments 文件夹
        attachments_path = markdown_dir / "attachments" / img_path.name
        if attachments_path.exists():
            print(f"    [Debug] Found in attachments/: {attachments_path}")
            return str(attachments_path)

        # 打印调试信息
        print(f"    [Debug] Image not found: {image_path}")
        print(f"    [Debug] Tried: {full_path}")

        return None

    def _process_inline_images(self, line: str, markdown_dir: Path) -> str:
        """处理段落中的内联图片

        将 ![](path) 或 ![[path]] 替换为占位符或处理
        注意：Notion 不支持真正的内联图片，所以这里用占位符
        """
        # 处理 Obsidian wiki-link 内联图片 ![[path]]
        def replace_obsidian_image(match):
            image_name = match.group(1)
            image_path = self.find_image_path(markdown_dir, image_name)
            if image_path:
                return f"[📷 {image_name}]"
            return f"[⚠️ 图片: {image_name}]"

        line = re.sub(r'!\[\[(.*?)\]\]', replace_obsidian_image, line)

        # 处理标准 Markdown 内联图片 ![alt](path)
        def replace_md_image(match):
            alt_text = match.group(1)
            image_path = match.group(2)
            full_path = self._resolve_image_path(markdown_dir, image_path)
            if full_path and Path(full_path).exists():
                return f"[📷 {alt_text or Path(full_path).name}]"
            return f"[⚠️ 图片: {alt_text or image_path}]"

        line = re.sub(r'!\[(.*?)\]\((.*?)\)', replace_md_image, line)

        return line

    def convert_obsidian_to_notion_blocks(self, markdown_content: str, markdown_dir: Path) -> List[Dict[str, Any]]:
        """将 Obsidian Markdown 转换为 Notion blocks

        支持的语法:
        - # 标题
        - - / * 无序列表
        - > 引用
        - ``` 代码块
        - ![[图片]] (Obsidian wiki-link)
        - [[内部链接]]
        """
        blocks = []
        lines = markdown_content.split('\n')
        i = 0

        print(f"  [Debug] Converting markdown: {len(lines)} lines")

        while i < len(lines):
            line = lines[i].rstrip()

            # 跳过 YAML frontmatter
            if line == '---' and i == 0:
                i += 1
                while i < len(lines) and lines[i].strip() != '---':
                    i += 1
                i += 1
                continue

            # 跳过空行
            if not line.strip():
                i += 1
                continue

            # 处理标题
            if line.startswith('#'):
                level = len(line) - len(line.lstrip('#'))
                level = min(level, 3)  # Notion 只支持 h1-h3
                content = line.lstrip('#').strip()
                block_type = f"heading_{level}"
                blocks.append({
                    "type": block_type,
                    block_type: {
                        "rich_text": [{"type": "text", "text": {"content": content}}]
                    }
                })
                i += 1
                continue

            # 处理无序列表
            if re.match(r'^[\-\*]\s+', line):
                content = re.sub(r'^[\-\*]\s+', '', line)
                blocks.append({
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {
                        "rich_text": [{"type": "text", "text": {"content": content}}]
                    }
                })
                i += 1
                continue

            # 处理任务列表 - [ ]
            if re.match(r'^\-\s\[[\sx]\]', line):
                is_checked = '[x]' in line.lower()
                content = re.sub(r'^\-\s\[[\sx]\]\s*', '', line)
                blocks.append({
                    "type": "to_do",
                    "to_do": {
                        "rich_text": [{"type": "text", "text": {"content": content}}],
                        "checked": is_checked
                    }
                })
                i += 1
                continue

            # 处理代码块
            if line.strip().startswith('```'):
                lang = line.strip()[3:].strip() or "plain text"
                i += 1
                code_lines = []
                while i < len(lines) and not lines[i].strip().startswith('```'):
                    code_lines.append(lines[i])
                    i += 1
                code_content = '\n'.join(code_lines)
                blocks.append({
                    "type": "code",
                    "code": {
                        "rich_text": [{"type": "text", "text": {"content": code_content}}],
                        "language": lang
                    }
                })
                i += 1
                continue

            # 处理引用
            if line.startswith('>'):
                content = line[1:].strip()
                blocks.append({
                    "type": "quote",
                    "quote": {
                        "rich_text": [{"type": "text", "text": {"content": content}}]
                    }
                })
                i += 1
                continue

            # 处理图片 - 优先处理单独一行的图片
            # 格式1: ![[filename]] (Obsidian wiki-link)
            obsidian_image_match = re.match(r'^!\[\[(.*?)\]\]$', line)
            if obsidian_image_match:
                image_name = obsidian_image_match.group(1)
                print(f"  [Debug] Processing Obsidian image: {image_name}")
                image_path = self.find_image_path(markdown_dir, image_name)
                if image_path:
                    image_url = self.upload_image_to_notion(image_path)
                    if image_url:
                        blocks.append({
                            "type": "image",
                            "image": {
                                "type": "external",
                                "external": {"url": image_url}
                            }
                        })
                        print(f"  [Debug] Image block added")
                        i += 1
                        continue
                    else:
                        # 占位符: 图片未上传
                        blocks.append({
                            "type": "paragraph",
                            "paragraph": {
                                "rich_text": [{
                                    "type": "text",
                                    "text": {"content": f"[📷 图片: {image_name}]"}
                                }]
                            }
                        })
                        i += 1
                        continue
                else:
                    print(f"  [Warning] Image not found: {image_name}")
                    blocks.append({
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{
                                "type": "text",
                                "text": {"content": f"[⚠️ 图片未找到: {image_name}]"}
                            }]
                        }
                    })
                    i += 1
                    continue

            # 格式2: ![alt](path) 或 !(path) (标准 Markdown)
            md_image_match = re.match(r'^!\[(.*?)\]\((.*?)\)$', line)
            if md_image_match:
                alt_text = md_image_match.group(1)
                image_path = md_image_match.group(2)
                print(f"  [Debug] Processing Markdown image: ![{alt_text}]({image_path})")

                # 解析图片路径
                full_image_path = self._resolve_image_path(markdown_dir, image_path)

                if full_image_path and Path(full_image_path).exists():
                    image_url = self.upload_image_to_notion(full_image_path)
                    if image_url:
                        blocks.append({
                            "type": "image",
                            "image": {
                                "type": "external",
                                "external": {"url": image_url}
                            }
                        })
                        print(f"  [Debug] Image block added")
                        i += 1
                        continue
                    else:
                        # 占位符: 图片未上传
                        blocks.append({
                            "type": "paragraph",
                            "paragraph": {
                                "rich_text": [{
                                    "type": "text",
                                    "text": {"content": f"[📷 图片: {Path(full_image_path).name if full_image_path else image_path}]"}
                                }]
                            }
                        })
                        i += 1
                        continue
                else:
                    print(f"  [Warning] Image not found: {image_path}")
                    blocks.append({
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{
                                "type": "text",
                                "text": {"content": f"[⚠️ 图片未找到: {image_path}]"}
                            }]
                        }
                    })
                    i += 1
                    continue

            # 处理内联图片 - 先提取所有内联图片，然后再处理文本
            inline_images = []

            # 提取标准 Markdown 内联图片 ![alt](path)
            md_inline_images = list(re.finditer(r'!\[(.*?)\]\((.*?)\)', line))
            for match in md_inline_images:
                alt_text = match.group(1)
                image_path = match.group(2)
                inline_images.append(('markdown', image_path, alt_text))

            # 提取 Obsidian wiki-link 内联图片 ![[path]]
            obsidian_inline_images = list(re.finditer(r'!\[\[(.*?)\]\]', line))
            for match in obsidian_inline_images:
                image_name = match.group(1)
                inline_images.append(('obsidian', image_name, None))

            # 如果有内联图片，需要特殊处理
            if inline_images:
                # 将文本行拆分为文本和图片的混合 blocks
                # 先创建一个用于存储文本部分的列表
                text_parts = []
                last_end = 0

                # 收集所有内联图片的位置
                all_matches = []
                for match in re.finditer(r'!\[\[.*?\]\]|!\[.*?\]\(.*?\)', line):
                    match_text = match.group(0)
                    all_matches.append((match.start(), match.end(), match_text))

                if all_matches:
                    # 处理每个图片和其前后的文本
                    for start, end, match_text in sorted(all_matches):
                        # 添加前面的文本部分
                        if start > last_end:
                            text_parts.append(line[last_end:start])

                        # 处理图片
                        if match_text.startswith('![['):
                            # Obsidian wiki-link: ![[path]]
                            image_name = match_text[3:-2]  # 去掉 ![[ 和 ]]
                            print(f"  [Debug] Processing inline Obsidian image: {image_name}")
                            # 使用 _resolve_image_path 以支持带路径的图片引用
                            full_image_path = self._resolve_image_path(markdown_dir, image_name)
                            if full_image_path and Path(full_image_path).exists():
                                image_url = self.upload_image_to_notion(full_image_path)
                                if image_url:
                                    blocks.append({
                                        "type": "image",
                                        "image": {
                                            "type": "external",
                                            "external": {"url": image_url}
                                        }
                                    })
                                else:
                                    # 图片上传失败，添加占位符
                                    blocks.append({
                                        "type": "paragraph",
                                        "paragraph": {
                                            "rich_text": [{"type": "text", "text": {"content": f"[📷 {image_name}]"}}]
                                        }
                                    })
                            else:
                                # 图片未找到
                                blocks.append({
                                    "type": "paragraph",
                                    "paragraph": {
                                        "rich_text": [{"type": "text", "text": {"content": f"[⚠️ {image_name}]"}}]
                                    }
                                })
                        else:
                            # Markdown 图片: ![alt](path)
                            # 从 ![alt](path) 中提取 alt 和 path
                            inner = match_text[2:-1]  # 去掉 ![ 和 ]
                            if '](' in inner:
                                alt_text, image_path = inner.split('](', 1)
                                image_path = image_path.rstrip(')')
                                print(f"  [Debug] Processing inline Markdown image: ![{alt_text}]({image_path})")
                                full_image_path = self._resolve_image_path(markdown_dir, image_path)
                                if full_image_path and Path(full_image_path).exists():
                                    image_url = self.upload_image_to_notion(full_image_path)
                                    if image_url:
                                        blocks.append({
                                            "type": "image",
                                            "image": {
                                                "type": "external",
                                                "external": {"url": image_url}
                                            }
                                        })
                                    else:
                                        blocks.append({
                                            "type": "paragraph",
                                            "paragraph": {
                                                "rich_text": [{"type": "text", "text": {"content": f"[📷 {alt_text or Path(full_image_path).name}]"}}]
                                            }
                                        })
                                else:
                                    blocks.append({
                                        "type": "paragraph",
                                        "paragraph": {
                                            "rich_text": [{"type": "text", "text": {"content": f"[⚠️ {image_path}]"}}]
                                        }
                                    })

                        last_end = end

                    # 添加最后的文本部分
                    if last_end < len(line):
                        text_parts.append(line[last_end:])

                    # 将所有文本部分合并为一个段落
                    if text_parts:
                        combined_text = ''.join(text_parts).strip()
                        if combined_text:
                            blocks.append({
                                "type": "paragraph",
                                "paragraph": {
                                    "rich_text": [{"type": "text", "text": {"content": combined_text}}]
                                }
                            })

                    i += 1
                    continue

            # 处理普通段落（没有内联图片的情况）
            if line.strip():
                blocks.append({
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": line.strip()}}]
                    }
                })

            i += 1

        print(f"  [Debug] Total blocks generated: {len(blocks)}")
        return blocks

    def find_page_by_file_id(self, database_id: str, file_id: str) -> Optional[str]:
        """在数据库中通过 file_id 查找已存在的页面

        Returns:
            页面 ID，如果未找到则返回 None
        """
        print(f"  [Debug] Looking for file_id: {file_id}")

        # 方法1: 使用 databases.query (如果可用)
        if hasattr(self.notion, 'databases') and hasattr(self.notion.databases, 'query'):
            try:
                print(f"  [Debug] Using databases.query() method")
                response = self.notion.databases.query(
                    database_id=database_id,
                    filter={
                        "property": "file_id",
                        "rich_text": {
                            "equals": file_id
                        }
                    }
                )
                results = response.get('results', [])
                print(f"  [Debug] Found {len(results)} pages with file_id")

                if results:
                    page_id = results[0]['id']
                    print(f"  [Debug] Existing page ID: {page_id}")
                    return page_id
                return None
            except Exception as e:
                print(f"  [Debug] databases.query failed: {e}")

        # 方法2: 直接使用 HTTP API
        try:
            print(f"  [Debug] Using HTTP API directly")
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json"
            }

            url = f"https://api.notion.com/v1/databases/{database_id}/query"
            payload = {
                "filter": {
                    "property": "file_id",
                    "rich_text": {
                        "equals": file_id
                    }
                }
            }

            print(f"  [Debug] POST to {url}")
            print(f"  [Debug] Filter: property='file_id', equals='{file_id}'")

            response = httpx.post(url, headers=headers, json=payload, timeout=30.0)

            print(f"  [Debug] Response status: {response.status_code}")

            if response.status_code != 200:
                print(f"  [Error] HTTP {response.status_code}: {response.text}")
                return None

            data = response.json()
            results = data.get('results', [])
            print(f"  [Debug] HTTP API found {len(results)} pages")

            if results:
                page_id = results[0]['id']
                print(f"  [Debug] Found existing page: {page_id}")
                return page_id

            print(f"  [Debug] No existing page found with file_id")
            return None

        except httpx.HTTPStatusError as e:
            print(f"  [Error] HTTP {e.response.status_code}: {e.response.text[:200]}")
            if e.response.status_code == 400:
                print(f"  [Info] This might mean 'file_id' property doesn't exist or can't be filtered")
            elif e.response.status_code == 401:
                print(f"  [Info] Authentication failed - check NOTION_TOKEN")
            elif e.response.status_code == 403:
                print(f"  [Info] Permission denied - check Integration capabilities")
            elif e.response.status_code == 404:
                print(f"  [Info] Database not found - check NOTION_DATABASE_ID")
            return None
        except httpx.TimeoutException:
            print(f"  [Error] HTTP request timed out")
            return None
        except Exception as e:
            print(f"  [Error] HTTP request failed: {type(e).__name__}: {str(e)[:200]}")
            import traceback
            traceback.print_exc()
            return None

    def clear_page_blocks(self, page_id: str) -> bool:
        """删除页面中的所有 blocks

        Returns:
            是否成功删除
        """
        try:
            # 获取页面中的所有 blocks
            blocks = []
            has_more = True
            start_cursor = None

            while has_more:
                params = {"block_id": page_id}
                if start_cursor:
                    params["start_cursor"] = start_cursor

                response = self.notion.blocks.children.list(**params)
                blocks.extend(response.get('results', []))
                has_more = response.get('has_more', False)
                start_cursor = response.get('next_cursor')

            # 删除所有 blocks
            for block in blocks:
                if block.get('type') != 'unsupported':  # 跳过不支持的 block 类型
                    try:
                        self.notion.blocks.delete(block_id=block['id'])
                    except Exception as e:
                        print(f"    [Warning] Failed to delete block {block['id']}: {e}")

            return True
        except Exception as e:
            print(f"  [Error] Failed to clear page blocks: {e}")
            return False

    def update_page_blocks(self, page_id: str, blocks: List[Dict[str, Any]]) -> bool:
        """更新页面的 blocks

        Returns:
            是否成功更新
        """
        try:
            # 分批添加 blocks，每批最多 100 个
            for i in range(0, len(blocks), 100):
                batch = blocks[i:i+100]
                self.notion.blocks.children.append(
                    block_id=page_id,
                    children=batch
                )
            return True
        except Exception as e:
            print(f"  [Error] Failed to update page blocks: {e}")
            return False

    def create_or_update_page(self, markdown_file: Path):
        """创建或更新 Notion 页面"""
        # 生成文件的唯一 ID
        file_id = self.generate_file_id(markdown_file)

        print(f"\n📄 Processing: {markdown_file.relative_to(self.vault_path)}")
        print(f"  [File ID: {file_id}]")

        # 读取 markdown 内容
        try:
            with open(markdown_file, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f"  ✗ Failed to read file: {e}")
            return

        # 获取标题（文件名或第一个 # 标题）
        title = markdown_file.stem
        first_line = content.split('\n')[0].strip()
        if first_line.startswith('#'):
            title = first_line.lstrip('#').strip()

        # 转换为 Notion blocks
        markdown_dir = markdown_file.parent
        blocks = self.convert_obsidian_to_notion_blocks(content, markdown_dir)

        if not blocks:
            print(f"  ⚠ No content blocks found, skipping")
            return

        print(f"  → Generated {len(blocks)} blocks")

        # 检查页面是否已存在（通过 file_id）
        existing_page_id = self.find_page_by_file_id(self.database_id, file_id)

        if existing_page_id:
            print(f"  ✓ Found existing page: {existing_page_id}")
            print(f"  → Updating page: '{title}'")

            # 删除页面中的所有现有 blocks
            if not self.clear_page_blocks(existing_page_id):
                print(f"  ✗ Failed to clear existing blocks")
                return

            print(f"  → Cleared existing blocks")

            # 添加新的 blocks
            if not self.update_page_blocks(existing_page_id, blocks):
                print(f"  ✗ Failed to add new blocks")
                return

            if len(blocks) > 100:
                print(f"  → Added {len(blocks)} blocks in {(len(blocks) + 99) // 100} batches")
            else:
                print(f"  → Added {len(blocks)} blocks")

            print(f"  ✅ Updated page: {existing_page_id}")
        else:
            print(f"  → Creating new page: '{title}'")
            try:
                # 分批创建，每批最多 100 个 blocks
                page = self.notion.pages.create(
                    parent={"database_id": self.database_id},
                    properties={
                        "Name": {
                            "title": [{"text": {"content": title}}]
                        },
                        "file_id": {
                            "rich_text": [{"text": {"content": file_id}}]
                        }
                    },
                    children=blocks[:100]
                )

                # 如果有更多 blocks，分批添加
                if len(blocks) > 100:
                    page_id = page['id']
                    for i in range(100, len(blocks), 100):
                        self.notion.blocks.children.append(
                            block_id=page_id,
                            children=blocks[i:i+100]
                        )
                    print(f"  → Added {len(blocks) - 100} additional blocks")

                print(f"  ✅ Created page: {page['id']}")
            except Exception as e:
                print(f"  ✗ Failed to create page: {e}")

    def run(self):
        """主函数：遍历所有 markdown 文件并同步"""
        print(f"\n{'='*50}")
        print(f"Obsidian → Notion Sync (with file_id matching)")
        print(f"{'='*50}")
        print(f"Source: {self.vault_path}")
        print(f"Database: {self.database_id}")

        # 诊断：使用 HTTP API 打印数据库结构
        try:
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json"
            }
            url = f"https://api.notion.com/v1/databases/{self.database_id}"
            response = httpx.get(url, headers=headers, timeout=30.0)

            if response.status_code == 200:
                db = response.json()
                print(f"\n[Debug] Database structure:")
                title = db.get('title', [{}])[0].get('plain_text', 'N/A') if db.get('title') else 'N/A'
                print(f"  Title: {title}")
                props = db.get('properties', {})
                print(f"  Properties ({len(props)}):")
                for prop_name, prop_data in props.items():
                    prop_type = prop_data.get('type', 'unknown')
                    print(f"    - '{prop_name}' (type: {prop_type})")

                # 检查是否有 file_id 属性
                if 'file_id' not in props:
                    print(f"\n  ⚠️  WARNING: 'file_id' property not found!")
                    print(f"  Please add a 'file_id' property (type: rich_text) to your database")
                else:
                    print(f"\n  ✅ 'file_id' property found")
            else:
                print(f"\n[Warning] Could not retrieve database structure: HTTP {response.status_code}")
        except Exception as e:
            print(f"\n[Warning] Could not retrieve database structure: {e}")

        print(f"{'='*50}\n")

        # 查找所有 .md 文件
        markdown_files = list(self.vault_path.rglob('*.md'))

        # 过滤掉 .obsidian 和其他系统文件夹
        excluded_paths = ['.obsidian', '.git', '.github', 'node_modules']
        markdown_files = [
            f for f in markdown_files
            if not any(excluded in str(f) for excluded in excluded_paths)
        ]

        print(f"Found {len(markdown_files)} markdown files\n")

        for md_file in markdown_files:
            self.create_or_update_page(md_file)

        print(f"\n{'='*50}")
        print(f"Sync completed!")
        print(f"{'='*50}\n")


def main():
    """主入口函数"""
    # 从环境变量获取配置
    NOTION_TOKEN = os.environ.get('NOTION_TOKEN')
    NOTION_DATABASE_ID = os.environ.get('NOTION_DATABASE_ID')
    VAULT_PATH = os.environ.get('GITHUB_WORKSPACE', os.getcwd())

    # 验证配置
    if not NOTION_TOKEN:
        print("Error: NOTION_TOKEN environment variable not set")
        print("Please add it as a GitHub Secret")
        sys.exit(1)

    if not NOTION_DATABASE_ID:
        print("Error: NOTION_DATABASE_ID environment variable not set")
        print("Please add it as a GitHub Secret")
        sys.exit(1)

    # 执行同步
    sync = ObsidianToNotionSync(NOTION_TOKEN, NOTION_DATABASE_ID, VAULT_PATH)
    sync.run()


if __name__ == "__main__":
    main()

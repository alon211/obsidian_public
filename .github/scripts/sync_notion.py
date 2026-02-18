#!/usr/bin/env python3
"""
Sync Obsidian markdown files to Notion database via GitHub Actions

Features:
- Converts Obsidian wiki-link syntax [[image]] to Notion image blocks
- Handles YAML frontmatter
- Supports headings, lists, code blocks, quotes, paragraphs
- Creates new pages or updates existing ones based on title

Requirements:
pip install notion-client markdown2
"""

import os
import re
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    from notion_client import Client
except ImportError:
    print("Error: notion-client not installed. Run: pip install notion-client")
    sys.exit(1)


class ObsidianToNotionSync:
    """Sync Obsidian vault to Notion database"""

    def __init__(self, token: str, database_id: str, vault_path: str):
        self.notion = Client(auth=token)
        self.database_id = database_id
        self.vault_path = Path(vault_path)

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
        """上传图片到 Notion S3 并返回 URL

        注意: Notion API 的文件上传功能需要特殊权限，
        这里暂时返回 None，使用占位文本代替
        """
        # TODO: 实现 Notion S3 图片上传
        # 需要: 1. 获取上传 URL
        #       2. 上传图片文件
        #       3. 返回最终 URL
        print(f"  [Image] Found: {image_path} (upload not yet implemented)")
        return None

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

            # 处理图片 ![[filename]]
            image_match = re.match(r'^!\[\[(.*?)\]\]$', line)
            if image_match:
                image_name = image_match.group(1)
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
                    else:
                        # 占位符: 图片未上传
                        blocks.append({
                            "type": "paragraph",
                            "paragraph": {
                                "rich_text": [{
                                    "type": "text",
                                    "text": {"content": f"[📷 图片: {image_name}]", "attributes": {"code": True}}
                                }]
                            }
                        })
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

            # 处理内联图片 ![[图片]] 在文本中
            inline_image_match = re.search(r'!\[\[(.*?)\]\]', line)
            if inline_image_match:
                image_name = inline_image_match.group(1)
                image_path = self.find_image_path(markdown_dir, image_name)
                if image_path:
                    # 替换为占位符
                    line = re.sub(r'!\[\[(.*?)\]\]', f"[📷 {image_name}]", line)

            # 处理普通段落
            if line.strip():
                blocks.append({
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": line.strip()}}]
                    }
                })

            i += 1

        return blocks

    def find_page_by_title(self, database_id: str, title: str) -> Optional[str]:
        """在数据库中查找已存在的页面

        Returns:
            页面 ID，如果未找到则返回 None
        """
        try:
            response = self.notion.databases.query(
                database_id=database_id,
                filter={
                    "property": "Name",
                    "title": {
                        "equals": title
                    }
                }
            )
            if response.get('results'):
                return response['results'][0]['id']
        except Exception as e:
            print(f"  [Error] Finding page: {e}")
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
        print(f"\n📄 Processing: {markdown_file.relative_to(self.vault_path)}")

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

        # 检查页面是否已存在
        existing_page_id = self.find_page_by_title(self.database_id, title)

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
        print(f"Obsidian → Notion Sync")
        print(f"{'='*50}")
        print(f"Source: {self.vault_path}")
        print(f"Database: {self.database_id}")
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

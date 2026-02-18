#!/usr/bin/env python3
"""
本地测试脚本 - 模拟 GitHub Actions 运行

用法:
1. 设置环境变量:
   set NOTION_TOKEN=你的token
   set NOTION_DATABASE_ID=你的database_id

2. 运行测试:
   python .github/scripts/run_local_test.py
"""

import os
import sys
from pathlib import Path

# 添加脚本目录到路径
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

# 导入同步模块
from sync_notion import ObsidianToNotionSync

def main():
    print("="*60)
    print("本地测试 - Obsidian to Notion Sync")
    print("="*60)

    # 获取配置
    NOTION_TOKEN = os.environ.get('NOTION_TOKEN')
    NOTION_DATABASE_ID = os.environ.get('NOTION_DATABASE_ID')

    # 如果没有设置环境变量，提示用户输入
    if not NOTION_TOKEN:
        print("\n请设置 NOTION_TOKEN 环境变量:")
        print("  Windows: set NOTION_TOKEN=你的token")
        print("  Linux/Mac: export NOTION_TOKEN=你的token")
        NOTION_TOKEN = input("\n或者直接输入 NOTION_TOKEN: ").strip()

    if not NOTION_DATABASE_ID:
        print("\n请设置 NOTION_DATABASE_ID 环境变量:")
        print("  Windows: set NOTION_DATABASE_ID=你的database_id")
        print("  Linux/Mac: export NOTION_DATABASE_ID=你的database_id")
        NOTION_DATABASE_ID = input("\n或者直接输入 NOTION_DATABASE_ID: ").strip()

    # 设置仓库路径 (脚本所在目录的父目录的父目录)
    vault_path = script_dir.parent.parent.resolve()
    print(f"\n仓库路径: {vault_path}")

    # 验证配置
    if not NOTION_TOKEN:
        print("\n❌ 错误: NOTION_TOKEN 未设置")
        sys.exit(1)

    if not NOTION_DATABASE_ID:
        print("\n❌ 错误: NOTION_DATABASE_ID 未设置")
        sys.exit(1)

    print(f"\n配置信息:")
    print(f"  Token: {NOTION_TOKEN[:15]}...{NOTION_TOKEN[-10:]}")
    print(f"  Database ID: {NOTION_DATABASE_ID}")
    print("="*60)

    # 执行同步
    try:
        sync = ObsidianToNotionSync(NOTION_TOKEN, NOTION_DATABASE_ID, str(vault_path))
        sync.run()
        print("\n✅ 测试完成!")
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

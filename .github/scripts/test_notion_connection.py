#!/usr/bin/env python3
"""
测试 Notion 连接和 Database ID
"""

import os
import sys

try:
    from notion_client import Client
    import httpx
except ImportError:
    print("Installing required packages...")
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "notion-client", "httpx"])
    from notion_client import Client
    import httpx

# 从环境变量获取配置
NOTION_TOKEN = os.environ.get('NOTION_TOKEN', input('Enter NOTION_TOKEN: '))
NOTION_DATABASE_ID = os.environ.get('NOTION_DATABASE_ID', input('Enter NOTION_DATABASE_ID: '))

print(f"\n{'='*50}")
print(f"Notion Database Connection Test")
print(f"{'='*50}")
print(f"Token: {NOTION_TOKEN[:20]}...{NOTION_TOKEN[-10:]}")
print(f"Database ID: {NOTION_DATABASE_ID}")
print(f"{'='*50}\n")

# 方法1: 使用 notion_client
print("[Test 1] Using notion_client to retrieve database...")
try:
    notion = Client(auth=NOTION_TOKEN)
    db = notion.databases.retrieve(NOTION_DATABASE_ID)
    print(f"✅ Success!")
    print(f"  Title: {db.get('title', [{}])[0].get('plain_text', 'N/A')}")
    props = db.get('properties', {})
    print(f"  Properties ({len(props)}):")
    for prop_name, prop_data in props.items():
        prop_type = prop_data.get('type', 'unknown')
        print(f"    - '{prop_name}' (type: {prop_type})")
except Exception as e:
    print(f"❌ Failed: {e}")

# 方法2: 使用 HTTP API
print(f"\n[Test 2] Using HTTP API to query database...")
try:
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}"
    response = httpx.get(url, headers=headers, timeout=30.0)

    if response.status_code == 200:
        data = response.json()
        print(f"✅ Success!")
        print(f"  Title: {data.get('title', [{}])[0].get('plain_text', 'N/A')}")
        props = data.get('properties', {})
        print(f"  Properties ({len(props)}):")
        for prop_name, prop_data in props.items():
            prop_type = prop_data.get('type', 'unknown')
            print(f"    - '{prop_name}' (type: {prop_type})")
    else:
        print(f"❌ HTTP {response.status_code}: {response.text}")
except Exception as e:
    print(f"❌ Failed: {e}")

print(f"\n{'='*50}")
print(f"If you see 'Properties (0)' or connection errors,")
print(f"please check:")
print(f"  1. Integration has Read/Update/Insert content permissions")
print(f"  2. Integration is added to the database")
print(f"  3. Database ID is correct (32 characters)")
print(f"{'='*50}\n")

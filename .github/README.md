# Obsidian to Notion 自动同步

使用 GitHub Actions 自动将 Obsidian 仓库中的 Markdown 文件和图片同步到 Notion 数据库。

## 功能特性

- ✅ 自动同步: 每次 push 到 main 分支时自动触发
- ✅ 手动触发: 支持在 GitHub Actions 页面手动运行
- ✅ Obsidian 语法支持:
  - Wiki-link 图片语法: `![[图片.png]]`
  - YAML frontmatter
  - 标题 (# ## ###)
  - 列表 (无序、任务列表)
  - 代码块
  - 引用
- ✅ 图片路径自动识别:
  - `images/` 子文件夹
  - `attachments/` 子文件夹
  - 同级目录

## 快速开始

### 1. 获取 Notion API 凭证

#### 创建 Notion Integration

1. 访问 https://www.notion.so/my-integrations
2. 点击 "New integration"
3. 填写名称 (如: "Obsidian Sync")
4. 选择你的 workspace
5. 复制 "Internal Integration Token" (格式: `ntn_XXXX...` 或 `secret_XXXX...`)

#### 创建 Notion 数据库

1. 在 Notion 中创建一个数据库 (Database)
2. 确保数据库第一列名为 "Name" (标题列)
3. 点击数据库右上角 "..." → "Add connections"
4. 选择你刚创建的 Integration
5. 复制数据库 ID (从 URL 中获取，32 个字符)

**获取 Database ID 的方法:**
```
https://www.notion.so/username/[DATABASE_ID]?v=...
                     ↑ 这是 Database ID
```

### 2. 配置 GitHub Secrets

在你的 GitHub 仓库中添加 Secrets:

1. 打开仓库页面
2. Settings → Secrets and variables → Actions
3. 点击 "New repository secret"
4. 添加以下两个 secrets:

| Secret 名称 | 值 |
|------------|-----|
| `NOTION_TOKEN` | 你的 Notion Integration Token |
| `NOTION_DATABASE_ID` | 你的 Notion Database ID (32字符) |

### 3. 文件结构

确保你的仓库包含以下文件:

```
obsidian_public/
├── .github/
│   ├── workflows/
│   │   └── sync-to-notion.yml    # GitHub Actions 工作流
│   ├── scripts/
│   │   └── sync_notion.py         # 同步脚本
│   └── README.md                   # 本文档
├── 调试前需要确认的项目/
│   ├── OP20EM10程序逻辑.md         # Markdown 文件
│   └── images/                     # 图片文件夹
│       ├── Pasted image 20260217085700.png
│       └── ...
└── ...
```

### 4. 触发同步

#### 自动触发
```bash
git add .
git commit -m "update notes"
git push origin main
```

#### 手动触发
1. 打开仓库的 "Actions" 标签页
2. 选择 "Sync to Notion" 工作流
3. 点击 "Run workflow"
4. 选择分支并点击 "Run workflow"

## 支持的 Markdown 语法

| 语法 | 示例 | Notion 转换 |
|------|------|-------------|
| 标题 | `# 标题` | Heading 1 |
| 列表 | `- 项目` | Bullet List |
| 任务 | `- [x] 完成` | To-do (checked) |
| 代码 | ` ```python ` | Code Block |
| 引用 | `> 引用` | Quote |
| 图片 | `![[图片.png]]` | Image (支持) |

## 图片处理

脚本会自动在以下位置查找图片:

1. `images/` 子文件夹
2. `attachments/` 子文件夹
3. 与 Markdown 文件同级目录

**注意:** 目前图片上传功能尚未实现，图片会显示为占位符 `[📷 图片: filename]`。

## 故障排除

### 1. "Unauthorized" 错误

**原因:** API Token 无效或未授权

**解决:**
- 确认 Token 格式正确 (`ntn_XXXX` 或 `secret_XXXX`)
- 确认 Integration 已添加到数据库
- 确认 Integration 有读写权限

### 2. "database_id not found" 错误

**原因:** Database ID 错误或无权限访问

**解决:**
- 检查 Database ID 是否为 32 个字符
- 确认数据库已与 Integration 共享
- 确认 Integration 在数据库的连接列表中

### 3. "object not found" 错误

**原因:** 数据库第一列不是 "Name"

**解决:**
- 在 Notion 数据库中，将第一列重命名为 "Name"

### 4. 图片未显示

**原因:** 图片上传功能尚未实现

**临时方案:**
- 将图片上传到图床 (如 Imgur, Cloudinary)
- 在 Markdown 中使用标准图片语法: `![alt](URL)`

## 高级配置

### 修改同步目录

编辑 `.github/workflows/sync-to-notion.yml`:

```yaml
- name: Sync to Notion
  env:
    VAULT_PATH: "your/custom/path"  # 添加自定义路径
  run: |
    python3 .github/scripts/sync_notion.py
```

### 仅同步特定文件夹

编辑 `.github/scripts/sync_notion.py` 中的 `run()` 方法:

```python
# 修改过滤条件
markdown_files = [
    f for f in markdown_files
    if "调试前需要确认的项目" in str(f)  # 只同步特定文件夹
]
```

## 开发计划

- [ ] 实现图片上传到 Notion S3
- [ ] 支持更新已有页面 (而非只创建新页面)
- [ ] 支持 Wikilink 内部链接转换
- [ ] 支持更多 Markdown 语法 (表格、数学公式等)
- [ ] 添加增量同步 (仅同步修改的文件)

## 参考资源

- [Notion API 文档](https://developers.notion.com/reference)
- [GitHub Actions 文档](https://docs.github.com/en/actions)
- [obsidian-notion-sync](https://github.com/Akash-Sharma-1/obsidian-notion-sync) - 原始灵感来源

## 许可证

MIT

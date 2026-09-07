# 政治理论题库问答

一个针对 4180 道政治理论题设计的结构化题库检索系统。用户粘贴原题后，系统优先精确匹配题库标准答案；原题有少量缺字或改写时使用 FTS5 与模糊检索。系统不调用大模型，标准答案始终来自题库数据库。

## 为什么不是普通长文档 RAG

普通固定长度切片可能把上一题答案和下一题题干放进同一个 Chunk。本项目先将 DOCX 解析为“一题一条记录”，保留题型、题干、选项、答案、章节和原文段落位置，再建立检索索引。

```text
DOCX
  -> 结构化解析与 4180 题完整性校验
  -> SQLite questions 表 + FTS5 trigram 索引
  -> 原题精确匹配
  -> 全文/模糊检索
  -> 置信度与 Top1/Top2 分差门控
  -> 确定性返回题库标准答案
```

## 主要能力

- 解析单选题、多选题、判断题以及 `【答案】A` 等格式差异；
- 导入前校验总题数、答案格式和答案引用选项；
- Unicode、全半角、题号、空格和标点标准化；
- 精确匹配优先，不消耗模型 API；
- FTS5 trigram + RapidFuzz 处理轻微缺字和改写；
- 相似题置信度不足时展示候选题，不擅自猜答案；
- Streamlit 查询界面、访问令牌、会话级限流和检索诊断；
- Docker Compose、非 root 容器、Volume 持久化、Nginx 和 HTTPS 部署配置。

## 本地启动

将题库放到：

```text
source/question_bank.docx
```

运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1
```

访问 `http://127.0.0.1:8503`。

也可以分步执行：

```powershell
.\.venv\Scripts\python.exe scripts\import_docx.py
.\.venv\Scripts\python.exe -m streamlit run app.py --server.port 8503
```

## 访问配置

复制 `.env.example` 为 `.env`。本地可以关闭鉴权，公网部署必须设置访问密码。系统不需要模型 API Key。

## 数据边界

- 标准答案来自导入题库，不代表系统对题库内容进行了事实核验；
- 原题精确查询可以稳定返回数据库记录，改写越大越需要候选确认；
- 原题重复且答案冲突时，系统必须让用户根据章节选择；
- 题库 DOCX、运行数据库和访问令牌默认不进入 Git。

## 测试

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe scripts\audit_database.py
.\.venv\Scripts\python.exe scripts\smoke_test_bank.py
```

公网部署见 [deploy/README.md](deploy/README.md)。

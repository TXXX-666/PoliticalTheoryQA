# 政治理论题库问答公网部署

目标地址预留为 `https://quiz.insightpilot-ai.top`，与现有两个项目共用服务器和主域名，通过子域名和 Nginx 分流。应用端口只绑定 `127.0.0.1:8503`。

## 1. DNS

在现有域名解析中增加 A 记录：

```text
主机记录：quiz
记录类型：A
记录值：47.76.114.249
```

若服务器公网 IP 已变化，以实际公网 IP 为准。

## 2. 获取代码和上传题库

项目推送到 GitHub 后，在服务器执行：

```bash
cd /opt
git clone <你的 GitHub 仓库地址> political-theory-qa
cd /opt/political-theory-qa
mkdir -p source
```

题库文件不提交 GitHub。在本机 PowerShell 单独上传：

```powershell
scp "C:\Users\Admin\Desktop\政治理论1201题--4180题册.docx" root@47.76.114.249:/opt/political-theory-qa/source/question_bank.docx
```

## 3. 配置环境变量

```bash
cd /opt/political-theory-qa
cp .env.example .env
openssl rand -hex 32
nano .env
```

至少填写：

```env
QABANK_ACCESS_TOKEN=上一步生成的随机令牌
QABANK_REQUIRE_AUTH=true
```

模型 API 可暂时留空：

```env
DASHSCOPE_API_KEY=
QABANK_ENABLE_SEMANTIC=false
QABANK_ENABLE_LLM_EXPLANATION=false
```

留空时原题精确匹配、FTS 和模糊检索仍然工作。需要语义检索或辅助说明时，再填写 API Key。

## 4. 启动容器

```bash
docker compose up -d --build
docker compose ps
docker compose logs --tail=200 quiz
curl -f http://127.0.0.1:8503/_stcore/health
```

首次启动会自动解析题库并导入 4180 道题。数据库保存在 Docker Volume 中。

## 5. 配置 Nginx 和 HTTPS

```bash
cp deploy/nginx/quiz-limits.conf.example /etc/nginx/conf.d/quiz-limits.conf
cp deploy/nginx/quiz.conf.example /etc/nginx/sites-available/political-theory-qa
ln -s /etc/nginx/sites-available/political-theory-qa /etc/nginx/sites-enabled/political-theory-qa
nginx -t
systemctl reload nginx
```

DNS 生效后申请证书：

```bash
certbot --nginx -d quiz.insightpilot-ai.top
curl -I https://quiz.insightpilot-ai.top
```

云安全组只需要保持 `80` 和 `443` 开放，不要开放 `8503`。

## 6. 可选语义索引和 LLM 辅助说明

在 `.env` 填写 `DASHSCOPE_API_KEY` 后：

```bash
docker compose exec quiz python scripts/build_embeddings.py
nano .env
```

设置：

```env
QABANK_ENABLE_SEMANTIC=true
QABANK_ENABLE_LLM_EXPLANATION=true
```

重新创建容器以加载环境变量：

```bash
docker compose up -d --force-recreate quiz
```

## 7. 更新代码

```bash
cd /opt/political-theory-qa
git pull origin main
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 quiz
```

不要执行 `docker compose down -v`，否则会删除运行数据库和可选语义索引。题库原 DOCX 位于宿主机 `source/`，不会因容器重建而丢失。

## 8. 加入现有统一入口页

应用上线验证后，在 `/opt/insightpilot/portal/index.html` 增加指向
`https://quiz.insightpilot-ai.top` 的项目入口，再执行：

```bash
nginx -t
systemctl reload nginx
```

统一入口页只是静态链接，不需要将题库服务合并进 InsightPilot 容器。

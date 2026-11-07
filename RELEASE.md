# Mailpit v1.33.0.1 Beta

**名称与分类**　Mailpit；包 ID 为 mailpit；开发工具；TOS 7，x86_64，依赖 Docker Engine。

**简介**　在 NAS 上接收本机应用发出的 SMTP 测试邮件，在受密码保护的网页收件箱查看正文、邮件头及原文。适用于开发调试。

**使用说明**　启动前配置独立账户文件 config/auth.htpasswd，确保 UID 1000 可读、应用 data 目录可写。NAS 本机 SMTP 为 127.0.0.1:11025，Web 为 18025。直接 HTTP 访问仅用于受信网络。邮件最多保留 100 封，单封上限 5 MB。配置及构建方式见 README.md。

**版本与许可**　首个 TOS Beta，采用 Mailpit 上游稳定版 v1.33.0。镜像由上游 axllent/mailpit 发布，包内锁定 linux/amd64 摘要。上游采用 MIT 许可，版权和原文在 licenses/Mailpit-MIT.txt。[上游源码](https://github.com/axllent/mailpit/tree/v1.33.0)

**Release 附件**　dist/mailpit.tar.gz 和 dist/SHA256SUMS。安装包 SHA256 为 `07ee2d10ce47f8c4eaa4f9d0b73364dc1ac29ebdfc9d878fae0317d23dd19ac0`。

**供审核员复核**　TOS 7.0.1422 真机在导入同一摘要镜像后，通过 Compose 启动、浏览器收信、SMTP 回环隔离、数据保留和清理。默认镜像代理首次拉取返回 502。应用中心安装与卸载待平台验证。

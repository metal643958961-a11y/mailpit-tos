# Mailpit for TOS 7

本地 Beta 适配包 1.33.0.1，适用于 x86_64 TOS 7 与 Docker Engine。Mailpit 接收 NAS 本机开发服务发出的测试邮件，通过浏览器查看邮件内容。上游稳定版为 v1.33.0。Compose 固定上游 Docker Hub 的 linux/amd64 内容摘要，安装归档只含 TOS 元数据、语言文件、图标及 Compose。[上游](https://github.com/axllent/mailpit/tree/v1.33.0) · [镜像](https://hub.docker.com/r/axllent/mailpit) · [MIT 许可原文](licenses/Mailpit-MIT.txt)

## 首次使用

1. 在所选卷的 `DockerAppData/mailpit` 下准备 `config` 和 `data`。容器使用 UID/GID `1000:1000`，需要读取配置、写入数据。请只为应用自己的目录设置权限。
2. 在有 Apache htpasswd 工具的本地终端运行 `htpasswd -nB inbox`，按提示输入独立强口令。把输出的整行保存到 `config/auth.htpasswd`，限制为容器 UID 可读。修改账户文件后重启应用。[上游认证说明](https://mailpit.axllent.org/docs/configuration/passwords/)
3. 启动应用，从受信网络打开桌面入口，或经可信 HTTPS 反代访问网页收件箱。端口为 18025，直接连接使用 HTTP Basic 认证。启动时若缺少有效账户行，容器会退出并按重启策略重试。
4. 将 NAS 本机测试程序的 SMTP 地址设为 `127.0.0.1:11025`。此回环地址属于 NAS 主机，其他容器内的 localhost 指向其自身。只投递合成测试邮件。适配包未配置转寄或外部 SMTP 中继。邮件存入 `data/mailpit.db`，最多保留 100 封，单封上限 5 MB。

## 构建与验收

在本目录运行 `python3 build.py`，再运行 `(cd dist && shasum -a 256 -c SHA256SUMS)`。集成测试在专用空 Linux Docker 虚拟机中以 root 运行 `python3 test.py dist/mailpit.tar.gz`，使用隔离目录和临时测试身份。

TOS 7.0.1422 真机导入同一摘要镜像后，已验证原样 Compose 运行、浏览器收信、SMTP 回环隔离、重建持久化和清理。该体验机默认镜像代理首次拉取返回 502。应用中心一键安装、桌面入口与卸载选项仍待验证。

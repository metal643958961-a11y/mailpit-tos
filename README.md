# mailpit for TOS 7

x86_64 Docker 整改版本 1.33.0.2。本地静态及容器回归通过，真实TOS应用中心安装仍待官方验收；Release发布不代表已通过审核。

首次启动自动生成独立随机凭据，无需 .env 或预先 chown。初始化服务与主服务均使用 1000:1000，私有数据位于专用命名卷的 private 目录。管理员从 Container Manager 中查看该应用卷的 private/password，用户名为 inbox。请勿将凭据放入日志或反馈。保留该卷重装可保留数据和密码；删除卷会永久清除数据。

旧版绑定目录迁移必须停服、备份，将原 data 和凭据移入命名卷 private 下并保持 1000:1000 所有权，验证后再切换。本地回归验证将分别记录，不将重建等同于跨版本升级。

[隐私政策](PRIVACY.md) · [第三方许可](licenses/) · [反馈](https://github.com/metal643958961-a11y/mailpit-tos/issues)

公开源码、隐私政策和许可随此固定版本提供。上游镜像全部来自 Docker Hub，以摘要固定。





## 构建与本地回归

`python3 build.py` 在本应用目录确定性重建四文件安装包及SHA256。依赖系统Python3、Ruby YAML，不安装额外包。
隔离Linux回归命令与适用范围见[TESTING.md](TESTING.md)。

## 卸载和迁移

停止应用后，在Container Manager核对挂载的Docker卷：默认Compose项目为`mailpit`，通常卷名`mailpit_state`，平台可能因冲突改名，必须以实际挂载为准。默认卸载保留该卷；需要永久删除时先备份并确认没有其他容器引用，再删除该专用卷。不要使用全局volume prune。TOS的“删除数据”目前不自动删除命名卷。
旧版数据迁移必须停服：把原data内容复制到新卷private/data，旧凭据复制到private/password，所有者保持配置user且目录700、凭据600。首次新启动会从原凭据生成NATS配置或Mailpit哈希。InspIRCd原聊天内存不可迁移。不要把正式凭据写到命令行日志或公开Issue。迁移在Linux合成数据上通过，不等同TOS自动升级。

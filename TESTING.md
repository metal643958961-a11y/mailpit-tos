# 本地验证

构建：`python3 build.py`。包规范：在Linux使用对应架构官方TOSAppSelfTestingTool运行 `-c dist/mailpit.tar.gz`。

容器回归必须使用**空的、专用Linux Docker VM**（会重启Docker，拒绝检测到其他容器的环境）：先按Compose固定摘要缓存linux/amd64镜像，再执行 `sudo python3 test_runtime.py mailpit dist/mailpit.tar.gz legacy_test.py`。不提供旧版包参数时，旧版数据迁移将输出NOT_TESTED；可追加本地已核验原版包路径验证迁移。需要Docker Compose v2与Python3.9+。

VictoriaMetrics的/data由真实TOS平台映射/chown；本脚本仅在隔离临时目录模拟这一行为，不访问宿主/data，不代表真实TOS安装/卸载验证。其他三款使用专用命名卷。所有数据为随机凭据和合成消息/指标，结束时清理。

真实TOS安装仅在获授权设备使用官方工具 `-i`；普通Linux不能冒充TOS。源码中的测试工具不是安装包文件。

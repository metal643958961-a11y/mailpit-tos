# 验证范围 · 2026-11-12

mailpit 1.33.0.2：官方TOSAppSelfTestingTool静态检查通过；专用Linux x86_64 Docker首次初始化、认证、核心功能、重启、合成数据持久化及清理通过。固定镜像安全扫描HIGH/CRITICAL=0（数据库2026-11-12），不代表没有其他风险。

真实TOS应用中心安装、桌面入口、升级、卸载尚未验收。冷启动测试使用缓存镜像，历史TOS代理502尚未证实解除。旧版数据迁移与命名卷/绑定目录清理限制见README。

本批原始审核清单共26 PASS、0 FAIL、7 NOT_TESTED；NATS 2/0/0，Mailpit 2/0/0，InspIRCd 7/0/2，VictoriaMetrics 15/0/5。其中4项为新版本公开源码/隐私链接待发布验证，另3项为VictoriaMetrics真实TOS生命周期验收；这不表示其他应用已完成真实TOS验收。发布后的匿名链接与下载校验另行记录。

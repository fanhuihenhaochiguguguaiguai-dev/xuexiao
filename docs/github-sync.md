# GitHub 持续双向同步

唯一正式仓库：https://github.com/fanhuihenhaochiguguguaiguai-dev/xuexiao 。同步使用当前环境已有的 Git 认证，不保存令牌到工程。

AI 在每个开发阶段开始前运行 `python tools/sync_progress.py begin`；通过检查后运行 `python tools/sync_progress.py checkpoint --stage 阶段说明`。后台 `python -u tools/sync_progress.py watch --interval 60` 每分钟检查远程并重试待推送成果。手机用户无需执行命令。

阶段提交先检查 JSON 和疑似凭据，再运行配置中的 Python 测试、移动/性能 JS 测试以及模型、物理、构建和 PWA 门禁。源码内容、权限与验证收据匹配才复用结果。仅文档/报告修改只检查格式和凭据；真实浏览器与手机硬件仍需对应专项验收，不由 Git 检查冒充。

| 情况 | 行为 |
| --- | --- |
| 文件无变化 | 不创建重复提交，复用内容哈希验证收据 |
| 远程领先 | 安全快进；与未提交修改重叠时推迟，不覆盖 |
| 两端有无冲突的提交 | `merge-tree` 先预检，合并后重新验证再正常推送 |
| 提交冲突 | 保持本地文件，上传 `codex/saved-阶段-提交号` 分支；主分支保留远程成果，等待AI修复 |
| 验证不通过 | 不创建阶段提交、不推送失败成果，保留文件和日志 |
| 网络或认证失败 | 已验证阶段先保存在本地提交；单次最多3次推送，后台每分钟再试 |
| 待推送时又开始编辑 | 只允许推送先前验证的不可变提交，不提交这些新编辑 |
| 同步锁被占用 | 跳过本轮，下一轮再试；进程退出自动释放锁 |

状态可用 `python tools/sync_progress.py status` 查看。正常阶段返回 `SYNCED`；`CHECKPOINT_PENDING` 表示尚未同步，`VALIDATION_FAILED` 表示未通过检查，`CONFLICT_REQUIRES_RESOLUTION` 表示停止自动合并。CLI 在可恢复失败时保持退出码0以免打断开发，**必须检查 JSON 状态，不能以退出码当成成功**。本地日志在 `git rev-parse --git-path campus-sync` 返回目录内。

并行任务使用 `python tools/sync_progress.py worktree --task water` 等命令创建独立 `codex/water` 分支和外部工作树。完成任务后由AI检查、合并回主线并重新验证；不自动猜测冲突解法。现有工作树不会被重复创建或覆盖。

本次11项真实 Git 集成测试使用隔离临时裸仓库和两个克隆，已验证快进、脏文件保护、增量提交、干净分叉合并、冲突保存、检查失败、断网恢复、编辑中重试、长期进程状态刷新、独立工作树与互斥锁。未向用户仓库制造测试冲突。

持续运行范围为**当前存活的云环境**。环境休眠、删除或凭据撤销时不能保证继续推送；本地成果与待同步状态保留，下一会话按 AGENTS.md 恢复。GitHub Actions负责推送后的再次验证，不能替代本地云进程把未推送的文件上传。

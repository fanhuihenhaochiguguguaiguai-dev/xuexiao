# 校园探索实验室的续作约定

这是独立体验试验，当前分支为 `experiments/campus-exploration-lab`。正式 `xuexiao/main` 和其原Site不属于本次试验的写入范围；不要将此独立根目录分支整体合入main。可验证的模块或经验后续按明确任务迁移。

1. 先读 `docs/EXPERIMENT.md`、`reports/verification.json`、`reports/web-deployment.json`，复用通过结果。原校园/人物GLB和world的字节身份见baseline，未改动就不重建或重新导入。
2. 每阶段先 `python3 tools/sync_progress.py begin`，通过相关检查后 `checkpoint --stage ...`。同步引擎保留冲突，不强推、reset、clean或自动stash。watcher只在云环境运行时检查，不承诺停机后仍同步；环境重启后核对实际PID/命令，再复用或重启。
3. 四地点寻路使用已有Rapier碰撞和保守网格，自动行走必须经原人物控制器；不得用传送或篡改终点伪造到达。优先小闭环验证再扩大。只运行修改影响到的验证。
4. 桌面软件WebGPU、手机尺寸与模拟触控不等于实体安卓性能。页面/Canvas初始化不等于场景可见，原站全景需等待遮罩结束。未授权的原始照片/全景截图只放忽略的.cache，不能提交。
5. 试验Site身份以 `.openai/hosting.json` 为准，保留原访问范围，不重复创建Site。`tools/publish_source.py`是本环境缺少Sites官方本地脚本时的替代路径；短期官方凭据只能经隐藏stdin传递，不落盘、放命令参数或日志。静态归档须与已推送提交逐字节一致。
6. 源码主保存位置是本实验分支；Sites是对应已验收提交的发布副本。发布回执可作为纯文档提交随后补存，不因此重复发布不变的游戏。保持正式校园精度缺口和手机未验证事项真实可见。

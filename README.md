# 河南经贸 · 校园探索实验室

这是用户授权的独立体验试验，不是正式数字校园的新主线，不覆盖 `xuexiao` 项目。复用现有校园、人物、Rapier碰撞和水面，重点验证真实步行寻路、导览、建筑互动与安卓网页画质预算。

来源检查点、保留模型哈希和全景参考见 `reports/baseline.json`。现有建筑高度、部分楼栋身份及人物细节仍为近似，不是学校实测数字孪生。原始全景照片未复制或上传；仅按用户提供链接打开原站。地图资料署名 © OpenStreetMap contributors / ODbL，混合素材来源与许可见 `docs/UPSTREAM_ASSETS.md`。

```sh
npm ci
npm test
npm run build
python3 -m http.server 8080 --bind 127.0.0.1 --directory dist
```

导航网格由已有物理碰撞与校园边界生成；缓存命中则跳过。`npm run build:nav` 只在碰撞源变化后需要执行。12条真实Rapier步行路线和控制中断等边界有独立自动检查。软件渲染/手机尺寸模拟不等于安卓硬件验收。

持续同步复用正式项目已经验证的 `tools/sync_progress.py`，配置指向本实验仓库；它不会改动正式校园仓库。每个阶段先 `begin`，验证后 `checkpoint --stage ...`。`watch --interval 60` 只在本次云环境运行时检查并重试已验证提交，不提交正在编辑的内容；停机后不承诺持续同步。冲突保留，不强推。

实际改动、对比收益、可迁移经验与限制见 [试验报告](docs/EXPERIMENT.md)，机器结果见 [验证汇总](reports/verification.json)。新建仓库权限被GitHub拒绝，已使用独立实验分支保存；不会修改正式main。

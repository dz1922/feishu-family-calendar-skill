---
name: feishu-family-calendar
description: 当用户要用飞书（Feishu/Lark）开放平台管理家庭日程，例如孩子接送、兴趣班、学校周通知、指派家人任务时使用。
---

# 飞书家庭日程 Skill

## 原则
- **双模式**：共享日历「孩子们」管时间与到点提醒；共享任务清单「孩子们」管谁去做。一件事若既有时间又需要有人执行，两边都建。
- 凭证只从环境变量 `FEISHU_APP_ID` / `FEISHU_APP_SECRET` 读，绝不写进代码、日志或回复。
- 成员用 open_id，由用户提供；不要猜。对外示例一律用角色昵称：大熊（爸爸）、兔妈（妈妈）、老松（爷爷）、花奶奶（奶奶）、老船长（外公）、织毛衣外婆（外婆）、小鹿（大宝，女孩）、小豆丁（二宝，男孩）。

## 接入
1. 企业自建应用，开通日历、任务、通讯录读取权限，发布版本，可见范围含全部家人。
2. `POST /open-apis/auth/v3/tenant_access_token/internal` 取 token（`scripts/feishu_family.py token` 自检）。
3. 使用 Calendar v4、Task v2 OpenAPI。

## 步骤
1. 建日历：`create-calendar`；建清单：`create-tasklist`。
2. 共享日历：`POST /open-apis/calendar/v4/calendars/{calendar_id}/acls?user_id_type=open_id`，每位家人 `role=writer`（或 reader）。提醒家人在飞书里刷新/接受。
3. 共享清单：家人加为协作成员 `editor`（`share-tasklist`）。仅作执行人不够。
4. 日历事件：周期用 RRULE（如 `FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR`），`reminders=[{minutes:0}]`。
5. 任务：`due` + `repeat_rule` + `reminders=[{relative_fire_minute:0}]`。**多天周期必须按星期拆成多条**，每条 `FREQ=WEEKLY;BYDAY=<单一天>`（`add-task --byday` 自动拆）。
6. 接送任务 `due` 设当天 12:00，标题带放学时间，如「🦌小鹿｜放学16:10」。
7. 部署每天 23:00（Asia/Shanghai）`complete-today`：只完成「当天到期且未完成」的任务，使下一期出现；不碰其他日期。

## 命名规范
- 格式「<emoji><孩子昵称>｜<事项>」，女孩 👧、男孩 👦🏻；接送类可用 🦌 等形象 emoji。
- 短标题，不写长句；细节放描述。

## 临时事项 / 老师周通知
- 从图片或文字中提取要准备的物品/材料/活动，逐条建日历+任务。
- 默认周日 19:00 提醒准备本周事项；通知写明具体某天的，提前一天 19:00 提醒。

## 分工示例
- 小豆丁工作日放学：执行人老松，大熊也列为执行人便于知情。
- 小鹿各天放学时间不同：按天拆任务，分别指派老船长或老松。

## 坑与核对
- 周期任务界面只显示当前/下一期 → 按天拆分。
- 周期任务不完成就不滚动 → 23:00 定时。
- 家人看不到 → 检查 ACL、清单协作者、可见范围、版本是否发布。
- 批量删除/重建：先列出→确认→删除→复查数量为 0。
- 避免两个程序同时改同一清单；建完用 `list --tasklist` 按「标题+BYDAY」去重核对。
- 写操作前可 `--dry-run`；创建、删除、共享前向用户确认范围。

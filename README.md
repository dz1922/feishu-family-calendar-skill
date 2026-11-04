# 飞书家庭日程（feishu-family-calendar）

用飞书（Feishu / Lark）开放平台，把一家人的接送、兴趣班、学校通知管起来：**日历管时间，任务管谁去做**。

> 本项目为社区作品，**非飞书官方**，与字节跳动/飞书无隶属关系。

## 适合谁

- 家里有娃，接送、上课、带东西经常靠微信群喊；
- 家人（爸妈、爷爷奶奶、外公外婆）都装了飞书或愿意装；
- 有人愿意花 30 分钟照着做一次，之后基本自动运转。

示例家庭（全文统一使用）：

| 角色 | 昵称 |
|---|---|
| 爸爸 | 大熊 |
| 妈妈 | 兔妈 |
| 爷爷 | 老松 |
| 奶奶 | 花奶奶 |
| 外公 | 老船长 |
| 外婆 | 织毛衣外婆 |
| 大宝 | 小鹿（女孩，一年级） |
| 二宝 | 小豆丁（男孩，幼儿园中班） |

## 核心理念：日历 + 任务 双模式

| | 共享日历「孩子们」 | 共享任务清单「孩子们」 |
|---|---|---|
| 负责 | 几点、在哪，到点提醒 | 谁去做：接送、带装备、准备材料 |
| 例子 | 👧小鹿｜舞蹈课 周三 18:00 | 🦌小鹿｜16:10｜放学 → 指派老船长 |

日历让全家看到「今天有什么」，任务让每个人知道「这件是我的」。

## 5 分钟上手

需要 Python 3.8+，无第三方依赖。

### 1. 建飞书自建应用
飞书开放平台 → 开发者后台 → 创建「企业自建应用」，记下 App ID / App Secret。

### 2. 开权限并发布
- 权限：**日历**（读写日历、日程、共享）、**任务**（读写任务、清单）、**通讯录**（读取用户基本信息，用于拿 open_id）。
- 「版本管理与发布」创建版本并发布；**可见范围要包含所有家人**。

```bash
export FEISHU_APP_ID=你的AppID
export FEISHU_APP_SECRET=你的AppSecret
python3 scripts/feishu_family.py token   # 显示「token 正常」即成功
```
建议写进 `.env`（已被 .gitignore 忽略），千万不要提交到仓库。

### 3. 建日历和清单
```bash
python3 scripts/feishu_family.py create-calendar --name 孩子们
python3 scripts/feishu_family.py create-tasklist --name 孩子们
```
记下输出的 calendar_id 和 tasklist_guid。

### 4. 共享给家人（必做！）
应用建的日历/清单默认只有应用自己能看到。家人的 open_id 可在开放平台 API 调试台或通讯录接口查到。
```bash
python3 scripts/feishu_family.py share-calendar --calendar <日历ID> --open-id <爸爸的open_id> <妈妈的open_id> <爷爷的open_id> --role writer
python3 scripts/feishu_family.py share-tasklist --tasklist <清单guid> --open-id <爸爸的open_id> <妈妈的open_id> <爷爷的open_id> <外公的open_id>
```
家人在飞书日历里刷新或接受共享。

### 5. 导入日程
```bash
# 日历：工作日放学，开始时提醒
python3 scripts/feishu_family.py add-event --calendar <日历ID> --title "👦🏻小豆丁｜放学" \
  --date 2026-11-02 --start 16:00 --end 16:30 --rrule "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR"

# 任务：工作日小豆丁放学，老松接，大熊知情；自动拆成 5 条
python3 scripts/feishu_family.py add-task --tasklist <清单guid> --title "👦🏻小豆丁｜16:00｜放学" \
  --byday MO,TU,WE,TH,FR --due-time 12:00 --assignee <爷爷的open_id> <爸爸的open_id>

# 小鹿每天放学时间不同，按天分别指派
python3 scripts/feishu_family.py add-task --tasklist <清单guid> --title "🦌小鹿｜16:10｜放学" \
  --byday TU,TH --assignee <爷爷的open_id>
python3 scripts/feishu_family.py add-task --tasklist <清单guid> --title "🦌小鹿｜15:30｜放学" \
  --byday MO,WE --assignee <外公的open_id>
```
所有写操作都可先加 `--dry-run` 看请求内容。完整示例见 `examples/family.example.json`。

### 6. 开定时
```bash
crontab -e   # 粘贴 examples/crontab.example 的内容
```
每天 23:00 自动勾掉「今天到期且未完成」的任务，让下一期出现。

## 规则与规范

- **任务标题格式：`<emoji><昵称>｜HH:MM｜事项`**。中间写**活动实际时间**，不是提醒/due 时间。例：「👧小鹿｜18:30｜乐读」「🦌小鹿｜16:10｜放学」「👦🏻小豆丁｜16:45｜足球」。这样中午 12:00 提醒接送时，负责人仍能一眼看到真正放学点。
- **接送任务 due 设当天 12:00**，中午就提醒「今天谁去接」；真正放学时间只写在标题中间那一截。
- **提醒**：日历 `minutes=0`、任务 `relative_fire_minute=0`，都表示到点提醒。
- **临时事项**也走双模式。老师发来的周通知（图片/文字），提取要准备的东西：周日 19:00 提醒准备本周事项；写明了具体某天的，提前一天 19:00 再提醒。

## 常见坑

1. **家人看不到日历/清单**：没做共享。日历用 ACL 加 writer/reader；清单要加为协作成员（editor），只当执行人时清单视图显示不全。另检查应用可见范围、是否已发布版本。
2. **周一到周五的周期任务只看到一天**：飞书周期任务只显示当前/下一期实例。解决：按星期拆成 5 条、每条只有一个 BYDAY（脚本 `--byday` 自动处理）。
3. **下一期不出现**：周期任务要被「完成」才生成下一期，所以需要 23:00 的 `complete-today`。它只处理当天，不碰其他日期。
4. **任务重复**：别让两个程序/两个人同时往一个清单批量导入。导完跑 `list --tasklist <guid>`，按「标题+规则」核对重复。
5. **批量删除/重建**：先 `list` 列出，确认后再删，删完再 `list` 确认数量为 0。

## FAQ

**Q：家人一定要在同一个飞书组织里吗？**  
A：自建应用的 open_id 和可见范围基于本组织。最简单是建一个家庭飞书团队，把家人都拉进来。

**Q：爷爷奶奶不会用任务怎么办？**  
A：只需要看飞书机器人/任务的提醒消息，点「完成」即可；不点也没关系，23:00 会自动滚动。

**Q：Lark 国际版能用吗？**  
A：设置 `FEISHU_BASE=https://open.larksuite.com`。

**Q：放学时间改了？**  
A：删掉对应那一天的任务，用新标题（人物｜新时间｜放学）重建；其他天不受影响——这也是按天拆分的好处。

## 目录

```
README.md               本文档
SKILL.md                给 AI 助手用的 skill 说明
scripts/feishu_family.py 单文件命令行工具（Python 标准库）
examples/               示例家庭配置、crontab
```

## 免责声明

本项目非飞书官方出品，接口以飞书开放平台文档为准，可能随官方更新而变化。请妥善保管 App Secret，因使用本项目造成的任何损失由使用者自行承担。许可证：MIT。

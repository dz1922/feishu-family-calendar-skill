#!/usr/bin/env python3
"""飞书家庭日程小工具（仅标准库）。

凭证从环境变量读取：FEISHU_APP_ID / FEISHU_APP_SECRET。
成员一律用 open_id 指定，由使用者自行填写。
"""
import argparse
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("FEISHU_BASE", "https://open.feishu.cn")  # Lark 国际版改为 https://open.larksuite.com
TZ_NAME = "Asia/Shanghai"
TZ = dt.timezone(dt.timedelta(hours=8))
DAYS = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]


def die(msg):
    print("错误：" + msg, file=sys.stderr)
    sys.exit(1)


def http(method, path, body=None, token=None, query=None):
    url = BASE + path
    if query:
        url += "?" + urllib.parse.urlencode(query)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json; charset=utf-8")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            res = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        res = json.loads(e.read().decode() or "{}")
    if res.get("code", 0) != 0:
        die("%s %s -> code=%s msg=%s" % (method, path, res.get("code"), res.get("msg")))
    return res


def get_token():
    app_id = os.environ.get("FEISHU_APP_ID")
    secret = os.environ.get("FEISHU_APP_SECRET")
    if not app_id or not secret:
        die("请先设置环境变量 FEISHU_APP_ID / FEISHU_APP_SECRET")
    res = http("POST", "/open-apis/auth/v3/tenant_access_token/internal",
               {"app_id": app_id, "app_secret": secret})
    return res["tenant_access_token"]


def ts(date_str, time_str):
    d = dt.datetime.strptime(date_str + " " + time_str, "%Y-%m-%d %H:%M").replace(tzinfo=TZ)
    return int(d.timestamp())


def next_date_for(day_code, start=None):
    start = start or dt.datetime.now(TZ).date()
    delta = (DAYS.index(day_code) - start.weekday()) % 7
    return (start + dt.timedelta(days=delta)).isoformat()


OID = {"user_id_type": "open_id"}


# ---------- 子命令 ----------
def cmd_token(a):
    t = get_token()
    print("token 正常，前缀：%s..." % t[:6])


def cmd_create_calendar(a):
    res = http("POST", "/open-apis/calendar/v4/calendars",
               {"summary": a.name, "description": a.desc or "", "permissions": "private"}, get_token())
    print("日历已创建，calendar_id =", res["data"]["calendar"]["calendar_id"])


def cmd_share_calendar(a):
    t = get_token()
    for oid in a.open_id:
        http("POST", "/open-apis/calendar/v4/calendars/%s/acls" % a.calendar,
             {"role": a.role, "scope": {"type": "user", "user_id": oid}}, t, OID)
        print("已共享（%s）给 %s" % (a.role, oid))
    print("提示：家人需在飞书日历里刷新或接受共享。")


def members(ids, role):
    return [{"id": i, "type": "user", "role": role} for i in ids]


def cmd_create_tasklist(a):
    body = {"name": a.name}
    if a.editor:
        body["members"] = members(a.editor, "editor")
    res = http("POST", "/open-apis/task/v2/tasklists", body, get_token(), OID)
    print("清单已创建，tasklist_guid =", res["data"]["tasklist"]["guid"])


def cmd_share_tasklist(a):
    http("POST", "/open-apis/task/v2/tasklists/%s/add_members" % a.tasklist,
         {"members": members(a.open_id, a.role)}, get_token(), OID)
    print("已把 %d 位家人加为清单 %s" % (len(a.open_id), a.role))


def cmd_add_event(a):
    body = {
        "summary": a.title,
        "description": a.desc or "",
        "start_time": {"timestamp": str(ts(a.date, a.start)), "timezone": TZ_NAME},
        "end_time": {"timestamp": str(ts(a.date, a.end)), "timezone": TZ_NAME},
        "reminders": [{"minutes": m} for m in a.remind],
    }
    if a.rrule:
        body["recurrence"] = a.rrule
    if a.dry_run:
        print(json.dumps(body, ensure_ascii=False, indent=2)); return
    res = http("POST", "/open-apis/calendar/v4/calendars/%s/events" % a.calendar, body, get_token())
    print("事件已创建：", a.title, res["data"]["event"]["event_id"])


def cmd_add_task(a):
    """--byday 多天时按天拆成多条，每条 weekly 只含一天（飞书只显示下一期）。"""
    if a.byday:
        days = [d.strip().upper() for d in a.byday.split(",") if d.strip()]
        for d in days:
            if d not in DAYS:
                die("非法星期：" + d)
        plans = [(next_date_for(d), "FREQ=WEEKLY;INTERVAL=1;BYDAY=" + d) for d in days]
    else:
        if not a.date:
            die("一次性任务需要 --date，周期任务需要 --byday")
        plans = [(a.date, None)]
    t = None if a.dry_run else get_token()
    for date, rule in plans:
        body = {
            "summary": a.title,
            "description": a.desc or "",
            "due": {"timestamp": str(ts(date, a.due_time) * 1000), "is_all_day": False},
            "reminders": [{"relative_fire_minute": a.remind}],
            "members": members(a.assignee or [], "assignee"),
            "tasklists": [{"tasklist_guid": a.tasklist}],
        }
        if rule:
            body["repeat_rule"] = rule
        if a.dry_run:
            print(json.dumps(body, ensure_ascii=False)); continue
        res = http("POST", "/open-apis/task/v2/tasks", body, t, OID)
        print("任务已创建：%s %s %s" % (a.title, rule or date, res["data"]["task"]["guid"]))


def iter_tasks(t, tasklist, completed=None):
    token = None
    while True:
        q = {"page_size": 100, "user_id_type": "open_id"}
        if completed is not None:
            q["completed"] = "true" if completed else "false"
        if token:
            q["page_token"] = token
        d = http("GET", "/open-apis/task/v2/tasklists/%s/tasks" % tasklist, None, t, q)["data"]
        for it in d.get("items", []):
            yield it
        if not d.get("has_more"):
            break
        token = d.get("page_token")


def task_detail(t, guid):
    return http("GET", "/open-apis/task/v2/tasks/%s" % guid, None, t, OID)["data"]["task"]


def cmd_complete_today(a):
    """只勾掉「今天到期且未完成」的任务，其他日期一概不碰。"""
    t = get_token()
    today = dt.datetime.now(TZ).date()
    n = 0
    for it in iter_tasks(t, a.tasklist, completed=False):
        task = task_detail(t, it["guid"])
        due = (task.get("due") or {}).get("timestamp")
        if not due:
            continue
        due_date = dt.datetime.fromtimestamp(int(due) / 1000, TZ).date()
        if due_date != today:
            continue
        if a.dry_run:
            print("[dry-run] 将完成：", task.get("summary")); n += 1; continue
        now_ms = str(int(dt.datetime.now(TZ).timestamp() * 1000))
        http("PATCH", "/open-apis/task/v2/tasks/%s" % it["guid"],
             {"task": {"completed_at": now_ms}, "update_fields": ["completed_at"]}, t, OID)
        print("已完成：", task.get("summary"))
        n += 1
    print("今天（%s）共处理 %d 条。" % (today, n))


def cmd_list(a):
    t = get_token()
    if a.tasklist:
        seen = {}
        for it in iter_tasks(t, a.tasklist, completed=False):
            task = task_detail(t, it["guid"])
            rule = task.get("repeat_rule", "")
            key = (task.get("summary"), rule)
            seen[key] = seen.get(key, 0) + 1
            print("%s\t%s\t%s" % (task.get("summary"), rule or "-", it["guid"]))
        dups = [k for k, v in seen.items() if v > 1]
        print("共 %d 条；重复（标题+规则）%d 组%s" % (sum(seen.values()), len(dups),
              "：" + str(dups) if dups else ""))
    if a.calendar:
        now = int(dt.datetime.now(TZ).timestamp())
        q = {"start_time": str(now - 86400), "end_time": str(now + 14 * 86400), "page_size": 100}
        d = http("GET", "/open-apis/calendar/v4/calendars/%s/events" % a.calendar, None, t, q)["data"]
        items = d.get("items", [])
        for e in items:
            print("%s\t%s\t%s" % (e.get("summary"), e.get("recurrence") or "-", e.get("event_id")))
        print("日历事件 %d 条" % len(items))


def main():
    p = argparse.ArgumentParser(description="飞书家庭日程：日历 + 任务 双模式")
    s = p.add_subparsers(dest="cmd", required=True)

    s.add_parser("token", help="自检凭证").set_defaults(f=cmd_token)

    x = s.add_parser("create-calendar"); x.add_argument("--name", default="孩子们")
    x.add_argument("--desc"); x.set_defaults(f=cmd_create_calendar)

    x = s.add_parser("share-calendar"); x.add_argument("--calendar", required=True)
    x.add_argument("--open-id", nargs="+", required=True)
    x.add_argument("--role", default="writer", choices=["reader", "writer", "owner", "free_busy_reader"])
    x.set_defaults(f=cmd_share_calendar)

    x = s.add_parser("create-tasklist"); x.add_argument("--name", default="孩子们")
    x.add_argument("--editor", nargs="*", help="创建时即加为协作者的 open_id")
    x.set_defaults(f=cmd_create_tasklist)

    x = s.add_parser("share-tasklist"); x.add_argument("--tasklist", required=True)
    x.add_argument("--open-id", nargs="+", required=True)
    x.add_argument("--role", default="editor", choices=["editor", "viewer"])
    x.set_defaults(f=cmd_share_tasklist)

    x = s.add_parser("add-event"); x.add_argument("--calendar", required=True)
    x.add_argument("--title", required=True); x.add_argument("--date", required=True, help="YYYY-MM-DD（首次日期）")
    x.add_argument("--start", required=True, help="HH:MM"); x.add_argument("--end", required=True)
    x.add_argument("--rrule", help="如 FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR")
    x.add_argument("--remind", type=int, nargs="*", default=[0], help="提前分钟，0=开始时")
    x.add_argument("--desc"); x.add_argument("--dry-run", action="store_true")
    x.set_defaults(f=cmd_add_event)

    x = s.add_parser("add-task"); x.add_argument("--tasklist", required=True)
    x.add_argument("--title", required=True)
    x.add_argument("--byday", help="MO,TU,... 多天会自动拆成每天一条 weekly 任务")
    x.add_argument("--date", help="一次性任务的日期 YYYY-MM-DD")
    x.add_argument("--due-time", default="12:00", help="HH:MM，接送类建议 12:00")
    x.add_argument("--assignee", nargs="*", help="执行人 open_id，可多个")
    x.add_argument("--remind", type=int, default=0, help="relative_fire_minute，0=到期时")
    x.add_argument("--desc"); x.add_argument("--dry-run", action="store_true")
    x.set_defaults(f=cmd_add_task)

    x = s.add_parser("complete-today"); x.add_argument("--tasklist", required=True)
    x.add_argument("--dry-run", action="store_true"); x.set_defaults(f=cmd_complete_today)

    x = s.add_parser("list"); x.add_argument("--tasklist"); x.add_argument("--calendar")
    x.set_defaults(f=cmd_list)

    a = p.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
import pandas as pd
import streamlit as st
import plotly.express as px
from pathlib import Path

SUMMARY_DIR = Path("summary")

st.set_page_config(page_title="楽園柏 分析UI", layout="wide")
st.title("楽園柏 分析UI")

def load_csv(name):
    p = SUMMARY_DIR / name
    if not p.exists():
        st.warning(f"ファイルなし: {name}")
        return pd.DataFrame()
    return pd.read_csv(p, encoding="utf-8-sig")

def num(sr):
    return pd.to_numeric(
        sr.astype(str)
          .str.replace("%", "", regex=False)
          .str.replace(",", "", regex=False)
          .str.strip(),
        errors="coerce"
    )

def full_zorome(n):
    s = str(int(n))
    return len(s) >= 2 and len(set(s)) == 1

def machine_rate(total_diff, total_g):
    total_in = total_g * 3
    if total_in == 0:
        return None
    return (total_diff + total_in) / total_in * 100

def prep_all_units(df):
    if df.empty:
        return df

    df = df.copy()

    for c in ["差枚", "G数", "出率", "台番"]:
        if c in df.columns:
            df[c] = num(df[c])

    df = df[df["台番"].notna()].copy()
    df["台番"] = df["台番"].astype(int)

    df["日付"] = pd.to_datetime(df["日付"])
    df["年月"] = df["日付"].dt.strftime("%Y-%m")
    df["週"] = df["日付"].dt.strftime("%Y-W%U")
    df["日"] = df["日付"].dt.day

    weekday_map = {0: "月", 1: "火", 2: "水", 3: "木", 4: "金", 5: "土", 6: "日"}
    df["曜日"] = df["日付"].dt.weekday.map(weekday_map)

    df["末尾"] = df["台番"] % 10
    df["下二桁"] = df["台番"] % 100
    df["下二桁ゾロ目"] = ((df["下二桁"] // 10) == (df["下二桁"] % 10))
    df["完全ゾロ目"] = df["台番"].apply(full_zorome)
    df["プラス"] = df["差枚"] > 0
    df["投入枚数"] = df["G数"] * 3

    return df

def aggregate(df, group_cols):
    if df.empty:
        return pd.DataFrame()

    if not group_cols:
        total_diff = df["差枚"].sum()
        total_g = df["G数"].sum()
        total_in = df["投入枚数"].sum()
        count = df["台番"].count()
        plus_count = df["プラス"].sum()
        days = df["日付"].nunique()

        rate = ((total_diff + total_in) / total_in * 100) if total_in != 0 else None
        plus_rate = (plus_count / count * 100) if count != 0 else None

        return pd.DataFrame([{
            "総差枚": int(round(total_diff)),
            "総G数": total_g,
            "総投入枚数": total_in,
            "台数": count,
            "プラス台数": plus_count,
            "集計日数": days,
            "機械割(%)": round(rate, 2) if rate is not None else None,
            "プラス台率(%)": round(plus_rate, 1) if plus_rate is not None else None,
        }])

    g = (
        df.groupby(group_cols, as_index=False)
        .agg(
            総差枚=("差枚", "sum"),
            総G数=("G数", "sum"),
            総投入枚数=("投入枚数", "sum"),
            台数=("台番", "count"),
            プラス台数=("プラス", "sum"),
            集計日数=("日付", "nunique"),
        )
    )

    g["機械割(%)"] = ((g["総差枚"] + g["総投入枚数"]) / g["総投入枚数"] * 100).round(2)
    g["プラス台率(%)"] = (g["プラス台数"] / g["台数"] * 100).round(1)
    g["総差枚"] = g["総差枚"].round(0).astype(int)

    return g.sort_values(["機械割(%)", "総差枚"], ascending=False)

def day_comment(df_day):
    if df_day.empty:
        return "この日のデータがありません。"

    total_diff = int(df_day["差枚"].sum())
    total_g = int(df_day["G数"].sum())
    rate = machine_rate(total_diff, total_g)
    plus_rate = round((df_day["差枚"] > 0).mean() * 100, 1)

    top_m = aggregate(df_day, ["機種"]).head(5)
    top_s = aggregate(df_day, ["末尾"]).head(3)
    double = df_day[df_day["下二桁ゾロ目"]]
    full = df_day[df_day["完全ゾロ目"]]

    rate_text = f"{rate:.2f}%" if rate is not None else "-"
    lines = [f"総差枚は **{total_diff:,}枚**、機械割は **{rate_text}**、プラス台率は **{plus_rate}%** です。"]

    if total_diff > 0:
        lines.append("店全体はプラス寄り。全体配分が強い日です。")
    else:
        lines.append("店全体はマイナス寄り。全体狙いより、機種・末尾・ゾロ目など局所狙い向きです。")

    if not top_s.empty:
        s = " / ".join([f"末尾{int(r['末尾'])}: {int(r['総差枚']):,}枚" for _, r in top_s.iterrows()])
        lines.append(f"強かった末尾は **{s}** です。")

    if not top_m.empty:
        m = " / ".join([f"{r['機種']}({int(r['総差枚']):,}枚)" for _, r in top_m.iterrows()])
        lines.append(f"強かった機種は **{m}** です。")

    if not double.empty:
        lines.append(f"下二桁ゾロ目の合計差枚は **{int(double['差枚'].sum()):,}枚**。")

    if not full.empty:
        lines.append(f"完全ゾロ目の合計差枚は **{int(full['差枚'].sum()):,}枚**。")

    return "\n\n".join(lines)

all_units = prep_all_units(load_csv("rakuen_kashiwa_all_units_merged.csv"))

if all_units.empty:
    st.error("all_units データがありません。summaryフォルダを確認してください。")
    st.stop()

tabs = st.tabs([
    "機種ランキング",
    "末尾・ゾロ目",
    "機種×末尾クロス",
    "各台カルテ",
    "曜日分析",
    "月別分析",
    "週別分析",
    "月またぎ同日比較",
    "ヒートマップ",
    "全台検索",
    "その日の傾向",
    "朝イチ用",
])

with tabs[0]:
    st.header("機種ランキング")
    min_days = st.slider("最低集計日数", 1, int(all_units["日付"].nunique()), 1, key="machine_days")
    df = aggregate(all_units, ["機種"])
    df = df[df["集計日数"] >= min_days]
    st.dataframe(df, use_container_width=True, hide_index=True)

with tabs[1]:
    st.header("末尾・ゾロ目ランキング")

    st.subheader("一桁末尾")
    st.dataframe(aggregate(all_units, ["末尾"]), use_container_width=True, hide_index=True)

    st.subheader("下二桁ゾロ目：00 / 11 / 22 / 33 ...")
    st.dataframe(aggregate(all_units[all_units["下二桁ゾロ目"]], ["下二桁"]), use_container_width=True, hide_index=True)

    st.subheader("完全ゾロ目：111 / 222 / 333 ...")
    st.dataframe(aggregate(all_units[all_units["完全ゾロ目"]], ["台番"]), use_container_width=True, hide_index=True)

    st.subheader("カテゴリ比較")
    cat_rows = []
    for name, sub in [
        ("通常台", all_units[~all_units["下二桁ゾロ目"]]),
        ("下二桁ゾロ目", all_units[all_units["下二桁ゾロ目"]]),
        ("完全ゾロ目", all_units[all_units["完全ゾロ目"]]),
    ]:
        a = aggregate(sub, [])
        if not a.empty:
            row = a.iloc[0].to_dict()
            row["カテゴリ"] = name
            cat_rows.append(row)

    if cat_rows:
        cat = pd.DataFrame(cat_rows)
        cat = cat[["カテゴリ", "総差枚", "機械割(%)", "プラス台率(%)", "台数", "集計日数"]]
        st.dataframe(cat, use_container_width=True, hide_index=True)

with tabs[2]:
    st.header("機種×末尾クロス分析")

    min_count = st.slider("最低台数", 1, 100, 5, key="cross_count")

    st.subheader("機種×一桁末尾")
    cross = aggregate(all_units, ["機種", "末尾"])
    cross = cross[cross["台数"] >= min_count]
    st.dataframe(cross, use_container_width=True, hide_index=True)

    st.subheader("機種×下二桁ゾロ目")
    cross_double = aggregate(all_units[all_units["下二桁ゾロ目"]], ["機種", "下二桁"])
    st.dataframe(cross_double, use_container_width=True, hide_index=True)

    st.subheader("機種×完全ゾロ目")
    cross_full = aggregate(all_units[all_units["完全ゾロ目"]], ["機種", "台番"])
    st.dataframe(cross_full, use_container_width=True, hide_index=True)

with tabs[3]:
    st.header("各台カルテ")

    machine_list = ["全機種"] + sorted(all_units["機種"].dropna().unique().tolist())
    selected_machine = st.selectbox("機種で絞り込み", machine_list)

    view = all_units.copy()
    if selected_machine != "全機種":
        view = view[view["機種"] == selected_machine]

    unit_stats = aggregate(view, ["台番", "機種", "末尾"])
    if not unit_stats.empty:
        unit_stats["平均差枚"] = (unit_stats["総差枚"] / unit_stats["台数"]).round(1)
        unit_stats = unit_stats.sort_values(["機械割(%)", "総差枚"], ascending=False)

    st.subheader("台番別ランキング")
    st.dataframe(unit_stats, use_container_width=True, hide_index=True)

    st.subheader("台番カルテ")
    selected_unit = st.selectbox("台番を選択", sorted(view["台番"].unique().tolist()))
    hist = view[view["台番"] == selected_unit].sort_values("日付")

    total_diff = int(hist["差枚"].sum())
    avg_diff = round(hist["差枚"].mean(), 1)
    win_rate = round((hist["差枚"] > 0).mean() * 100, 1)
    total_g = int(hist["G数"].sum())
    rate = machine_rate(total_diff, total_g)
    max_win = int(hist["差枚"].max())
    max_lose = int(hist["差枚"].min())

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("総差枚", f"{total_diff:,}枚")
    c2.metric("平均差枚", f"{avg_diff:,}枚")
    c3.metric("勝率", f"{win_rate}%")
    c4.metric("機械割", f"{rate:.2f}%" if rate is not None else "-")
    c5.metric("最大勝ち", f"{max_win:,}枚")
    c6.metric("最大負け", f"{max_lose:,}枚")

    st.subheader("日別履歴")
    st.dataframe(
        hist.sort_values("日付", ascending=False)[
            ["日付", "曜日", "機種", "台番", "差枚", "G数", "出率", "末尾", "下二桁ゾロ目", "完全ゾロ目"]
        ],
        use_container_width=True,
        hide_index=True
    )

    st.subheader("曜日別カルテ")
    st.dataframe(aggregate(hist, ["曜日"]), use_container_width=True, hide_index=True)

    st.subheader("月別カルテ")
    st.dataframe(aggregate(hist, ["年月"]), use_container_width=True, hide_index=True)

    st.subheader("特定日カルテ")
    special_days = hist[hist["日"].isin([7, 17, 22, 27])].copy()
    st.dataframe(aggregate(special_days, ["日"]), use_container_width=True, hide_index=True)

    st.subheader("台番推移グラフ")
    chart = hist.copy()
    chart["日付_str"] = chart["日付"].dt.strftime("%Y-%m-%d")
    fig = px.bar(
        chart,
        x="日付_str",
        y="差枚",
        color="差枚",
        color_continuous_scale="RdBu_r",
        title=f"台番 {selected_unit} 日別差枚"
    )
    st.plotly_chart(fig, use_container_width=True)

with tabs[4]:
    st.header("曜日分析")
    st.subheader("曜日別 全体")
    st.dataframe(aggregate(all_units, ["曜日"]), use_container_width=True, hide_index=True)

    st.subheader("曜日×末尾")
    st.dataframe(aggregate(all_units, ["曜日", "末尾"]), use_container_width=True, hide_index=True)

    st.subheader("曜日×機種")
    st.dataframe(aggregate(all_units, ["曜日", "機種"]), use_container_width=True, hide_index=True)

with tabs[5]:
    st.header("月別分析")
    st.subheader("月別 全体")
    st.dataframe(aggregate(all_units, ["年月"]), use_container_width=True, hide_index=True)

    st.subheader("月別×機種")
    st.dataframe(aggregate(all_units, ["年月", "機種"]), use_container_width=True, hide_index=True)

    st.subheader("月別×末尾")
    st.dataframe(aggregate(all_units, ["年月", "末尾"]), use_container_width=True, hide_index=True)

with tabs[6]:
    st.header("週別分析")
    st.subheader("週別 全体")
    st.dataframe(aggregate(all_units, ["週"]), use_container_width=True, hide_index=True)

    st.subheader("週別×機種")
    st.dataframe(aggregate(all_units, ["週", "機種"]), use_container_width=True, hide_index=True)

    st.subheader("週別×末尾")
    st.dataframe(aggregate(all_units, ["週", "末尾"]), use_container_width=True, hide_index=True)

with tabs[7]:
    st.header("月またぎ同日比較")

    day_text = st.text_input("比較したい日付（日） 例: 22 または 7,17,22,27", "22")

    days = []
    for x in day_text.split(","):
        x = x.strip()
        if x.isdigit():
            days.append(int(x))

    target = all_units[all_units["日"].isin(days)].copy()

    st.subheader("対象日 全体")
    st.dataframe(aggregate(target, ["日付"]), use_container_width=True, hide_index=True)

    st.subheader("対象日×機種")
    st.dataframe(aggregate(target, ["日付", "機種"]), use_container_width=True, hide_index=True)

    st.subheader("対象日×末尾")
    st.dataframe(aggregate(target, ["日付", "末尾"]), use_container_width=True, hide_index=True)

    st.subheader("対象日×下二桁ゾロ目")
    st.dataframe(aggregate(target[target["下二桁ゾロ目"]], ["日付", "下二桁"]), use_container_width=True, hide_index=True)

    st.subheader("対象日×完全ゾロ目")
    st.dataframe(aggregate(target[target["完全ゾロ目"]], ["日付", "台番"]), use_container_width=True, hide_index=True)

with tabs[8]:
    st.header("ヒートマップ")

    heat_type = st.selectbox(
        "表示するヒートマップ",
        [
            "日付×末尾",
            "曜日×末尾",
            "月×末尾",
            "週×末尾",
            "機種×末尾",
            "機種×曜日",
            "日付×台番",
            "月×台番",
        ]
    )

    view = all_units.copy()

    if heat_type in ["日付×台番", "月×台番"]:
        st.caption("台番ヒートマップは重くなるので、必要なら機種で絞ってください。")
        machines = ["全機種"] + sorted(view["機種"].dropna().unique().tolist())
        selected_machine = st.selectbox("機種で絞り込み", machines, key="heat_machine")
        if selected_machine != "全機種":
            view = view[view["機種"] == selected_machine]

    if heat_type == "日付×末尾":
        pivot = view.pivot_table(index="日付", columns="末尾", values="差枚", aggfunc="sum", fill_value=0)
    elif heat_type == "曜日×末尾":
        pivot = view.pivot_table(index="曜日", columns="末尾", values="差枚", aggfunc="sum", fill_value=0)
    elif heat_type == "月×末尾":
        pivot = view.pivot_table(index="年月", columns="末尾", values="差枚", aggfunc="sum", fill_value=0)
    elif heat_type == "週×末尾":
        pivot = view.pivot_table(index="週", columns="末尾", values="差枚", aggfunc="sum", fill_value=0)
    elif heat_type == "機種×末尾":
        top_machines = aggregate(view, ["機種"]).head(40)["機種"].tolist()
        sub = view[view["機種"].isin(top_machines)]
        pivot = sub.pivot_table(index="機種", columns="末尾", values="差枚", aggfunc="sum", fill_value=0)
    elif heat_type == "機種×曜日":
        top_machines = aggregate(view, ["機種"]).head(40)["機種"].tolist()
        sub = view[view["機種"].isin(top_machines)]
        pivot = sub.pivot_table(index="機種", columns="曜日", values="差枚", aggfunc="sum", fill_value=0)
    elif heat_type == "日付×台番":
        pivot = view.pivot_table(index="日付", columns="台番", values="差枚", aggfunc="sum", fill_value=0)
    else:
        pivot = view.pivot_table(index="年月", columns="台番", values="差枚", aggfunc="sum", fill_value=0)

    fig = px.imshow(
        pivot,
        aspect="auto",
        text_auto=False,
        title=heat_type,
        color_continuous_scale="RdBu_r"
    )
    fig.update_layout(height=800)
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("元データ")
    st.dataframe(pivot, use_container_width=True)

with tabs[9]:
    st.header("全台検索")

    view = all_units.copy()

    dates = ["全期間"] + [d.strftime("%Y-%m-%d") for d in sorted(view["日付"].dropna().unique())]
    selected_date = st.selectbox("日付", dates)

    if selected_date != "全期間":
        view = view[view["日付"] == pd.to_datetime(selected_date)]

    machines = sorted(view["機種"].dropna().unique())
    selected_machines = st.multiselect("機種", machines)
    if selected_machines:
        view = view[view["機種"].isin(selected_machines)]

    suffixes = sorted(view["末尾"].dropna().unique())
    selected_suffix = st.multiselect("末尾", suffixes)
    if selected_suffix:
        view = view[view["末尾"].isin(selected_suffix)]

    c1, c2 = st.columns(2)
    with c1:
        if st.checkbox("下二桁ゾロ目だけ"):
            view = view[view["下二桁ゾロ目"]]
    with c2:
        if st.checkbox("完全ゾロ目だけ"):
            view = view[view["完全ゾロ目"]]

    keyword = st.text_input("台番検索")
    if keyword:
        view = view[view["台番"].astype(str).str.contains(keyword)]

    view = view.sort_values(["差枚", "出率", "G数"], ascending=False)

    st.dataframe(
        view[["日付", "曜日", "機種", "台番", "末尾", "下二桁", "下二桁ゾロ目", "完全ゾロ目", "差枚", "G数", "出率"]],
        use_container_width=True,
        hide_index=True
    )

with tabs[10]:
    st.header("その日の傾向")

    date_list = [d.strftime("%Y-%m-%d") for d in sorted(all_units["日付"].dropna().unique())]
    selected = st.selectbox("日付", date_list, index=len(date_list)-1)

    df_day = all_units[all_units["日付"] == pd.to_datetime(selected)]

    st.markdown(day_comment(df_day))

    st.subheader("この日の強い台 TOP50")
    st.dataframe(
        df_day.sort_values(["差枚", "出率"], ascending=False)
        [["日付", "曜日", "機種", "台番", "末尾", "下二桁", "下二桁ゾロ目", "完全ゾロ目", "差枚", "G数", "出率"]]
        .head(50),
        use_container_width=True,
        hide_index=True
    )

with tabs[11]:
    st.header("朝イチ用")

    st.subheader("強機種 TOP20")
    st.dataframe(aggregate(all_units, ["機種"]).head(20), use_container_width=True, hide_index=True)

    st.subheader("強末尾 TOP10")
    st.dataframe(aggregate(all_units, ["末尾"]).head(10), use_container_width=True, hide_index=True)

    st.subheader("機種×末尾 本命候補 TOP50")
    st.dataframe(aggregate(all_units, ["機種", "末尾"]).head(50), use_container_width=True, hide_index=True)

    st.subheader("下二桁ゾロ目 本命候補")
    st.dataframe(aggregate(all_units[all_units["下二桁ゾロ目"]], ["下二桁"]).head(20), use_container_width=True, hide_index=True)

    st.subheader("完全ゾロ目 本命候補")
    st.dataframe(aggregate(all_units[all_units["完全ゾロ目"]], ["台番"]).head(20), use_container_width=True, hide_index=True)
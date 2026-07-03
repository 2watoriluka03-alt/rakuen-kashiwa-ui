# -*- coding: utf-8 -*-
import pandas as pd
import streamlit as st
from pathlib import Path

SUMMARY_DIR = Path("summary")

st.set_page_config(page_title="楽園柏 分析UI", layout="wide")
st.title("楽園柏 分析UI")


def load_csv(name):
    p = SUMMARY_DIR / name
    if not p.exists():
        st.error(f"{name} がありません")
        st.stop()
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
    df = df.copy()

    for c in ["差枚", "G数", "出率", "台番"]:
        df[c] = num(df[c])

    df = df[df["台番"].notna()].copy()
    df["台番"] = df["台番"].astype(int)

    df["日付"] = pd.to_datetime(df["日付"])
    df["年月"] = df["日付"].dt.strftime("%Y-%m")
    df["週"] = df["日付"].dt.strftime("%Y-W%U")
    df["日"] = df["日付"].dt.day

    weekday_map = {
        0: "月", 1: "火", 2: "水",
        3: "木", 4: "金", 5: "土", 6: "日"
    }
    df["曜日"] = df["日付"].dt.weekday.map(weekday_map)

    df["末尾"] = df["台番"] % 10
    df["下二桁"] = df["台番"] % 100
    df["下二桁ゾロ目"] = (
        (df["下二桁"] // 10) == (df["下二桁"] % 10)
    )
    df["完全ゾロ目"] = df["台番"].apply(full_zorome)
    df["プラス"] = df["差枚"] > 0
    df["投入枚数"] = df["G数"] * 3

    return df


def aggregate(df, group_cols):
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

    g["機械割(%)"] = (
        (g["総差枚"] + g["総投入枚数"]) /
        g["総投入枚数"] * 100
    ).round(2)

    g["プラス台率(%)"] = (
        g["プラス台数"] / g["台数"] * 100
    ).round(1)

    g["総差枚"] = g["総差枚"].round(0).astype(int)

    return g


def stat_cards(items):
    cols = st.columns(2)

    for i, (label, value) in enumerate(items):
        with cols[i % 2]:
            st.markdown(
                f"""
                <div style="
                    border:1px solid rgba(255,255,255,0.18);
                    border-radius:14px;
                    padding:14px 16px;
                    margin-bottom:12px;
                    background:#1f2937;
                    min-height:86px;
                ">
                    <div style="
                        font-size:15px;
                        color:#d1d5db;
                        margin-bottom:6px;
                    ">{label}</div>

                    <div style="
                        font-size:30px;
                        font-weight:800;
                        line-height:1.15;
                        color:#ffffff;
                    ">{value}</div>
                </div>
                """,
                unsafe_allow_html=True
            )


all_units = prep_all_units(
    load_csv("rakuen_kashiwa_all_units_merged.csv")
)

tabs = st.tabs([
    "各台カルテ",
    "機種全データ"
])

##################################################
# 各台カルテ
##################################################

with tabs[0]:
    st.header("台番カルテ")

    selected_unit = st.selectbox(
        "台番を選択",
        sorted(all_units["台番"].unique().tolist())
    )

    hist = all_units[
        all_units["台番"] == selected_unit
    ].sort_values("日付")

    total_diff = int(hist["差枚"].sum())
    avg_diff = round(hist["差枚"].mean(), 1)
    win_rate = round((hist["差枚"] > 0).mean() * 100, 2)

    total_g = int(hist["G数"].sum())
    rate = machine_rate(total_diff, total_g)

    max_win = int(hist["差枚"].max())
    max_lose = int(hist["差枚"].min())

    stat_cards([
        ("総差枚", f"{total_diff:,}枚"),
        ("平均差枚", f"{avg_diff:,}枚"),
        ("勝率", f"{win_rate:.2f}%"),
        ("機械割", f"{rate:.2f}%"),
        ("最大勝ち", f"{max_win:,}枚"),
        ("最大負け", f"{max_lose:,}枚"),
    ])

    st.subheader("日別履歴")

    hist_view = hist[
        [
            "日付",
            "曜日",
            "機種",
            "台番",
            "差枚",
            "G数",
            "出率",
            "末尾",
            "下二桁ゾロ目",
            "完全ゾロ目"
        ]
    ].sort_values("日付", ascending=False)

    st.dataframe(
        hist_view,
        use_container_width=True,
        hide_index=True,
        height=min(520, 80 + 38 * len(hist_view)),
        column_config={
            "日付": st.column_config.DatetimeColumn(
                "日付",
                format="YYYY-MM-DD"
            ),
            "差枚": st.column_config.NumberColumn(
                "差枚",
                format="%d枚"
            ),
            "G数": st.column_config.NumberColumn(
                "G数",
                format="%dG"
            ),
            "出率": st.column_config.NumberColumn(
                "出率",
                format="%.2f%%"
            ),
        }
    )

##################################################
# 機種全データ
##################################################

with tabs[1]:
    st.header("機種全データ")

    machine = st.selectbox(
        "機種を選択",
        sorted(all_units["機種"].dropna().unique().tolist())
    )

    view = all_units[
        all_units["機種"] == machine
    ].copy()

    day_text = st.text_input(
        "特定日だけ表示（例: 7,11,22）"
    )

    days = []
    for x in day_text.split(","):
        x = x.strip()
        if x.isdigit():
            days.append(int(x))

    if days:
        view = view[
            view["日"].isin(days)
        ]

    sort_col = st.selectbox(
        "並び替え",
        ["日付", "台番", "差枚", "G数", "出率", "末尾"]
    )

    sort_order = st.radio(
        "順番",
        ["降順", "昇順"],
        horizontal=True
    )

    view = view.sort_values(
        sort_col,
        ascending=(sort_order == "昇順")
    )

    st.dataframe(
        view[
            [
                "日付",
                "曜日",
                "機種",
                "台番",
                "末尾",
                "差枚",
                "G数",
                "出率",
                "下二桁",
                "下二桁ゾロ目",
                "完全ゾロ目"
            ]
        ],
        use_container_width=True,
        hide_index=True,
        height=700,
        column_config={
            "日付": st.column_config.DatetimeColumn(
                "日付",
                format="YYYY-MM-DD"
            ),
            "差枚": st.column_config.NumberColumn(
                "差枚",
                format="%d枚"
            ),
            "G数": st.column_config.NumberColumn(
                "G数",
                format="%dG"
            ),
            "出率": st.column_config.NumberColumn(
                "出率",
                format="%.2f%%"
            ),
        }
    )
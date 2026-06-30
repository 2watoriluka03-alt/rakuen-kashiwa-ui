# -*- coding: utf-8 -*-
import pandas as pd
import streamlit as st
from pathlib import Path

SUMMARY_DIR = Path("summary")

st.set_page_config(page_title="楽園柏 分析UI", layout="wide")
st.title("楽園柏 店舗データ分析UI")

def load_csv(name):
    path = SUMMARY_DIR / name
    if not path.exists():
        st.warning(f"ファイルなし: {name}")
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")

def num(sr):
    return pd.to_numeric(
        sr.astype(str).str.replace("%", "", regex=False).str.replace(",", "", regex=False),
        errors="coerce"
    )

def prep_all_units(df):
    if df.empty:
        return df

    df = df.copy()
    for c in ["差枚", "G数", "出率", "台番"]:
        if c in df.columns:
            df[c] = num(df[c])

    df = df[df["台番"].notna()].copy()
    df["台番"] = df["台番"].astype(int)
    df["末尾"] = df["台番"] % 10

    last2 = df["台番"] % 100
    df["下二桁"] = last2
    df["下二桁ゾロ目"] = (last2 // 10 == last2 % 10)

    df["完全ゾロ目"] = df["台番"].astype(str).apply(lambda s: len(s) >= 2 and len(set(s)) == 1)

    return df

def day_comment(df_day):
    if df_day.empty:
        return "この日のデータがありません。"

    total_diff = int(df_day["差枚"].sum())
    avg_rate = round(df_day["出率"].mean(), 2)
    total_g = int(df_day["G数"].sum())

    top_machines = (
        df_day.groupby("機種", as_index=False)
        .agg(総差枚=("差枚", "sum"), 平均出率=("出率", "mean"), 平均G数=("G数", "mean"))
        .sort_values(["総差枚", "平均出率"], ascending=False)
        .head(5)
    )

    suffix = (
        df_day.groupby("末尾", as_index=False)
        .agg(総差枚=("差枚", "sum"), 平均出率=("出率", "mean"))
        .sort_values(["総差枚", "平均出率"], ascending=False)
        .head(3)
    )

    double = df_day[df_day["下二桁ゾロ目"]]
    full = df_day[df_day["完全ゾロ目"]]

    lines = []
    lines.append(f"この日の総差枚は **{total_diff:,}枚**、平均出率は **{avg_rate}%**、総G数は **{total_g:,}G** です。")

    if total_diff > 0:
        lines.append("店全体はプラス寄りで、全体的に扱いが強い日です。")
    else:
        lines.append("店全体はマイナス寄りなので、全体狙いよりも機種・末尾・ゾロ目の局所狙いが向いています。")

    if not suffix.empty:
        s = " / ".join([f"末尾{int(r['末尾'])}: {int(r['総差枚']):,}枚" for _, r in suffix.iterrows()])
        lines.append(f"強かった末尾は **{s}** です。")

    if not top_machines.empty:
        m = " / ".join([f"{r['機種']}({int(r['総差枚']):,}枚)" for _, r in top_machines.iterrows()])
        lines.append(f"強かった機種は **{m}** です。")

    if not double.empty:
        lines.append(f"下二桁ゾロ目は合計 **{int(double['差枚'].sum()):,}枚**。")
    if not full.empty:
        lines.append(f"完全ゾロ目は合計 **{int(full['差枚'].sum()):,}枚**。")

    return "\n\n".join(lines)

machine = load_csv("rakuen_kashiwa_machine_total_stats.csv")
suffix = load_csv("rakuen_kashiwa_suffix_total_stats.csv")
double = load_csv("rakuen_kashiwa_double_suffix_stats.csv")
full = load_csv("rakuen_kashiwa_full_zorome_stats.csv")
special = load_csv("rakuen_kashiwa_special_number_stats.csv")
all_units = prep_all_units(load_csv("rakuen_kashiwa_all_units_merged.csv"))

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "機種ランキング",
    "末尾・ゾロ目ランキング",
    "ゾロ目分析",
    "全台検索",
    "その日の傾向"
])

with tab1:
    st.header("機種別 総差枚・機械割")
    if not machine.empty:
        st.dataframe(
            machine.sort_values(["機械割(%)", "総差枚"], ascending=False),
            use_container_width=True,
            hide_index=True
        )

with tab2:
    st.header("末尾・ゾロ目ランキング")

    st.subheader("一桁末尾ランキング")
    if not suffix.empty:
        st.dataframe(
            suffix.sort_values(["機械割(%)", "総差枚"], ascending=False),
            use_container_width=True,
            hide_index=True
        )

    st.subheader("下二桁ゾロ目ランキング：22 / 33 / 44 など")
    if not double.empty:
        st.dataframe(
            double.sort_values(["機械割(%)", "総差枚"], ascending=False),
            use_container_width=True,
            hide_index=True
        )

    st.subheader("完全ゾロ目ランキング：333 / 555 / 777 など")
    if not full.empty:
        st.dataframe(
            full.sort_values(["機械割(%)", "総差枚"], ascending=False),
            use_container_width=True,
            hide_index=True
        )

    st.subheader("特殊番号カテゴリ比較")
    if not special.empty:
        st.dataframe(
            special.sort_values(["機械割(%)", "総差枚"], ascending=False),
            use_container_width=True,
            hide_index=True
        )

with tab3:
    st.header("ゾロ目分析")
    st.write("下二桁ゾロ目と完全ゾロ目を個別に確認するタブです。")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("下二桁ゾロ目")
        if not double.empty:
            st.dataframe(double, use_container_width=True, hide_index=True)

    with col2:
        st.subheader("完全ゾロ目")
        if not full.empty:
            st.dataframe(full, use_container_width=True, hide_index=True)

with tab4:
    st.header("全台検索")
    st.caption("初期表示は、その日の強い台順＝差枚の高い順です。")

    if not all_units.empty:
        view = all_units.copy()

        dates = sorted(view["日付"].dropna().unique())
        selected_date = st.selectbox("日付", ["全期間"] + dates)

        if selected_date != "全期間":
            view = view[view["日付"] == selected_date]

        machines_list = sorted(view["機種"].dropna().unique())
        selected_machines = st.multiselect("機種で絞り込み", machines_list)

        if selected_machines:
            view = view[view["機種"].isin(selected_machines)]

        suffix_options = sorted(view["末尾"].dropna().unique())
        selected_suffix = st.multiselect("末尾で絞り込み", suffix_options)

        if selected_suffix:
            view = view[view["末尾"].isin(selected_suffix)]

        col_a, col_b = st.columns(2)

        with col_a:
            only_double = st.checkbox("下二桁ゾロ目だけ表示")
        with col_b:
            only_full = st.checkbox("完全ゾロ目だけ表示")

        if only_double:
            view = view[view["下二桁ゾロ目"]]
        if only_full:
            view = view[view["完全ゾロ目"]]

        keyword = st.text_input("台番検索")
        if keyword:
            view = view[view["台番"].astype(str).str.contains(keyword, na=False)]

        view = view.sort_values(["差枚", "出率", "G数"], ascending=False)

        show_cols = [
            "日付", "機種", "台番", "末尾", "下二桁", "下二桁ゾロ目",
            "完全ゾロ目", "差枚", "G数", "出率"
        ]
        show_cols = [c for c in show_cols if c in view.columns]

        st.dataframe(view[show_cols], use_container_width=True, hide_index=True)

with tab5:
    st.header("その日の傾向")

    if not all_units.empty:
        dates = sorted(all_units["日付"].dropna().unique())
        selected_day = st.selectbox("傾向を見る日付", dates, index=len(dates)-1)

        df_day = all_units[all_units["日付"] == selected_day].copy()
        df_day = df_day.sort_values(["差枚", "出率"], ascending=False)

        st.subheader(f"{selected_day} の傾向コメント")
        st.markdown(day_comment(df_day))

        st.subheader("この日の強い台 TOP30")
        show_cols = [
            "日付", "機種", "台番", "末尾", "下二桁", "下二桁ゾロ目",
            "完全ゾロ目", "差枚", "G数", "出率"
        ]
        show_cols = [c for c in show_cols if c in df_day.columns]

        st.dataframe(df_day[show_cols].head(30), use_container_width=True, hide_index=True)
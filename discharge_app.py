"""
退院先推移分析ダッシュボード
"""
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from discharge_data_loader import DischargeDataLoader
import pandas as pd


# ページ設定
st.set_page_config(
    page_title="退院先推移分析ダッシュボード",
    page_icon="🏥",
    layout="wide"
)

# カスタムCSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.5rem;
        font-weight: bold;
        color: #2c3e50;
        margin-top: 2rem;
        margin-bottom: 1rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource(ttl=3600)
def load_discharge_data():
    """データを読み込み（キャッシュ）"""
    loader = DischargeDataLoader()
    # 総患者数を先に読み込んでから処理（推定患者数の計算に使用）
    loader.load_data().load_los_data().process_data()
    return loader


def get_value_col(config: dict) -> str:
    """表示モードに応じた値の列名を返す"""
    return '推定患者数' if config["display_mode"] == "推定患者数（件）" else '割合'


def get_tickformat(config: dict) -> str:
    """表示モードに応じたグラフの軸フォーマットを返す"""
    return ",.0f" if config["display_mode"] == "推定患者数（件）" else ".1%"


def fmt_value(value, config: dict) -> str:
    """メトリクス表示用の値フォーマット"""
    if config["display_mode"] == "推定患者数（件）":
        return f"{int(value):,}件" if pd.notna(value) else "-"
    return f"{value:.1%}"


def render_sidebar(loader):
    """サイドバーUIのレンダリング"""
    st.sidebar.title("🏥 退院先分析")
    st.sidebar.markdown("---")

    # 表示モード切り替え（タイトル直下）
    display_mode = st.sidebar.radio(
        "📊 表示モード",
        ["割合（%）", "推定患者数（件）"],
        index=1  # デフォルト：推定患者数
    )

    st.sidebar.markdown("---")

    # 施設選択：デフォルトで4施設を選択
    facilities = loader.get_facility_list()
    default_keywords = ["信州医療センター", "長野赤十字病院", "長野市民病院", "北信総合病院"]
    default_facilities = [f for f in facilities if any(kw in f for kw in default_keywords)]
    selected_facilities = st.sidebar.multiselect(
        "📍 施設選択（複数可）",
        facilities,
        default=default_facilities
    )

    # 後方互換性のため、単一施設も保持
    selected_facility = selected_facilities[0] if selected_facilities else facilities[0]

    # 年度選択（複数選択に変更）
    years = loader.years
    selected_years = st.sidebar.multiselect(
        "📅 年度選択（複数可）",
        years,
        default=years  # デフォルトで全年度選択
    )

    # 後方互換性のため、単一年度も保持
    selected_year = selected_years[-1] if selected_years else years[-1]

    # 比較年度選択（年度間比較用）
    st.sidebar.markdown("### 年度間比較")
    col1, col2 = st.sidebar.columns(2)
    with col1:
        compare_year1 = st.selectbox("年度1", years, index=0)
    with col2:
        compare_year2 = st.selectbox("年度2", years, index=len(years) - 1)

    # 退院先カテゴリ選択（フラットリスト）
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📊 退院先カテゴリ")

    # 「家庭への退院（当院に通院）」はデフォルトOFF
    excluded_defaults = {"家庭への退院（当院に通院）", "家庭への退院（他院への通院）", "家庭への退院（その他）"}
    selected_destinations = []
    for dest in loader.destinations:
        default_value = dest not in excluded_defaults
        if st.sidebar.checkbox(dest, value=default_value, key=f"dest_{dest}"):
            selected_destinations.append(dest)

    return {
        "facility": selected_facility,
        "facilities": selected_facilities,
        "year": selected_year,
        "years": selected_years,
        "compare_year1": compare_year1,
        "compare_year2": compare_year2,
        "destinations": selected_destinations if selected_destinations else loader.destinations,
        "display_mode": display_mode
    }


def render_facility_analysis(loader, config):
    """タブ1: 施設別分析"""
    st.markdown('<div class="sub-header">📊 施設別退院先分析</div>', unsafe_allow_html=True)

    facilities = config["facilities"] if config["facilities"] else [config["facility"]]
    selected_years = config["years"] if config["years"] else [config["year"]]

    # 複数施設・複数年度の推移グラフ（メイン表示）
    st.markdown("#### 📈 退院先推移（全年度比較）")

    # 選択された施設と年度のデータを取得
    trend_data_list = []
    for facility in facilities:
        facility_data = loader.get_facility_data(facility)
        facility_data = facility_data[
            (facility_data['退院先'].isin(config["destinations"])) &
            (facility_data['年度'].isin(selected_years))
        ]
        trend_data_list.append(facility_data)

    value_col = get_value_col(config)
    tickfmt = get_tickformat(config)

    if trend_data_list:
        all_data = pd.concat(trend_data_list)

        # スタック棒グラフ（退院先の構成を一覧表示）
        st.markdown("#### 📊 退院先構成（スタック）")
        facet_col = '施設名' if len(facilities) > 1 else None
        facet_col_wrap = min(len(facilities), 2) if len(facilities) > 1 else None
        fig_stack = px.bar(
            all_data,
            x='年度',
            y=value_col,
            color='退院先',
            barmode='stack',
            facet_col=facet_col,
            facet_col_wrap=facet_col_wrap,
            title="退院先構成推移（スタック）",
            height=500 if len(facilities) <= 2 else 800
        )
        fig_stack.update_yaxes(tickformat=tickfmt)
        fig_stack.update_layout(hovermode='x unified')
        st.plotly_chart(fig_stack, use_container_width=True)

        st.markdown("---")

        # 施設が1つの場合は退院先で色分け、複数の場合は施設で色分け
        if len(facilities) == 1:
            # 単一施設：退院先で色分け
            fig_main = px.line(
                all_data,
                x='年度',
                y=value_col,
                color='退院先',
                markers=True,
                title=f"{facilities[0]} - 退院先推移"
            )
        else:
            # 複数施設：各退院先ごとにグラフを作成
            st.markdown("各退院先の施設間比較")

            for dest in config["destinations"]:
                dest_data = all_data[all_data['退院先'] == dest]
                if not dest_data.empty:
                    fig = px.line(
                        dest_data,
                        x='年度',
                        y=value_col,
                        color='施設名',
                        markers=True,
                        text=value_col,
                        title=f"{dest} - 施設間比較推移"
                    )
                    if value_col == '推定患者数':
                        fig.update_traces(texttemplate="%{text:,.0f}", textposition="top center",
                                          textfont=dict(size=10))
                    else:
                        fig.update_traces(texttemplate="%{text:.1%}", textposition="top center",
                                          textfont=dict(size=10))
                    fig.update_yaxes(tickformat=tickfmt)
                    fig.update_layout(height=400, hovermode='x unified')
                    st.plotly_chart(fig, use_container_width=True)

        if len(facilities) == 1:
            fig_main.update_yaxes(tickformat=tickfmt)
            fig_main.update_layout(height=600, hovermode='x unified')
            st.plotly_chart(fig_main, use_container_width=True)

    # 年度別詳細表示
    st.markdown("---")
    st.markdown("#### 📊 年度別詳細分析")

    # 分析対象の年度を選択
    detail_year = st.selectbox(
        "詳細表示する年度を選択",
        selected_years,
        index=len(selected_years) - 1,
        key="facility_analysis_detail_year"
    )

    # 選択施設のデータ表示
    for facility in facilities:
        st.markdown(f"### {facility} - {detail_year}年度")

        facility_year_data = loader.get_facility_data(facility, detail_year)
        facility_year_data = facility_year_data[facility_year_data['退院先'].isin(config["destinations"])]

        col1, col2 = st.columns([1, 1])

        with col1:
            # 円グラフ（構成比は常に割合ベース）
            fig_pie = px.pie(
                facility_year_data,
                values='割合',
                names='退院先',
                title="退院先内訳",
                hole=0.4
            )
            fig_pie.update_traces(textposition='inside', textinfo='percent+label')
            fig_pie.update_layout(height=400)
            st.plotly_chart(fig_pie, use_container_width=True)

        with col2:
            # 主要指標
            home_data = facility_year_data[facility_year_data['退院先'].str.contains('家庭への退院')]
            transfer_data = facility_year_data[facility_year_data['退院先'] == '他の病院・診療所への転院']
            death_data = facility_year_data[facility_year_data['退院先'] == '終了（死亡等）']

            home_val = home_data[value_col].sum()
            transfer_val = transfer_data[value_col].sum()
            death_val = death_data[value_col].sum()

            label = "家庭復帰" if value_col == '推定患者数' else "家庭復帰率"
            # メトリクス
            metric_col1, metric_col2 = st.columns(2)
            with metric_col1:
                st.metric(f"🏠 {label}", fmt_value(home_val, config))
                st.metric("🏥 転院" + ("" if value_col == '推定患者数' else "率"), fmt_value(transfer_val, config))
            with metric_col2:
                st.metric("💔 死亡" + ("" if value_col == '推定患者数' else "率"), fmt_value(death_val, config))

            # データテーブル
            st.markdown("**詳細データ**")
            display_cols = ['退院先', '割合', '推定患者数'] if '推定患者数' in facility_year_data.columns else ['退院先', '割合']
            display_data = facility_year_data[display_cols].copy()
            display_data['割合'] = display_data['割合'].apply(lambda x: f"{x:.2%}")
            st.dataframe(display_data, use_container_width=True, hide_index=True, height=250)

        st.markdown("---")


def render_year_comparison(loader, config):
    """タブ2: 年度間比較"""
    st.markdown('<div class="sub-header">🔄 年度間比較分析</div>', unsafe_allow_html=True)

    facilities = config["facilities"] if config["facilities"] else [config["facility"]]
    selected_years = config["years"] if config["years"] else loader.years

    # 全年度のヒートマップ表示
    st.markdown("#### 📊 全年度推移ヒートマップ（選択施設）")

    for facility in facilities:
        st.markdown(f"### {facility}")

        # 施設の全年度データを取得
        facility_all_data = loader.get_facility_data(facility)
        facility_all_data = facility_all_data[
            (facility_all_data['退院先'].isin(config["destinations"])) &
            (facility_all_data['年度'].isin(selected_years))
        ]

        value_col = get_value_col(config)
        tickfmt = get_tickformat(config)
        color_label = "推定患者数" if value_col == '推定患者数' else "割合"
        text_fmt = ",.0f" if value_col == '推定患者数' else ".1%"

        # ピボットテーブル作成
        pivot_data = facility_all_data.pivot(
            index='退院先',
            columns='年度',
            values=value_col
        )

        # ヒートマップ
        fig_heatmap = px.imshow(
            pivot_data,
            labels=dict(x="年度", y="退院先", color=color_label),
            x=pivot_data.columns,
            y=pivot_data.index,
            color_continuous_scale="Blues",
            aspect="auto",
            text_auto=text_fmt
        )
        fig_heatmap.update_layout(height=500)
        fig_heatmap.update_xaxes(side="top")
        st.plotly_chart(fig_heatmap, use_container_width=True)

        # 年度間変化テーブル（割合ベースで表示）
        if len(selected_years) >= 2:
            st.markdown(f"**年度間変化（{selected_years[0]} → {selected_years[-1]}）**")

            year_start = selected_years[0]
            year_end = selected_years[-1]

            comparison_data = loader.get_year_comparison(year_start, year_end)
            comparison_data = comparison_data[
                (comparison_data['施設名'] == facility) &
                (comparison_data['退院先'].isin(config["destinations"]))
            ]

            if not comparison_data.empty:
                display_comparison = comparison_data[[
                    '退院先',
                    f'割合_{year_start}',
                    f'割合_{year_end}',
                    '差分'
                ]].copy()

                display_comparison.columns = ['退院先', f'{year_start}', f'{year_end}', '変化']
                display_comparison[f'{year_start}'] = display_comparison[f'{year_start}'].apply(lambda x: f"{x:.2%}")
                display_comparison[f'{year_end}'] = display_comparison[f'{year_end}'].apply(lambda x: f"{x:.2%}")
                display_comparison['変化'] = display_comparison['変化'].apply(
                    lambda x: f"+{x:.2%}" if x > 0 else f"{x:.2%}"
                )

                # 変化の大きい順にソート
                comparison_data['abs_diff'] = comparison_data['差分'].abs()
                display_comparison['abs_diff'] = comparison_data['abs_diff'].values
                display_comparison = display_comparison.sort_values('abs_diff', ascending=False).drop('abs_diff', axis=1)

                st.dataframe(display_comparison, use_container_width=True, hide_index=True)

        st.markdown("---")

    # 2年度間の詳細比較
    st.markdown("---")
    st.markdown("#### 🔍 2年度間詳細比較")

    year1 = config["compare_year1"]
    year2 = config["compare_year2"]

    if year1 == year2:
        st.warning("異なる年度を選択してください")
        return

    # 全施設の比較データ取得
    comparison_all = loader.get_year_comparison(year1, year2)
    comparison_all = comparison_all[comparison_all['退院先'].isin(config["destinations"])]

    # ヒートマップ用のピボットテーブル
    pivot_diff = comparison_all.pivot(
        index='施設名',
        columns='退院先',
        values='差分'
    )

    st.markdown(f"#### {year1} → {year2} の変化（全施設ヒートマップ）")

    # ヒートマップ
    fig_heatmap_diff = px.imshow(
        pivot_diff,
        labels=dict(x="退院先", y="施設名", color="変化率"),
        x=pivot_diff.columns,
        y=pivot_diff.index,
        color_continuous_scale="RdYlGn",
        color_continuous_midpoint=0,
        aspect="auto",
        text_auto=".1%"
    )
    fig_heatmap_diff.update_layout(height=600)
    fig_heatmap_diff.update_xaxes(side="top")
    st.plotly_chart(fig_heatmap_diff, use_container_width=True)


def render_facility_comparison(loader, config):
    """タブ3: 施設間比較"""
    st.markdown('<div class="sub-header">🏥 施設間比較分析</div>', unsafe_allow_html=True)

    selected_years = config["years"] if config["years"] else loader.years

    # 比較する退院先カテゴリを選択（先頭にプレースホルダーを追加）
    _PLACEHOLDER = "比較する退院先カテゴリを選択"
    comparison_dest = st.selectbox(
        "比較する退院先カテゴリを選択",
        [_PLACEHOLDER] + config["destinations"],
        index=0
    )

    if comparison_dest == _PLACEHOLDER:
        st.info("退院先カテゴリを選択してください")
        return

    # 全施設データ取得
    all_facilities = loader.get_facility_list()

    # 複数施設選択：デフォルトで4施設
    default_keywords = ["信州医療センター", "長野赤十字病院", "長野市民病院", "北信総合病院"]
    default_facilities = [f for f in all_facilities if any(kw in f for kw in default_keywords)]
    selected_facilities = st.multiselect(
        "比較する施設を選択（複数可）",
        all_facilities,
        default=default_facilities
    )

    if not selected_facilities:
        st.warning("少なくとも1つの施設を選択してください")
        return

    # 全年度の推移比較（メイン表示）
    st.markdown("#### 📈 施設間推移比較（全年度）")

    trend_data_list = []
    for facility in selected_facilities:
        facility_trend = loader.get_facility_data(facility)
        facility_trend = facility_trend[
            (facility_trend['退院先'] == comparison_dest) &
            (facility_trend['年度'].isin(selected_years))
        ]
        trend_data_list.append(facility_trend)

    value_col = get_value_col(config)
    tickfmt = get_tickformat(config)
    color_label = "推定患者数" if value_col == '推定患者数' else "割合"
    text_fmt = ",.0f" if value_col == '推定患者数' else ".1%"

    if trend_data_list:
        trend_data = pd.concat(trend_data_list)

        fig_trend = px.line(
            trend_data,
            x='年度',
            y=value_col,
            color='施設名',
            markers=True,
            title=f"{comparison_dest} - 全年度推移比較"
        )
        fig_trend.update_yaxes(tickformat=tickfmt)
        fig_trend.update_layout(height=600, hovermode='x unified')
        st.plotly_chart(fig_trend, use_container_width=True)

    # 年度別比較棒グラフ
    st.markdown("---")
    st.markdown("#### 📊 年度別施設間比較")

    detail_year = st.selectbox(
        "詳細表示する年度を選択",
        selected_years,
        index=len(selected_years) - 1,
        key="facility_comparison_detail_year"
    )

    comparison_data = loader.get_facility_comparison(
        selected_facilities,
        comparison_dest,
        detail_year
    )

    mean_value = comparison_data[value_col].mean()

    # 横並び棒グラフ
    fig_bar = go.Figure()

    if value_col == '推定患者数':
        bar_text = comparison_data[value_col].apply(lambda x: f"{int(x):,}件" if pd.notna(x) else "-")
        mean_label = f"平均: {int(mean_value):,}件"
        y_title = "推定患者数（件）"
    else:
        bar_text = comparison_data[value_col].apply(lambda x: f"{x:.1%}")
        mean_label = f"平均: {mean_value:.1%}"
        y_title = "割合"

    fig_bar.add_trace(go.Bar(
        x=comparison_data['施設名'],
        y=comparison_data[value_col],
        name=comparison_dest,
        text=bar_text,
        textposition='outside',
        marker_color='lightblue'
    ))

    fig_bar.add_hline(
        y=mean_value,
        line_dash="dash",
        line_color="red",
        annotation_text=mean_label,
        annotation_position="right"
    )

    fig_bar.update_layout(
        title=f"{comparison_dest} - 施設間比較（{detail_year}）",
        xaxis_title="施設名",
        yaxis_title=y_title,
        height=600,
        showlegend=False
    )
    fig_bar.update_yaxes(tickformat=tickfmt)
    fig_bar.update_xaxes(tickangle=-45)

    st.plotly_chart(fig_bar, use_container_width=True)

    # 各年度の施設間ヒートマップ
    st.markdown("---")
    st.markdown("#### 🔥 施設×年度ヒートマップ")

    heatmap_data_list = []
    for facility in selected_facilities:
        facility_data = loader.get_facility_data(facility)
        facility_data = facility_data[
            (facility_data['退院先'] == comparison_dest) &
            (facility_data['年度'].isin(selected_years))
        ]
        heatmap_data_list.append(facility_data)

    if heatmap_data_list:
        heatmap_data = pd.concat(heatmap_data_list)

        pivot_heatmap = heatmap_data.pivot(
            index='施設名',
            columns='年度',
            values=value_col
        )

        fig_heatmap = px.imshow(
            pivot_heatmap,
            labels=dict(x="年度", y="施設名", color=color_label),
            x=pivot_heatmap.columns,
            y=pivot_heatmap.index,
            color_continuous_scale="Blues",
            aspect="auto",
            text_auto=text_fmt
        )
        fig_heatmap.update_layout(height=max(400, len(selected_facilities) * 40))
        fig_heatmap.update_xaxes(side="top")
        st.plotly_chart(fig_heatmap, use_container_width=True)


def render_data_table(loader, config):
    """タブ4: データテーブル"""
    st.markdown('<div class="sub-header">📋 データテーブル</div>', unsafe_allow_html=True)

    # フィルタオプション
    col1, col2, col3 = st.columns(3)

    with col1:
        filter_facilities = st.multiselect(
            "施設でフィルタ",
            loader.get_facility_list(),
            default=None
        )

    with col2:
        filter_years = st.multiselect(
            "年度でフィルタ",
            loader.years,
            default=None
        )

    with col3:
        filter_destinations = st.multiselect(
            "退院先でフィルタ",
            config["destinations"],
            default=None
        )

    # データ取得
    display_data = loader.processed_data.copy()

    # フィルタ適用
    if filter_facilities:
        display_data = display_data[display_data['施設名'].isin(filter_facilities)]
    if filter_years:
        display_data = display_data[display_data['年度'].isin(filter_years)]
    if filter_destinations:
        display_data = display_data[display_data['退院先'].isin(filter_destinations)]

    # 表示用に整形
    display_data['割合_表示'] = display_data['割合'].apply(lambda x: f"{x:.4f}")

    st.markdown(f"#### 表示件数: {len(display_data)} 件")

    # 推定患者数列があれば表示列に追加
    show_cols = ['施設名', '年度', '退院先', '割合_表示']
    csv_cols = ['告示番号', '通番', '施設名', '年度', '退院先', '割合']
    if '推定患者数' in display_data.columns:
        show_cols.append('推定患者数')
        csv_cols.append('推定患者数')

    st.dataframe(
        display_data[show_cols],
        use_container_width=True,
        height=600,
        hide_index=True
    )

    # CSVダウンロード
    csv = display_data[csv_cols].to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        label="📥 CSVダウンロード",
        data=csv,
        file_name="discharge_data.csv",
        mime="text/csv"
    )


def main():
    """メインアプリケーション"""
    # ヘッダー
    st.markdown('<div class="main-header">🏥 退院先推移分析ダッシュボード</div>', unsafe_allow_html=True)
    st.markdown("長野県内医療機関の退院先データを可視化・分析")

    # 入院元実績テーブル
    st.markdown("#### 当院への入院元実績（件）")
    nyuin_df = pd.DataFrame(
        {
            "信州医療センター":    [28, 28],
            "長野赤十字病院":      [10,  10],
            "長野市民病院":        [ 8, 14],
            "北信総合病院":        [12,  8],
            "飯山赤十字病院":      [ 4,  1],
            "林脳神経外科病院":    [ 1,  2],
            "長野中央病院":        [ 4,  1],
            "長野松代総合病院":    [ 1,  0],
            "篠ノ井総合病院":      [ 1,  0],
        },
        index=["令和6年", "令和7年"]
    )
    st.dataframe(nyuin_df, use_container_width=True)
    st.markdown("---")

    # データ読み込み
    try:
        loader = load_discharge_data()
    except Exception as e:
        st.error(f"データの読み込みに失敗しました: {e}")
        return

    # サイドバー
    config = render_sidebar(loader)

    # タブ作成
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 施設別分析",
        "🔄 年度間比較",
        "🏥 施設間比較",
        "📋 データテーブル"
    ])

    with tab1:
        render_facility_analysis(loader, config)

    with tab2:
        render_year_comparison(loader, config)

    with tab3:
        render_facility_comparison(loader, config)

    with tab4:
        render_data_table(loader, config)


if __name__ == "__main__":
    main()

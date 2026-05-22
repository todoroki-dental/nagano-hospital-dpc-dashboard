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


@st.cache_resource(ttl=3600)
def load_demographics():
    """人口動態データを読み込み（キャッシュ）"""
    from discharge_data_loader import load_demographics_data
    return load_demographics_data()


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


def build_destination_color_map(destinations: list) -> dict:
    """退院先ごとの固定カラーマップを生成する"""
    palette = px.colors.qualitative.D3  # 10色
    return {dest: palette[i % len(palette)] for i, dest in enumerate(destinations)}


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

    # 人口動態オーバーレイ設定
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 👥 人口動態オーバーレイ")
    st.sidebar.markdown("カテゴリ比較タブのグラフに重ねて表示します。")
    _DEMO_METRICS = {
        "65歳以上割合": "65歳以上割合",
        "75歳以上割合": "75歳以上割合",
        "総人口": "総数",
        "65歳以上人口": "65歳以上",
        "75歳以上人口": "うち75歳以上",
    }
    try:
        demo_df = load_demographics()
        all_cities = sorted(demo_df['市町村名'].unique().tolist())
        demo_cities = st.sidebar.multiselect(
            "市町村（複数選択→合算）",
            all_cities,
            default=[],
            key="demo_cities",
        )
        demo_metrics = st.sidebar.multiselect(
            "重ねる指標",
            list(_DEMO_METRICS.keys()),
            default=[],
            key="demo_metrics",
        )
        _ratio_set = {"65歳以上割合", "75歳以上割合"}
        _count_set = {"総人口", "65歳以上人口", "75歳以上人口"}
        if any(m in _ratio_set for m in demo_metrics) and any(m in _count_set for m in demo_metrics):
            st.sidebar.warning("割合系と人数系の同時表示はスケールが合いません")
    except Exception:
        st.sidebar.error("人口動態データの読み込みに失敗しました")
        demo_cities, demo_metrics = [], []

    return {
        "facility": selected_facility,
        "facilities": selected_facilities,
        "year": selected_year,
        "years": selected_years,
        "compare_year1": compare_year1,
        "compare_year2": compare_year2,
        "destinations": selected_destinations if selected_destinations else loader.destinations,
        "display_mode": display_mode,
        "color_map": build_destination_color_map(loader.destinations),
        "demo_cities": demo_cities,
        "demo_metrics": demo_metrics,
        "demo_metric_cols": [_DEMO_METRICS[m] for m in demo_metrics],
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

        # 選択退院先の合計折れ線グラフ（施設ごとに1本）
        st.markdown("#### 📈 退院先合計推移")
        fig_total = go.Figure()

        # 施設ごとに合計値の線を追加
        for facility in facilities:
            fac_data = all_data[all_data['施設名'] == facility]
            total = fac_data.groupby('年度', sort=False)[value_col].sum().reset_index()
            # 年度順にソート
            total = total.set_index('年度').reindex(selected_years).reset_index()
            if value_col == '推定患者数':
                text_vals = total[value_col].apply(lambda x: f"{int(x):,}" if pd.notna(x) else "")
            else:
                text_vals = total[value_col].apply(lambda x: f"{x:.1%}" if pd.notna(x) else "")
            fig_total.add_trace(go.Scatter(
                x=total['年度'],
                y=total[value_col],
                name=facility,
                mode='lines+markers+text',
                text=text_vals,
                textposition='top center',
                textfont=dict(size=12),
                legendgroup='facilities'
            ))

        # 凡例に集計対象の退院先をダミー表示
        for dest in config["destinations"]:
            fig_total.add_trace(go.Scatter(
                x=[None], y=[None],
                name=dest,
                mode='lines',
                line=dict(width=0),
                showlegend=True,
                legendgroup='destinations'
            ))

        fig_total.update_yaxes(tickformat=tickfmt)
        fig_total.update_layout(
            height=450,
            hovermode='x unified',
            legend=dict(title="施設 / 集計退院先")
        )
        st.plotly_chart(fig_total, use_container_width=True)

        # スタック棒グラフ
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
            color_discrete_map=config["color_map"],
            title="退院先構成推移（スタック）",
            height=500 if len(facilities) <= 2 else 800
        )
        fig_stack.update_yaxes(tickformat=tickfmt)
        fig_stack.update_xaxes(showticklabels=True)
        fig_stack.update_layout(hovermode='x unified', legend=dict(traceorder='reversed'))
        st.plotly_chart(fig_stack, use_container_width=True)

        # 複数施設を合算した退院先別推移
        st.markdown("#### 📈 退院先別推移（施設合算）")
        selected_multi = st.multiselect(
            "合算する施設を選択（複数可）",
            facilities,
            default=facilities,
            key="dest_trend_multi_facility"
        )
        if selected_multi:
            multi_data = all_data[all_data['施設名'].isin(selected_multi)]
            # 施設を合算：年度×退院先 でグループ化して合計
            agg_data = multi_data.groupby(['年度', '退院先'], sort=False)[value_col].sum().reset_index()
            # 年度を選択順に並べ直す
            agg_data['年度'] = pd.Categorical(agg_data['年度'], categories=selected_years, ordered=True)
            agg_data = agg_data.sort_values('年度')

            fig_agg = px.line(
                agg_data,
                x='年度',
                y=value_col,
                color='退院先',
                markers=True,
                text=value_col,
                color_discrete_map=config["color_map"],
                title=f"退院先別推移（合算：{'・'.join(selected_multi)}）"
            )
            if value_col == '推定患者数':
                fig_agg.update_traces(texttemplate="%{text:,.0f}", textposition="top center",
                                      textfont=dict(size=12))
            else:
                fig_agg.update_traces(texttemplate="%{text:.1%}", textposition="top center",
                                      textfont=dict(size=12))
            fig_agg.update_yaxes(tickformat=tickfmt)
            fig_agg.update_layout(height=500, hovermode='x unified')
            st.plotly_chart(fig_agg, use_container_width=True)
        else:
            st.info("施設を1つ以上選択してください")

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
                color_discrete_map=config["color_map"],
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
                                          textfont=dict(size=12))
                    else:
                        fig.update_traces(texttemplate="%{text:.1%}", textposition="top center",
                                          textfont=dict(size=12))
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
                color='退院先',
                color_discrete_map=config["color_map"],
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


_DEMO_COLORS = ["#ff7f0e", "#d62728", "#9467bd", "#8c564b"]


def _add_demographics_traces(
    fig: go.Figure,
    demo_df: pd.DataFrame,
    cities: list,
    metric_cols: list,
    metric_labels: list,
    years: list,
    has_right_axis: bool = False,
) -> go.Figure:
    """人口動態の折れ線を第3Y軸（y3）として fig に追加する"""
    if not cities or not metric_cols:
        return fig

    filtered = demo_df[demo_df['市町村名'].isin(cities)]
    agg = filtered.groupby('年度').agg(
        総数=('総数', 'sum'),
        **{'65歳以上': ('65歳以上', 'sum')},
        **{'うち75歳以上': ('うち75歳以上', 'sum')},
    ).reset_index()
    agg['65歳以上割合'] = agg['65歳以上'] / agg['総数']
    agg['75歳以上割合'] = agg['うち75歳以上'] / agg['総数']

    common_years = [y for y in years if y in agg['年度'].values]
    if not common_years:
        return fig
    agg = agg[agg['年度'].isin(common_years)]
    agg['年度'] = pd.Categorical(agg['年度'], categories=common_years, ordered=True)
    agg = agg.sort_values('年度')

    city_label = "・".join(cities) if len(cities) <= 3 else f"{cities[0]}他{len(cities) - 1}市町村"
    is_ratio_col = {'65歳以上割合', '75歳以上割合'}

    for i, (col, label) in enumerate(zip(metric_cols, metric_labels)):
        is_ratio = col in is_ratio_col
        y_vals = list(agg[col])
        text_vals = [f"{v:.1%}" if is_ratio else f"{int(v):,}" for v in y_vals]
        fig.add_trace(go.Scatter(
            x=list(agg['年度']),
            y=y_vals,
            name=f"{label}（{city_label}）",
            mode='lines+markers+text',
            text=text_vals,
            textposition='bottom center',
            textfont=dict(size=10),
            line=dict(color=_DEMO_COLORS[i % len(_DEMO_COLORS)], dash='dot', width=2),
            marker=dict(symbol='diamond', size=8),
            yaxis='y3',
            legendgroup='demographics',
            legendgrouptitle_text='人口動態' if i == 0 else None,
        ))

    # y2軸が既にある場合は y3 を右外側にオフセット
    yaxis3_cfg = dict(overlaying='y', side='right', showgrid=False, tickformat=".1%")
    if has_right_axis:
        yaxis3_cfg.update(anchor='free', position=1.05)
    fig.update_layout(yaxis3=yaxis3_cfg)
    return fig


def render_category_comparison(loader, config):
    """タブ5: 退院先カテゴリ比較分析"""
    st.markdown('<div class="sub-header">📊 退院先カテゴリ比較分析</div>', unsafe_allow_html=True)
    st.markdown("退院先を意味のあるグループにまとめて年度推移を比較します。")

    ALL_DESTS = loader.destinations

    # デフォルトグループ定義
    DEFAULT_GROUPS = [
        {
            "name": "家庭への退院",
            "dests": [
                '家庭への退院（当院に通院）',
                '家庭への退院（他院への通院）',
                '家庭への退院（その他）',
            ],
            "color": "#27ae60",
        },
        {
            "name": "介護施設系",
            "dests": [
                '介護老人保健施設に入所',
                '介護老人福祉施設に入所',
                '社会福祉施設、有料老人ホーム等に入所',
                '介護医療院',
            ],
            "color": "#2980b9",
        },
        {
            "name": "その他医療機関・診療所",
            "dests": ['他の病院・診療所への転院'],
            "color": "#e67e22",
        },
        {
            "name": "その他・終了",
            "dests": ['その他', '終了（死亡等）'],
            "color": "#c0392b",
        },
        {
            "name": "グループ5",
            "dests": [],
            "color": "#8e44ad",
        },
        {
            "name": "グループ6",
            "dests": [],
            "color": "#16a085",
        },
    ]

    # 施設・年度の選択（このタブ専用）
    ctrl_col1, ctrl_col2 = st.columns(2)
    with ctrl_col1:
        all_facilities = loader.get_facility_list()
        default_facs = config["facilities"] or [
            f for f in all_facilities
            if any(kw in f for kw in ["信州医療センター", "長野赤十字病院", "長野市民病院", "北信総合病院"])
        ]
        selected_facilities = st.multiselect(
            "🏥 医療機関（複数可）",
            all_facilities,
            default=default_facs,
            key="cat_fac",
        )
    with ctrl_col2:
        selected_years = st.multiselect(
            "📅 年度（複数可）",
            loader.years,
            default=config["years"] or loader.years,
            key="cat_yr",
        )

    transparent_bg = st.checkbox(
        "📸 PNG出力時に背景を透過にする（ツールバーのカメラアイコンで有効）",
        value=False,
        key="cat_transparent_bg",
    )

    if not selected_facilities or not selected_years:
        st.warning("医療機関と年度を少なくとも1つ選択してください")
        return

    def _apply_bg(fig):
        """透過背景モード時に paper_bgcolor / plot_bgcolor を透明に設定する"""
        if transparent_bg:
            fig.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
            )
        return fig

    value_col = get_value_col(config)
    tickfmt = get_tickformat(config)

    # カテゴリグループのカスタマイズ
    with st.expander("⚙️ カテゴリグループのカスタマイズ", expanded=False):
        st.markdown("グループ名・含める退院先・色を変更できます。")
        exp_cols = st.columns(3)
        groups_config = []
        for i, grp in enumerate(DEFAULT_GROUPS):
            with exp_cols[i % 3]:
                grp_name = st.text_input("グループ名", value=grp["name"], key=f"grp_name_{i}")
                grp_dests = st.multiselect(
                    "含める退院先",
                    ALL_DESTS,
                    default=[d for d in grp["dests"] if d in ALL_DESTS],
                    key=f"grp_dests_{i}",
                )
                grp_color = st.color_picker("色", value=grp["color"], key=f"grp_color_{i}")
                grp_chart_type = st.radio(
                    "グラフ種類",
                    ["棒グラフ", "折れ線"],
                    index=1,
                    key=f"grp_chart_{i}",
                    horizontal=True,
                )
                grp_yaxis = st.radio(
                    "Y軸",
                    ["左", "右"],
                    key=f"grp_yaxis_{i}",
                    horizontal=True,
                )
                if grp_dests:
                    groups_config.append({
                        "name": grp_name,
                        "dests": grp_dests,
                        "color": grp_color,
                        "chart_type": "bar" if grp_chart_type == "棒グラフ" else "line",
                        "yaxis": "left" if grp_yaxis == "左" else "right",
                    })

    if not groups_config:
        groups_config = DEFAULT_GROUPS

    color_map = {g["name"]: g["color"] for g in groups_config}
    group_order = [g["name"] for g in groups_config]

    # グループ別に集計
    all_rows = []
    for facility in selected_facilities:
        fac_data = loader.get_facility_data(facility)
        fac_data = fac_data[fac_data['年度'].isin(selected_years)]
        _agg_cols = ['割合', '推定患者数'] if '推定患者数' in fac_data.columns else ['割合']
        for grp in groups_config:
            summed = (
                fac_data[fac_data['退院先'].isin(grp["dests"])]
                .groupby('年度', sort=False)[_agg_cols]
                .sum()
                .reset_index()
            )
            summed['施設名'] = facility
            summed['グループ'] = grp["name"]
            all_rows.append(summed)

    if not all_rows:
        st.info("表示するデータがありません")
        return

    agg_df = pd.concat(all_rows, ignore_index=True)
    agg_df['年度'] = pd.Categorical(agg_df['年度'], categories=selected_years, ordered=True)
    agg_df['グループ'] = pd.Categorical(agg_df['グループ'], categories=group_order, ordered=True)
    agg_df = agg_df.sort_values(['施設名', 'グループ', '年度'])

    # 件数と割合を両方表示するラベル列を作成
    _has_count = '推定患者数' in agg_df.columns

    def _dual_label(row):
        if _has_count and pd.notna(row['推定患者数']):
            return f"{int(row['推定患者数']):,}件<br>({row['割合']:.1%})"
        return f"{row['割合']:.1%}"

    agg_df['表示ラベル'] = agg_df.apply(_dual_label, axis=1)

    # レイアウト計算
    n_fac = len(selected_facilities)
    n_rows = (n_fac + 1) // 2
    chart_height = max(450, 350 + (n_rows - 1) * 280)
    use_facet = n_fac > 1

    def _add_group_traces(fig, df, grp, row=None, col=None, show_legend=True, secondary_y=False):
        """1グループ分のトレース（折れ線 or 棒）をfigに追加する"""
        gd = df[df['グループ'] == grp['name']].sort_values('年度')
        kw = dict(name=grp['name'], legendgroup=grp['name'], showlegend=show_legend)
        if row is None:
            # 単一パネル：右軸はトレースのyaxisキーで指定
            if secondary_y:
                kw['yaxis'] = 'y2'
            add_kw = {}
        else:
            # サブプロット：secondary_yをadd_traceに渡す
            add_kw = dict(row=row, col=col)
            if secondary_y:
                add_kw['secondary_y'] = True
        if grp.get('chart_type', 'line') == 'line':
            fig.add_trace(go.Scatter(
                x=list(gd['年度']),
                y=list(gd[value_col]),
                mode='lines+markers+text',
                text=list(gd['表示ラベル']),
                texttemplate='%{text}',
                textposition='top center',
                textfont=dict(size=11),
                marker_color=grp['color'],
                line_color=grp['color'],
                **kw,
            ), **add_kw)
        else:
            fig.add_trace(go.Bar(
                x=list(gd['年度']),
                y=list(gd[value_col]),
                marker_color=grp['color'],
                **kw,
            ), **add_kw)

    _has_right_axis = any(grp.get('yaxis', 'left') == 'right' for grp in groups_config)

    def _build_mixed_fig(df, title, height):
        """単一パネル用の混合グラフを生成する"""
        fig = go.Figure()
        for grp in groups_config:
            _add_group_traces(fig, df, grp, secondary_y=(grp.get('yaxis', 'left') == 'right'))
        if _has_right_axis:
            fig.update_layout(
                yaxis2=dict(overlaying='y', side='right', tickformat=tickfmt, showgrid=False)
            )
        fig.update_layout(barmode='stack', height=height, hovermode='x unified', title=title)
        fig.update_yaxes(tickformat=tickfmt)
        return fig

    def _build_facet_mixed_fig(title, height):
        """複数施設のサブプロット混合グラフを生成する"""
        from plotly.subplots import make_subplots
        n_cols = min(n_fac, 2)
        nr = (n_fac + 1) // 2
        mkw = dict(rows=nr, cols=n_cols, subplot_titles=selected_facilities, shared_xaxes=False)
        if _has_right_axis:
            mkw['specs'] = [[{'secondary_y': True}] * n_cols for _ in range(nr)]
        fig = make_subplots(**mkw)
        for fi, facility in enumerate(selected_facilities):
            row = fi // n_cols + 1
            col_idx = fi % n_cols + 1
            fac_df = agg_df[agg_df['施設名'] == facility]
            for grp in groups_config:
                _add_group_traces(
                    fig, fac_df, grp,
                    row=row, col=col_idx,
                    show_legend=(fi == 0),
                    secondary_y=(grp.get('yaxis', 'left') == 'right'),
                )
        fig.update_layout(barmode='stack', height=height, hovermode='x unified', title=title)
        fig.update_yaxes(tickformat=tickfmt)
        return fig

    # 施設別グラフ（折れ線・棒をグループ設定に従って混合表示）
    st.markdown("#### 📊 年度別推移")
    if use_facet:
        fig_main = _build_facet_mixed_fig("退院先カテゴリ別年度推移", chart_height)
    else:
        single_df = agg_df[agg_df['施設名'] == selected_facilities[0]]
        fig_main = _build_mixed_fig(single_df, f"{selected_facilities[0]} - 退院先カテゴリ別年度推移", chart_height)
        if config.get("demo_cities") and config.get("demo_metric_cols"):
            fig_main = _add_demographics_traces(
                fig_main, load_demographics(),
                config["demo_cities"], config["demo_metric_cols"], config["demo_metrics"],
                selected_years, has_right_axis=_has_right_axis,
            )
    st.plotly_chart(_apply_bg(fig_main), use_container_width=True)

    combined_df = None  # 後段のダウンロード処理で参照するため事前に初期化

    # 全施設合算グラフ（複数施設時のみ）
    if use_facet:
        st.markdown("---")
        fac_label = "・".join(selected_facilities)
        st.markdown(f"#### 🔢 全施設合算（{len(selected_facilities)}施設）")

        _comb_cols = ['割合', '推定患者数'] if _has_count else ['割合']
        combined_df = (
            agg_df.groupby(['年度', 'グループ'], sort=False)[_comb_cols]
            .sum()
            .reset_index()
        )
        # 割合を患者数ベースで再計算（施設ごとの割合を単純合算すると100%超になるため）
        if _has_count:
            _year_total = combined_df.groupby('年度')['推定患者数'].transform('sum')
            combined_df['割合'] = combined_df['推定患者数'] / _year_total
        else:
            combined_df['割合'] = combined_df['割合'] / len(selected_facilities)
        combined_df['年度'] = pd.Categorical(combined_df['年度'], categories=selected_years, ordered=True)
        combined_df['グループ'] = pd.Categorical(combined_df['グループ'], categories=group_order, ordered=True)
        combined_df = combined_df.sort_values(['グループ', '年度'])
        combined_df['表示ラベル'] = combined_df.apply(_dual_label, axis=1)

        fig_comb = _build_mixed_fig(
            combined_df,
            f"全施設合算 - カテゴリ別年度推移（{fac_label}）",
            450,
        )
        if config.get("demo_cities") and config.get("demo_metric_cols"):
            fig_comb = _add_demographics_traces(
                fig_comb, load_demographics(),
                config["demo_cities"], config["demo_metric_cols"], config["demo_metrics"],
                selected_years, has_right_axis=_has_right_axis,
            )
        st.plotly_chart(_apply_bg(fig_comb), use_container_width=True)

    # 施設横断グループ比較（複数施設時のみ）
    if use_facet:
        st.markdown("#### 🔍 グループ別・施設間比較（折れ線）")
        st.markdown("各グループを独立したグラフで施設間比較します。")
        n_groups = len(groups_config)
        grp_cols = st.columns(min(n_groups, 2))
        for gi, grp in enumerate(groups_config):
            grp_df = agg_df[agg_df['グループ'] == grp["name"]]
            with grp_cols[gi % 2]:
                fig_g = px.line(
                    grp_df,
                    x='年度',
                    y=value_col,
                    color='施設名',
                    text='表示ラベル',
                    markers=True,
                    title=grp["name"],
                    category_orders={"施設名": selected_facilities},
                )
                fig_g.update_traces(texttemplate="%{text}", textposition="top center", textfont=dict(size=11))
                fig_g.update_yaxes(tickformat=tickfmt)
                fig_g.update_layout(height=350, hovermode='x unified', showlegend=True)
                st.plotly_chart(_apply_bg(fig_g), use_container_width=True)

    # 集計データとダウンロード
    st.markdown("---")
    st.markdown("#### 📥 集計データのダウンロード")

    _dl_show_cols = ['施設名', '年度', 'グループ', '割合'] + (['推定患者数'] if _has_count else [])
    _dl_tabs = ["施設別データ"] + (["全施設合算データ"] if combined_df is not None else [])
    dl_tab_list = st.tabs(_dl_tabs)

    with dl_tab_list[0]:
        _disp = agg_df[_dl_show_cols].copy()
        _disp['割合'] = _disp['割合'].apply(lambda x: f"{x:.2%}")
        st.dataframe(_disp, use_container_width=True, hide_index=True, height=300)
        _csv1 = agg_df[_dl_show_cols].to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 施設別データをCSVダウンロード",
            data=_csv1,
            file_name="category_by_facility.csv",
            mime="text/csv",
            key="dl_facility",
        )

    if combined_df is not None:
        with dl_tab_list[1]:
            _comb_show_cols = ['年度', 'グループ', '割合'] + (['推定患者数'] if _has_count else [])
            _disp_c = combined_df[_comb_show_cols].copy()
            _disp_c['割合'] = _disp_c['割合'].apply(lambda x: f"{x:.2%}")
            st.dataframe(_disp_c, use_container_width=True, hide_index=True, height=300)
            _csv2 = combined_df[_comb_show_cols].to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📥 全施設合算データをCSVダウンロード",
                data=_csv2,
                file_name="category_combined.csv",
                mime="text/csv",
                key="dl_combined",
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
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 施設別分析",
        "🔄 年度間比較",
        "🏥 施設間比較",
        "📋 データテーブル",
        "📈 カテゴリ比較",
    ])

    with tab1:
        render_facility_analysis(loader, config)

    with tab2:
        render_year_comparison(loader, config)

    with tab3:
        render_facility_comparison(loader, config)

    with tab4:
        render_data_table(loader, config)

    with tab5:
        render_category_comparison(loader, config)


if __name__ == "__main__":
    main()

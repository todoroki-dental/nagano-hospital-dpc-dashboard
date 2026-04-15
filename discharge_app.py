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
    loader.load_data().process_data()
    return loader


def render_sidebar(loader):
    """サイドバーUIのレンダリング"""
    st.sidebar.title("🏥 退院先分析")
    st.sidebar.markdown("---")

    # 施設選択（複数選択に変更）
    facilities = loader.get_facility_list()
    selected_facilities = st.sidebar.multiselect(
        "📍 施設選択（複数可）",
        facilities,
        default=[facilities[0]]
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

    # 退院先カテゴリ選択
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📊 退院先カテゴリ")

    # カテゴリグループ化
    destination_groups = {
        "家庭への退院": [
            "家庭への退院（当院に通院）",
            "家庭への退院（他院への通院）",
            "家庭への退院（その他）"
        ],
        "施設入所": [
            "介護老人保健施設に入所",
            "介護老人福祉施設に入所",
            "社会福祉施設、有料老人ホーム等に入所",
            "介護医療院"
        ],
        "その他": [
            "他の病院・診療所への転院",
            "終了（死亡等）",
            "その他"
        ]
    }

    selected_destinations = []
    for group, dests in destination_groups.items():
        with st.sidebar.expander(group, expanded=True):
            for dest in dests:
                if st.checkbox(dest, value=True, key=f"dest_{dest}"):
                    selected_destinations.append(dest)

    return {
        "facility": selected_facility,
        "facilities": selected_facilities,
        "year": selected_year,
        "years": selected_years,
        "compare_year1": compare_year1,
        "compare_year2": compare_year2,
        "destinations": selected_destinations if selected_destinations else loader.destinations
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

    if trend_data_list:
        all_data = pd.concat(trend_data_list)

        # 施設が1つの場合は退院先で色分け、複数の場合は施設で色分け
        if len(facilities) == 1:
            # 単一施設：退院先で色分け
            fig_main = px.line(
                all_data,
                x='年度',
                y='割合',
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
                        y='割合',
                        color='施設名',
                        markers=True,
                        title=f"{dest} - 施設間比較推移"
                    )
                    fig.update_yaxes(tickformat=".1%")
                    fig.update_layout(height=400, hovermode='x unified')
                    st.plotly_chart(fig, use_container_width=True)

        if len(facilities) == 1:
            fig_main.update_yaxes(tickformat=".1%")
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
            # 円グラフ
            fig_pie = px.pie(
                facility_year_data,
                values='割合',
                names='退院先',
                title=f"退院先内訳",
                hole=0.4
            )
            fig_pie.update_traces(textposition='inside', textinfo='percent+label')
            fig_pie.update_layout(height=400)
            st.plotly_chart(fig_pie, use_container_width=True)

        with col2:
            # 主要指標
            home_rate = facility_year_data[
                facility_year_data['退院先'].str.contains('家庭への退院')
            ]['割合'].sum()

            transfer_rate = facility_year_data[
                facility_year_data['退院先'] == '他の病院・診療所への転院'
            ]['割合'].sum()

            death_rate = facility_year_data[
                facility_year_data['退院先'] == '終了（死亡等）'
            ]['割合'].sum()

            # メトリクス
            metric_col1, metric_col2 = st.columns(2)
            with metric_col1:
                st.metric("🏠 家庭復帰率", f"{home_rate:.1%}")
                st.metric("🏥 転院率", f"{transfer_rate:.1%}")
            with metric_col2:
                st.metric("💔 死亡率", f"{death_rate:.1%}")

            # データテーブル
            st.markdown("**詳細データ**")
            display_data = facility_year_data[['退院先', '割合']].copy()
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

        # ピボットテーブル作成
        pivot_data = facility_all_data.pivot(
            index='退院先',
            columns='年度',
            values='割合'
        )

        # ヒートマップ
        fig_heatmap = px.imshow(
            pivot_data,
            labels=dict(x="年度", y="退院先", color="割合"),
            x=pivot_data.columns,
            y=pivot_data.index,
            color_continuous_scale="Blues",
            aspect="auto",
            text_auto=".1%"
        )
        fig_heatmap.update_layout(height=500)
        fig_heatmap.update_xaxes(side="top")
        st.plotly_chart(fig_heatmap, use_container_width=True)

        # 年度間変化テーブル
        if len(selected_years) >= 2:
            st.markdown(f"**年度間変化（{selected_years[0]} → {selected_years[-1]}）**")

            # 最初と最後の年度で比較
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

    # 比較する退院先カテゴリを選択
    comparison_dest = st.selectbox(
        "比較する退院先カテゴリを選択",
        config["destinations"]
    )

    # 全施設データ取得
    all_facilities = loader.get_facility_list()

    # 複数施設選択
    selected_facilities = st.multiselect(
        "比較する施設を選択（複数可）",
        all_facilities,
        default=all_facilities  # デフォルトで全施設
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

    if trend_data_list:
        trend_data = pd.concat(trend_data_list)

        fig_trend = px.line(
            trend_data,
            x='年度',
            y='割合',
            color='施設名',
            markers=True,
            title=f"{comparison_dest} - 全年度推移比較"
        )
        fig_trend.update_yaxes(tickformat=".1%")
        fig_trend.update_layout(height=600, hovermode='x unified')
        st.plotly_chart(fig_trend, use_container_width=True)

    # 年度別比較棒グラフ
    st.markdown("---")
    st.markdown("#### 📊 年度別施設間比較")

    # 年度を選択
    detail_year = st.selectbox(
        "詳細表示する年度を選択",
        selected_years,
        index=len(selected_years) - 1,
        key="facility_comparison_detail_year"
    )

    # データ取得
    comparison_data = loader.get_facility_comparison(
        selected_facilities,
        comparison_dest,
        detail_year
    )

    # 平均値を計算
    mean_value = comparison_data['割合'].mean()

    # 横並び棒グラフ
    fig_bar = go.Figure()

    fig_bar.add_trace(go.Bar(
        x=comparison_data['施設名'],
        y=comparison_data['割合'],
        name=comparison_dest,
        text=comparison_data['割合'].apply(lambda x: f"{x:.1%}"),
        textposition='outside',
        marker_color='lightblue'
    ))

    # 平均線を追加
    fig_bar.add_hline(
        y=mean_value,
        line_dash="dash",
        line_color="red",
        annotation_text=f"平均: {mean_value:.1%}",
        annotation_position="right"
    )

    fig_bar.update_layout(
        title=f"{comparison_dest} - 施設間比較（{detail_year}）",
        xaxis_title="施設名",
        yaxis_title="割合",
        height=600,
        showlegend=False
    )
    fig_bar.update_yaxes(tickformat=".1%")
    fig_bar.update_xaxes(tickangle=-45)

    st.plotly_chart(fig_bar, use_container_width=True)

    # 各年度の施設間ヒートマップ
    st.markdown("---")
    st.markdown("#### 🔥 施設×年度ヒートマップ")

    # 選択施設と年度でデータを取得
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

        # ピボットテーブル作成
        pivot_heatmap = heatmap_data.pivot(
            index='施設名',
            columns='年度',
            values='割合'
        )

        # ヒートマップ
        fig_heatmap = px.imshow(
            pivot_heatmap,
            labels=dict(x="年度", y="施設名", color="割合"),
            x=pivot_heatmap.columns,
            y=pivot_heatmap.index,
            color_continuous_scale="Blues",
            aspect="auto",
            text_auto=".1%"
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

    # データテーブル表示
    st.dataframe(
        display_data[['施設名', '年度', '退院先', '割合_表示']],
        use_container_width=True,
        height=600,
        hide_index=True
    )

    # CSVダウンロード
    csv = display_data[['告示番号', '通番', '施設名', '年度', '退院先', '割合']].to_csv(index=False).encode('utf-8-sig')
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

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## アプリの起動

```bash
# nagano_hospital_comparison/ がリポジトリルート
streamlit run discharge_app.py
```

ローカルで動かす場合はプロジェクトルート（`dpc_dashboard/`）の venv を使う：

```bash
source ../venv/bin/activate
streamlit run discharge_app.py
```

## アーキテクチャ

### データフロー

```
data/ent_nagano.xlsx          → DischargeDataLoader → processed_data（長形式DataFrame）
data/length_of_stay.xlsx      →   （推定患者数の計算に使用）
data/医療圏人口動態R2-R7.xlsx → load_demographics_data() → 人口動態DataFrame
```

**`ent_nagano.xlsx` の構造**：シート「退院先」、2段ヘッダー `(年度, 退院先)` のワイドフォーマット。`DischargeDataLoader.process_data()` で施設×年度×退院先の長形式に変換する。

**推定患者数の計算**：`length_of_stay.xlsx` から年度別総患者数を取得し、退院先割合に掛けて算出。`load_data().load_los_data().process_data()` の順で呼ぶ必要がある。

### discharge_app.py の構造

`render_sidebar()` が `config` 辞書を返し、全タブ関数に渡す。

| キー | 内容 |
|---|---|
| `facilities` / `facility` | 選択施設リスト / 単一（後方互換） |
| `years` / `year` | 選択年度リスト / 単一（後方互換） |
| `destinations` | 選択退院先リスト |
| `display_mode` | `"割合（%）"` or `"推定患者数（件）"` |
| `color_map` | `{退院先名: 色コード}` |
| `demo_cities` | 人口動態オーバーレイ：選択市町村リスト |
| `demo_metrics` | 人口動態オーバーレイ：表示指標ラベルリスト |
| `demo_metric_cols` | 人口動態オーバーレイ：実際の列名リスト |

表示モードに応じた値列名・軸フォーマットは `get_value_col(config)` / `get_tickformat(config)` で取得する。

### 人口動態オーバーレイ（カテゴリ比較タブのみ）

`_add_demographics_traces(fig, demo_df, cities, metric_cols, metric_labels, years, has_right_axis)` で Plotly Figure の第3Y軸（`yaxis='y3'`）に折れ線を追加する。既存グラフが `yaxis2`（右軸）を使っている場合は `has_right_axis=True` を渡すと `position=1.05` でオフセットされる。

### Streamlit Cloud デプロイ

GitHub リポジトリ `todoroki-dental/nagano-hospital-dpc-dashboard` の `main` ブランチを Streamlit Cloud が監視している。push すると自動再デプロイされる。

変更後は `nagano_hospital_comparison/.git` から直接 push する：

```bash
git add <files>
git commit -m "..."
git push origin main
```

## データファイルの追加・更新時の注意

- 新しい年度データを `ent_nagano.xlsx` に追加した場合、`DischargeDataLoader.load_los_data()` 内の年度リスト（`['r1', 'r2', ...]`）も更新が必要
- 退院先カテゴリが変わった場合、`render_sidebar()` 内の `excluded_defaults` と `render_category_comparison()` の `DEFAULT_GROUPS` を確認する
- 人口動態データは `data/医療圏人口動態R2-R7.xlsx`（Sheet9）。列名が変わると `load_demographics_data()` が壊れる

## 施設と医療圏の対応（コード内に定義なし）

| 施設名 | 医療圏 |
|---|---|
| 信州医療センター、長野赤十字病院、長野市民病院、長野中央病院、篠ノ井総合病院 等 | 長野医療圏 |
| 北信総合病院、飯山赤十字病院 | 北信医療圏 |

施設→医療圏のマッピングはコード内に持たず、ユーザーが市町村を手動で選択する設計。
